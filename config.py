import os

# Configuration for Smart Parking System

# Camera Settings
CAMERA_INDEX = 0  # 0 for default webcam, or RTSP URL for IP Camera

# Serial Settings (Arduino/ESP32)
SERIAL_PORT = 'COM7'  # Windows: 'COM3', Linux: '/dev/ttyUSB0'
BAUD_RATE = 115200

# Detection Settings
MODEL_PATH = 'models/best_plate.onnx'
CONF_THRESHOLD = 0.4
DETECT_DELAY = 0.1  # Seconds to wait between detections (ultra-fast mode)

OCR_MODEL_PATH = 'models/best_ocr.onnx'
OCR_CONF_THRESHOLD = 0.5
OCR_CHARSET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
OCR_CROP_PAD_RATIO = 0.15
OCR_USE_NMS = True
OCR_NMS_IOU_THRESHOLD = 0.80
OCR_SECOND_PASS_ENHANCE = True

# OCR debug profile (default OFF)
OCR_DEBUG_PROFILE = {}
# Uncomment this single line to enable OCR debug:
# OCR_DEBUG_PROFILE = {'debug': True, 'debug_show_window': False, 'debug_save_dir': 'debug/ocr', 'debug_topk': 5}

# API Settings
BACKEND_URL = 'http://localhost:5000/api/check-plate'

# Gate Settings
AUTO_CLOSE_DELAY = 5.0  # Seconds the gate stays open

# Buzzer Settings
BUZZER_ENABLED = True
BUZZER_ON_DENIED = True
BUZZER_ON_ALLOWED = False
BUZZER_BEEP_DURATION = 0.35  # Seconds
