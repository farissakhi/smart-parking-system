import cv2
import numpy as np
import onnxruntime as ort
import os

class PlateDetector:
    def __init__(self, model_path='models/best_plate.onnx', conf_threshold=0.5):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        
        if not os.path.exists(model_path):
            print(f"WARNING: Model not found at {model_path}. Please download it from HuggingFace.")
            self.session = None
        else:
            # Initialize ONNX Runtime session
            self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
            self.input_name = self.session.get_inputs()[0].name
            self.input_shape = self.session.get_inputs()[0].shape # [batch, channels, height, width]
            
            # Handle dynamic shapes (some ONNX models use strings or None)
            try:
                self.input_height = int(self.input_shape[2])
                self.input_width = int(self.input_shape[3])
            except (ValueError, TypeError):
                self.input_height = 640
                self.input_width = 640
                print(f"Dynamic input shape detected, using default 640x640")

    def preprocess(self, img):
        # Resize image to model input size
        img_resized = cv2.resize(img, (self.input_width, self.input_height))
        # BGR (OpenCV) to RGB
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        # Normalize to 0-1 and change to [channels, height, width]
        img_normalized = img_rgb.transpose(2, 0, 1).astype(np.float32) / 255.0
        # Add batch dimension
        img_batch = np.expand_dims(img_normalized, axis=0)
        return img_batch

    def detect(self, frame):
        if self.session is None:
            return []

        orig_h, orig_w = frame.shape[:2]
        blob = self.preprocess(frame)
        
        # Inference
        outputs = self.session.run(None, {self.input_name: blob})
        output = outputs[0][0]
        
        detections = []
        if output.shape[0] > output.shape[1]: 
             boxes = output
        else:
             boxes = output.T

        for box in boxes:
            confidence = box[4] if len(box) > 4 else 0
            if confidence > self.conf_threshold:
                x, y, w, h = box[:4]
                
                # Rescale to original size
                x1 = int((x - w/2) * orig_w / self.input_width)
                y1 = int((y - h/2) * orig_h / self.input_height)
                x2 = int((x + w/2) * orig_w / self.input_width)
                y2 = int((y + h/2) * orig_h / self.input_height)
                
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(orig_w, x2), min(orig_h, y2)
                
                cropped_plate = frame[y1:y2, x1:x2]
                detections.append({
                    'box': (x1, y1, x2, y2),
                    'confidence': confidence,
                    'crop': cropped_plate
                })
        
        return detections

if __name__ == "__main__":
    detector = PlateDetector()
    cap = cv2.VideoCapture(0)
    while True:
        ret, frame = cap.read()
        if not ret: break
        
        results = detector.detect(frame)
        if results:
            for res in results:
                x1, y1, x2, y2 = res['box']
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.imshow("Crop", res['crop'])
        
        cv2.imshow("Detect", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break
    cap.release()
    cv2.destroyAllWindows()
