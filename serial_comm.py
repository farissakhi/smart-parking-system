import serial
import json
import time
import config
import threading

class SerialComm:
    def __init__(self, port=None, baudrate=None, timeout=1):
        self.port = port or config.SERIAL_PORT
        self.baudrate = baudrate or config.BAUD_RATE
        self.timeout = timeout
        self.ser = None
        self._lock = threading.Lock()
        self.last_distance_cm = None
        self.object_present = None
        self.last_sensor_ts = 0.0
        self.connect()

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            print(f"Connected to ESP32 on {self.port}")
        except Exception as e:
            print(f"WARNING: Could not connect to ESP32 on {self.port}: {e}")
            self.ser = None

    def send_command(self, cmd, plate="UNKNOWN", status="denied", **extra):
        if self.ser and self.ser.is_open:
            data = {
                "cmd": cmd,
                "plate": plate,
                "status": status
            }
            if extra:
                data.update(extra)
            json_cmd = json.dumps(data) + "\n"
            try:
                self.ser.write(json_cmd.encode())
                print(f"Sent to ESP32: {json_cmd.strip()}")
            except Exception as e:
                print(f"[ERROR] Failed to write serial command: {e}")
        else:
            print(f"[LOG] Serial not connected. Command: {cmd} | Plate: {plate} | Status: {status}")

    def _handle_incoming_json(self, payload):
        distance = payload.get("distance_cm")
        object_present = payload.get("object_present")

        if isinstance(distance, (int, float)):
            with self._lock:
                self.last_distance_cm = float(distance)
                self.last_sensor_ts = time.time()

        if isinstance(object_present, bool):
            with self._lock:
                self.object_present = object_present
                self.last_sensor_ts = time.time()

    def update_incoming(self):
        if not (self.ser and self.ser.is_open):
            return

        try:
            while self.ser.in_waiting > 0:
                raw_line = self.ser.readline().decode(errors="ignore").strip()
                if not raw_line:
                    continue

                if raw_line.startswith("{") and raw_line.endswith("}"):
                    try:
                        payload = json.loads(raw_line)
                        self._handle_incoming_json(payload)
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass

    def is_object_present(self, threshold_cm=30.0):
        with self._lock:
            if isinstance(self.object_present, bool):
                return self.object_present
            if isinstance(self.last_distance_cm, (int, float)):
                return self.last_distance_cm <= float(threshold_cm)
            return None

    def has_fresh_sensor(self, max_age_s=2.0):
        with self._lock:
            if self.last_sensor_ts <= 0:
                return False
            return (time.time() - self.last_sensor_ts) <= float(max_age_s)

    def close(self):
        if self.ser:
            self.ser.close()

if __name__ == "__main__":
    comm = SerialComm()
    time.sleep(2)
    comm.send_command("OPEN_GATE", "B1234XYZ", "allowed")
    time.sleep(5)
    comm.send_command("CLOSE_GATE")
    comm.close()
