import cv2
import numpy as np
import re
import os
import onnxruntime as ort

class PlateOCR:
    def __init__(
        self,
        model_path='models/best_ocr.onnx',
        conf_threshold=0.35,
        charset='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ',
        debug=False,
        debug_show_window=False,
        debug_save_dir='debug/ocr',
        debug_topk=3,
        crop_pad_ratio=0.15,
        use_nms=True,
        nms_iou_threshold=0.80,
        second_pass_enhance=True,
    ):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.charset = charset
        self.debug = debug
        self.debug_show_window = debug_show_window
        self.debug_save_dir = debug_save_dir
        self.debug_topk = max(1, int(debug_topk))
        self.crop_pad_ratio = max(0.0, float(crop_pad_ratio))
        self.use_nms = bool(use_nms)
        self.nms_iou_threshold = float(nms_iou_threshold)
        self.second_pass_enhance = bool(second_pass_enhance)
        self.debug_counter = 0
        self.session = None
        self.input_name = None
        self.input_width = 640
        self.input_height = 640

        if self.debug:
            os.makedirs(self.debug_save_dir, exist_ok=True)

        if not os.path.exists(model_path):
            print(f"WARNING: OCR model not found at {model_path}")
            return

        try:
            self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
            self.input_name = self.session.get_inputs()[0].name
            input_shape = self.session.get_inputs()[0].shape
            try:
                self.input_height = int(input_shape[2])
                self.input_width = int(input_shape[3])
            except (ValueError, TypeError):
                self.input_height = 640
                self.input_width = 640
        except Exception as e:
            print(f"WARNING: Failed to load OCR model {model_path}: {e}")
            self.session = None
            self.input_name = None
        
    def _pad_crop(self, img):
        if img is None or img.size == 0:
            return None

        h, w = img.shape[:2]
        pad_x = int(w * self.crop_pad_ratio)
        pad_y = int(h * self.crop_pad_ratio)
        return cv2.copyMakeBorder(img, pad_y, pad_y, pad_x, pad_x, cv2.BORDER_CONSTANT, value=(114, 114, 114))

    def preprocess_for_ocr(self, img, enhance=False):
        if img is None or img.size == 0:
            return None, None, None, None

        padded_crop = self._pad_crop(img)
        if padded_crop is None:
            return None, None, None, None

        work = padded_crop.copy()
        if enhance:
            gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray = clahe.apply(gray)
            work = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        src_h, src_w = work.shape[:2]
        scale = min(self.input_width / max(1, src_w), self.input_height / max(1, src_h))
        new_w = max(1, int(round(src_w * scale)))
        new_h = max(1, int(round(src_h * scale)))

        resized = cv2.resize(work, (new_w, new_h))
        canvas = np.full((self.input_height, self.input_width, 3), 114, dtype=np.uint8)
        pad_x = (self.input_width - new_w) // 2
        pad_y = (self.input_height - new_h) // 2
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

        img_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        img_normalized = img_rgb.transpose(2, 0, 1).astype(np.float32) / 255.0
        img_batch = np.expand_dims(img_normalized, axis=0)
        meta = {
            'scale': scale,
            'pad_x': pad_x,
            'pad_y': pad_y,
            'src_w': src_w,
            'src_h': src_h,
        }
        return img_batch, img_rgb, meta, padded_crop

    def _decode_class_id(self, cls_id):
        if 0 <= cls_id < len(self.charset):
            return self.charset[cls_id]
        return ""

    def _topk_classes(self, class_scores):
        if class_scores is None or len(class_scores) == 0:
            return []
        topk_indices = np.argsort(class_scores)[-self.debug_topk:][::-1]
        topk = []
        for idx in topk_indices:
            cls_id = int(idx)
            conf = float(class_scores[cls_id])
            cls_char = self._decode_class_id(cls_id)
            if cls_char:
                topk.append((cls_char, conf))
        return topk

    def _extract_candidates(self, boxes, meta, pass_name):
        candidate_boxes = []
        candidate_scores = []
        candidate_cls = []
        candidate_topk = []
        candidate_x_mapped = []

        for box in boxes:
            if len(box) < 5:
                continue

            x, y, w, h = box[:4]
            scores = box[4:]
            if len(scores) == 0:
                continue

            confidence = None
            class_scores = None

            if len(scores) == len(self.charset) + 1:
                objectness = float(scores[0])
                class_scores = scores[1:]
                if len(class_scores) == 0:
                    continue
                cls_id = int(np.argmax(class_scores))
                confidence = objectness * float(class_scores[cls_id])
            elif len(scores) >= len(self.charset):
                class_scores = scores[-len(self.charset):]
                cls_id = int(np.argmax(class_scores))
                confidence = float(class_scores[cls_id])
            else:
                continue

            if confidence < self.conf_threshold:
                continue

            x1 = max(0, int(x - w / 2))
            y1 = max(0, int(y - h / 2))
            x2 = min(self.input_width, int(x + w / 2))
            y2 = min(self.input_height, int(y + h / 2))

            center_x = x1 + max(1, x2 - x1) / 2.0
            mapped_center_x = (center_x - meta['pad_x']) / max(meta['scale'], 1e-6)
            mapped_center_x = float(np.clip(mapped_center_x, 0, max(0, meta['src_w'] - 1)))

            candidate_boxes.append([x1, y1, max(1, x2 - x1), max(1, y2 - y1)])
            candidate_scores.append(confidence)
            candidate_cls.append(cls_id)
            candidate_topk.append(self._topk_classes(class_scores))
            candidate_x_mapped.append(mapped_center_x)

        return {
            'pass_name': pass_name,
            'boxes': candidate_boxes,
            'scores': candidate_scores,
            'cls': candidate_cls,
            'topk': candidate_topk,
            'x_mapped': candidate_x_mapped,
        }

    def _save_debug_images(self, original_crop, resized_rgb, debug_overlay):
        if not self.debug:
            return
        base_name = f"ocr_{self.debug_counter:06d}"
        crop_path = os.path.join(self.debug_save_dir, f"{base_name}_crop.jpg")
        resized_path = os.path.join(self.debug_save_dir, f"{base_name}_resized.jpg")
        overlay_path = os.path.join(self.debug_save_dir, f"{base_name}_overlay.jpg")

        cv2.imwrite(crop_path, original_crop)
        cv2.imwrite(resized_path, cv2.cvtColor(resized_rgb, cv2.COLOR_RGB2BGR))
        cv2.imwrite(overlay_path, debug_overlay)

    def _show_debug_windows(self, original_crop, debug_overlay):
        if not self.debug_show_window:
            return
        cv2.imshow("OCR Debug Crop", original_crop)
        cv2.imshow("OCR Debug Overlay", debug_overlay)
        cv2.waitKey(1)

    def read_plate(self, cropped_img):
        if self.session is None:
            return ""

        self.debug_counter += 1
        blob, resized_rgb, meta, padded_crop = self.preprocess_for_ocr(cropped_img, enhance=False)
        if blob is None:
            return ""

        debug_overlay = cv2.cvtColor(resized_rgb, cv2.COLOR_RGB2BGR)

        all_candidates = []

        try:
            outputs = self.session.run(None, {self.input_name: blob})
            if outputs:
                output = outputs[0][0]
                boxes = output if output.shape[0] > output.shape[1] else output.T
                all_candidates.append(self._extract_candidates(boxes, meta, pass_name='orig'))
        except Exception as e:
            print(f"OCR inference error (orig): {e}")

        if self.second_pass_enhance:
            blob2, _, meta2, _ = self.preprocess_for_ocr(cropped_img, enhance=True)
            if blob2 is not None:
                try:
                    outputs2 = self.session.run(None, {self.input_name: blob2})
                    if outputs2:
                        output2 = outputs2[0][0]
                        boxes2 = output2 if output2.shape[0] > output2.shape[1] else output2.T
                        all_candidates.append(self._extract_candidates(boxes2, meta2, pass_name='enhanced'))
                except Exception as e:
                    print(f"OCR inference error (enhanced): {e}")

        candidate_boxes = []
        candidate_scores = []
        candidate_cls = []
        candidate_topk = []
        candidate_x_mapped = []
        candidate_pass = []

        for bundle in all_candidates:
            candidate_boxes.extend(bundle['boxes'])
            candidate_scores.extend(bundle['scores'])
            candidate_cls.extend(bundle['cls'])
            candidate_topk.extend(bundle['topk'])
            candidate_x_mapped.extend(bundle['x_mapped'])
            candidate_pass.extend([bundle['pass_name']] * len(bundle['boxes']))

        if not candidate_boxes:
            if self.debug:
                print(f"[OCR-DEBUG #{self.debug_counter}] No candidate above threshold {self.conf_threshold}")
                self._save_debug_images(padded_crop, resized_rgb, debug_overlay)
                self._show_debug_windows(padded_crop, debug_overlay)
            return ""

        if self.use_nms:
            indices = cv2.dnn.NMSBoxes(candidate_boxes, candidate_scores, self.conf_threshold, self.nms_iou_threshold)
        else:
            indices = np.arange(len(candidate_boxes)).reshape(-1, 1)

        if len(indices) == 0:
            if self.debug:
                print(f"[OCR-DEBUG #{self.debug_counter}] NMS removed all candidates")
                self._save_debug_images(padded_crop, resized_rgb, debug_overlay)
                self._show_debug_windows(padded_crop, debug_overlay)
            return ""

        flat_indices = indices.flatten() if hasattr(indices, 'flatten') else indices
        debug_lines = []
        chars_raw = []
        for i in flat_indices:
            box = candidate_boxes[int(i)]
            cls_id = candidate_cls[int(i)]
            x1 = float(candidate_x_mapped[int(i)])
            char = self._decode_class_id(cls_id)
            conf = float(candidate_scores[int(i)])
            x, y, w, h = box

            cv2.rectangle(debug_overlay, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(debug_overlay, f"{char}:{conf:.2f}", (x, max(12, y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

            topk_text = ", ".join([f"{c}:{s:.2f}" for c, s in candidate_topk[int(i)]])
            pass_name = candidate_pass[int(i)]
            debug_lines.append(f"idx={int(i):4d} pass={pass_name} box=({x:3d},{y:3d},{w:3d},{h:3d}) pred={char} conf={conf:.3f} x_map={x1:.1f} topk=[{topk_text}]")

            if char:
                chars_raw.append((x1, char, conf))

        if not chars_raw:
            if self.debug:
                print(f"[OCR-DEBUG #{self.debug_counter}] Candidates found but decoded chars empty")
                for line in debug_lines:
                    print(f"[OCR-DEBUG #{self.debug_counter}] {line}")
                self._save_debug_images(padded_crop, resized_rgb, debug_overlay)
                self._show_debug_windows(padded_crop, debug_overlay)
            return ""

        chars_raw.sort(key=lambda item: item[0])
        chars = []
        min_x_gap = 8.0
        for item in chars_raw:
            if not chars:
                chars.append(item)
                continue

            prev_x, prev_char, prev_conf = chars[-1]
            cur_x, cur_char, cur_conf = item
            if abs(cur_x - prev_x) <= min_x_gap:
                if cur_conf > prev_conf:
                    chars[-1] = item
            else:
                chars.append(item)

        raw_text = "".join(char for _, char, _ in chars).upper().replace(" ", "")
        clean_text = re.sub(r'[^A-Z0-9]', '', raw_text)

        if self.debug:
            print(f"[OCR-DEBUG #{self.debug_counter}] raw='{raw_text}' clean='{clean_text}' selected={len(chars)}")
            for line in debug_lines:
                print(f"[OCR-DEBUG #{self.debug_counter}] {line}")
            self._save_debug_images(padded_crop, resized_rgb, debug_overlay)
            self._show_debug_windows(padded_crop, debug_overlay)

        return clean_text

if __name__ == "__main__":
    ocr = PlateOCR('models/best_ocr.onnx')
    img = cv2.imread('test_plate.jpg')
    if img is not None:
        print(f"Plate number: {ocr.read_plate(img)}")
    else:
        print("Test image not found.")
