import cv2
import time
import requests
import threading
import config
import json
import socketio
from flask import Flask, Response
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
stream_frame = None
lock = threading.Lock()

def detection_worker(detector, ocr, comm, frame_holder):
    """Background thread: runs detection + OCR + API without blocking camera."""
    gate_open_time = 0
    is_gate_open = False
    clear_since_time = None
    last_detection_time = 0
    buzzer_off_time = 0
    is_buzzer_on = False
    waiting_for_passage = None # Stores the plate currently passing

    def trigger_buzzer(current_time, plate="UNKNOWN", status="denied"):
        nonlocal is_buzzer_on, buzzer_off_time
        if not config.BUZZER_ENABLED:
            return
        # Go back to a simple command to match working test_buzzer.py
        comm.send_command("BUZZER_ON")
        is_buzzer_on = True
        # Use fresh time to avoid race condition with slow OCR processing
        buzzer_off_time = time.time() + float(config.BUZZER_BEEP_DURATION)

    while frame_holder['running']:
        current_time = time.time()
        comm.update_incoming()

        if is_buzzer_on and current_time >= buzzer_off_time:
            comm.send_command("BUZZER_OFF")
            is_buzzer_on = False

        # Auto close gate (only close when area is clear if ultrasonic gate is enabled)
        if is_gate_open and (current_time - gate_open_time > config.AUTO_CLOSE_DELAY):
            should_close = True

            if getattr(config, 'ULTRASONIC_GATE_ENABLED', False) and getattr(config, 'GATE_CLOSE_REQUIRE_CLEAR_OBJECT', True):
                has_fresh_sensor = comm.has_fresh_sensor(getattr(config, 'ULTRASONIC_SENSOR_MAX_AGE_S', 2.0))
                object_present = comm.is_object_present(getattr(config, 'ULTRASONIC_TRIGGER_DISTANCE_CM', 35.0))

                if has_fresh_sensor and object_present is False:
                    if clear_since_time is None:
                        clear_since_time = current_time
                    clear_duration = current_time - clear_since_time
                    
                    # Verify passage (toggle status) if not already done
                    if waiting_for_passage and clear_duration >= 0.5:
                        try:
                            requests.post(config.CONFIRM_URL, json={'plate_number': waiting_for_passage}, timeout=1)
                            print(f"Passage confirmed for {waiting_for_passage}. Status toggled.")
                            waiting_for_passage = None
                        except Exception as e:
                            print(f"Failed to confirm passage: {e}")

                    should_close = clear_duration >= float(getattr(config, 'GATE_CLOSE_CLEAR_HOLD_S', 0.5))
                else:
                    clear_since_time = None
                    should_close = False

            if should_close:
                print("Auto closing gate...")
                comm.send_command("CLOSE_GATE")
                is_gate_open = False
                clear_since_time = None
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

        if getattr(config, 'ULTRASONIC_GATE_ENABLED', False):
            has_fresh_sensor = comm.has_fresh_sensor(getattr(config, 'ULTRASONIC_SENSOR_MAX_AGE_S', 2.0))
            object_present = comm.is_object_present(getattr(config, 'ULTRASONIC_TRIGGER_DISTANCE_CM', 35.0))
            fail_open = bool(getattr(config, 'ULTRASONIC_FAIL_OPEN', True))

            if has_fresh_sensor and object_present is False:
                time.sleep(0.01)
                continue

            if (not has_fresh_sensor) and (not fail_open):
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
                            if config.BUZZER_ON_ALLOWED:
                                trigger_buzzer(current_time, plate=plate_text, status="allowed")
                            is_gate_open = True
                            waiting_for_passage = plate_text
                            gate_open_time = current_time
                            clear_since_time = None
                        else:
                            comm.send_command("DENY_GATE", plate_text, "denied")
                            if config.BUZZER_ON_DENIED:
                                trigger_buzzer(current_time, plate=plate_text, status="denied")

                    except Exception as e:
                        print(f"API Error: {e}")
                    break  # Process only the first valid plate per cycle

        time.sleep(0.01)


