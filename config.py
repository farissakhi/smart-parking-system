import os

# Configuration for Smart Parking System

# Camera Settings
CAMERA_INDEX = 0  # 0 for default webcam, or RTSP URL for IP Camera

# Serial Settings (Arduino/ESP32)
SERIAL_PORT = 'COM8'  # Windows: 'COM3', Linux: '/dev/ttyUSB0'
BAUD_RATE = 115200

# Detection Settings
MODEL_PATH = 'models/plate_model.onnx'
CONF_THRESHOLD = 0.4
DETECT_DELAY = 0.1  # Seconds to wait between detections (ultra-fast mode)

# API Settings
BACKEND_URL = 'http://localhost:5000/api/check-plate'

# Gate Settings
AUTO_CLOSE_DELAY = 5.0  # Seconds the gate stays open
