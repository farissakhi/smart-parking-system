import cv2
import time
import requests
import threading
import config
from detection import PlateDetector
from ocr import PlateOCR
from serial_comm import SerialComm

# Shared state between threads
latest_result = {
    'plate': None,
    'box': None,
    'status': None,
    'message': None
}
lock = threading.Lock()

def detection_worker(detector, ocr, comm, frame_holder):
    """Background thread: runs detection + OCR + API without blocking camera."""
    gate_open_time = 0
    is_gate_open = False
    last_detection_time = 0

    while frame_holder['running']:
        current_time = time.time()

        # Auto close gate
        if is_gate_open and (current_time - gate_open_time > config.AUTO_CLOSE_DELAY):
            print("Auto closing gate...")
            comm.send_command("CLOSE_GATE")
            is_gate_open = False
            with lock:
                latest_result['status'] = 'SCANNING'
                latest_result['plate'] = None
                latest_result['box'] = None

        # Skip detection if gate is open or not enough delay
        if is_gate_open or (current_time - last_detection_time < config.DETECT_DELAY):
            time.sleep(0.01)
            continue

        frame = frame_holder.get('frame')
        if frame is None:
            time.sleep(0.01)
            continue

        frame_copy = frame.copy()
        results = detector.detect(frame_copy)

        if results:
            for res in results:
                plate_text = ocr.read_plate(res['crop'])
                if len(plate_text) >= 5:
                    print(f"Detected Plate: {plate_text}")
                    last_detection_time = current_time

                    try:
                        response = requests.post(config.BACKEND_URL, json={'plate_number': plate_text}, timeout=2)
                        data = response.json()
                        status = data.get('status', 'DENIED')
                        message = data.get('message', 'Access Denied')
                        print(f"Backend Response: {status} - {message}")

                        with lock:
                            latest_result['plate'] = plate_text
                            latest_result['box'] = res['box']
                            latest_result['status'] = status
                            latest_result['message'] = message

                        if status == 'ALLOWED':
                            comm.send_command("OPEN_GATE", plate_text, "allowed")
                            is_gate_open = True
                            gate_open_time = current_time
                        else:
                            comm.send_command("DENY_GATE", plate_text, "denied")

                    except Exception as e:
                        print(f"API Error: {e}")
                    break  # Process only the first valid plate per cycle

        time.sleep(0.01)


def main():
    detector = PlateDetector(config.MODEL_PATH, config.CONF_THRESHOLD)
    ocr = PlateOCR()
    comm = SerialComm(config.SERIAL_PORT, config.BAUD_RATE)

    cap = cv2.VideoCapture(config.CAMERA_INDEX)

    frame_holder = {'frame': None, 'running': True}

    # Start detection in background thread
    worker = threading.Thread(target=detection_worker, args=(detector, ocr, comm, frame_holder), daemon=True)
    worker.start()

    print("Starting Smart Parking System...")
    print("Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame")
            break

        # Share a CLEAN copy with detection thread (before drawing overlays)
        frame_holder['frame'] = frame.copy()

        # Draw overlays on a SEPARATE display copy (so detection never sees text)
        display_frame = frame.copy()

        # Draw latest result on display frame (non-blocking)
        with lock:
            if latest_result['box']:
                x1, y1, x2, y2 = latest_result['box']
                color = (0, 255, 0) if latest_result['status'] == 'ALLOWED' else (0, 0, 255)
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
                label = f"{latest_result['plate']} - {latest_result['status']}"
                cv2.putText(display_frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            gate_status = latest_result.get('status', 'CLOSED')
            gate_color = (0, 0, 255) if gate_status == 'ALLOWED' else (0, 255, 0)
            cv2.putText(display_frame, f"Gate: {gate_status or 'SCANNING'}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, gate_color, 2)

        cv2.imshow("Smart Parking Preview", display_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    frame_holder['running'] = False
    cap.release()
    cv2.destroyAllWindows()
    comm.close()

if __name__ == "__main__":
    main()