def setup_socket(comm):
    """Initialize Socket.IO client to listen for manual gate commands."""
    sio = socketio.Client()

    @sio.on('gate_command')
    def on_gate_command(data):
        action = data.get('action')
        print(f"Manual Gate Command received: {action}")
        if action == 'OPEN':
            comm.send_command("OPEN_GATE", "MANUAL", "allowed")
        elif action == 'CLOSE':
            comm.send_command("CLOSE_GATE", "MANUAL", "denied")

    @sio.on('hardware_test')
    def on_hardware_test(data):
        component = data.get('component')
        print(f"Hardware Test Command: {component}")
        result = {'component': component, 'success': False, 'message': ''}

        try:
            if component == 'SERVO':
                comm.send_command("OPEN_GATE", "TEST", "allowed")
                time.sleep(3)
                comm.send_command("CLOSE_GATE", "TEST", "denied")
                result['success'] = True
                result['message'] = 'Gate opened and closed successfully'

            elif component == 'BUZZER':
                comm.send_command("BUZZER_ON")
                time.sleep(config.BUZZER_BEEP_DURATION)
                comm.send_command("BUZZER_OFF")
                result['success'] = True
                result['message'] = f'Buzzer beeped for {config.BUZZER_BEEP_DURATION}s'

            elif component.startswith('LED_'):
                color = component.replace('LED_', '').lower()
                comm.send_command(f"LED_{color.upper()}_ON")
                time.sleep(3)
                comm.send_command(f"LED_{color.upper()}_OFF")
                result['success'] = True
                result['message'] = f'{color.capitalize()} LED toggled for 3s'

            elif component == 'ULTRASONIC':
                comm.update_incoming()
                dist = comm.last_distance_cm
                present = comm.is_object_present()
                result['success'] = dist is not None
                result['message'] = f'Distance: {dist:.1f}cm, Object: {present}' if dist else 'No sensor data'
                result['distance'] = dist
                result['object_present'] = present

            else:
                result['message'] = f'Unknown component: {component}'

        except Exception as e:
            result['message'] = f'Error: {str(e)}'

        sio.emit('hardware_result', result)

    @sio.event
    def connect():
        print("Connected to Backend Socket Server")

    @sio.event
    def disconnect():
        print("Disconnected from Backend Socket Server")

    try:
        sio.connect(config.SOCKET_SERVER_URL)
        return sio
    except Exception as e:
        print(f"Warning: Could not connect to Socket server: {e}")
        return None

# ============================================================
# Video Streaming Server
# ============================================================
app = Flask(__name__)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

def gen_frames():
    while True:
        with lock:
            if stream_frame is None:
                time.sleep(0.1)
                continue
            ret, buffer = cv2.imencode('.jpg', stream_frame)
            if not ret:
                continue
            frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.04) # Limit to ~25 FPS

def flask_worker():
    app.run(host='0.0.0.0', port=config.STREAM_PORT, debug=False, use_reloader=False)

def main():
    detector = PlateDetector(config.MODEL_PATH, config.CONF_THRESHOLD)

    # OCR debug can be enabled by uncommenting one line in config.py (OCR_DEBUG_PROFILE)
    ocr_debug_profile = getattr(config, 'OCR_DEBUG_PROFILE', {})

    ocr = PlateOCR(
        model_path=config.OCR_MODEL_PATH,
        conf_threshold=config.OCR_CONF_THRESHOLD,
        charset=config.OCR_CHARSET,
        crop_pad_ratio=config.OCR_CROP_PAD_RATIO,
        use_nms=config.OCR_USE_NMS,
        nms_iou_threshold=config.OCR_NMS_IOU_THRESHOLD,
        second_pass_enhance=config.OCR_SECOND_PASS_ENHANCE,
        **ocr_debug_profile,
    )
    comm = SerialComm(config.SERIAL_PORT, config.BAUD_RATE)

    # Setup Socket.IO for manual controls
    sio = setup_socket(comm)

    cap = cv2.VideoCapture(config.CAMERA_INDEX)

    frame_holder = {'frame': None, 'running': True}

    # Start detection in background thread
    worker = threading.Thread(target=detection_worker, args=(detector, ocr, comm, frame_holder), daemon=True)
    worker.start()

    # Start MJPEG stream in background thread
    stream_thread = threading.Thread(target=flask_worker, daemon=True)
    stream_thread.start()

    # Start heartbeat thread (reports system health to backend)
    def heartbeat_worker():
        while frame_holder['running']:
            if sio and sio.connected:
                comm.update_incoming()
                sio.emit('iot_heartbeat', {
                    'serial_port': config.SERIAL_PORT,
                    'serial_connected': comm.ser is not None and comm.ser.is_open,
                    'ultrasonic_distance': comm.last_distance_cm,
                    'object_present': comm.is_object_present(),
                })
            time.sleep(3)

    hb_thread = threading.Thread(target=heartbeat_worker, daemon=True)
    hb_thread.start()

    print("Starting Smart Parking System...")
    print(f"Buzzer Config: ENABLED={config.BUZZER_ENABLED}, ALLOWED={config.BUZZER_ON_ALLOWED}, DENIED={config.BUZZER_ON_DENIED}")
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
            
            global stream_frame
            stream_frame = display_frame.copy()

        cv2.imshow("Smart Parking Preview", display_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    frame_holder['running'] = False
    if sio and sio.connected:
        sio.disconnect()
    cap.release()
    cv2.destroyAllWindows()
    comm.close()

if __name__ == "__main__":
    main()
