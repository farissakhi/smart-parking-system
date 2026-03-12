import serial
import json
import time

class SerialComm:
    def __init__(self, port='COM8', baudrate=115200, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.connect()

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            print(f"Connected to ESP32 on {self.port}")
        except Exception as e:
            print(f"WARNING: Could not connect to ESP32 on {self.port}: {e}")
            self.ser = None

    def send_command(self, cmd, plate="UNKNOWN", status="denied"):
        if self.ser and self.ser.is_open:
            data = {
                "cmd": cmd,
                "plate": plate,
                "status": status
            }
            json_cmd = json.dumps(data) + "\n"
            self.ser.write(json_cmd.encode())
            print(f"Sent to ESP32: {json_cmd.strip()}")
        else:
            print(f"[LOG] Serial not connected. Command: {cmd} | Plate: {plate} | Status: {status}")

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
