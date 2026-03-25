import time
import serial
from config import SERIAL_PORT, BAUD_RATE

print(f"Connecting to {SERIAL_PORT} at {BAUD_RATE} baud...")
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
    time.sleep(2)  # Wait for ESP32 to reset
    print("✓ Connected!")
except Exception as e:
    print(f"✗ Failed to connect: {e}")
    exit(1)

# Clear any startup messages
print("\n[STEP 1] Clearing startup messages...")
time.sleep(1)
if ser.in_waiting > 0:
    startup_msg = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
    print(f"Startup message: {startup_msg}")

# Test BUZZER_ON command
print("\n[STEP 2] Sending BUZZER_ON command...")
cmd = '{"cmd": "BUZZER_ON", "plate": "TEST", "status": "denied"}\n'
ser.write(cmd.encode())
print(f"Sent: {cmd.strip()}")

# Wait and read response
time.sleep(1)
if ser.in_waiting > 0:
    response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
    print(f"Response: {response}")
else:
    print("✗ No response from ESP32!")

# Test BUZZER_OFF command
print("\n[STEP 3] Sending BUZZER_OFF command...")
time.sleep(1)
cmd = '{"cmd": "BUZZER_OFF"}\n'
ser.write(cmd.encode())
print(f"Sent: {cmd.strip()}")

time.sleep(1)
if ser.in_waiting > 0:
    response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
    print(f"Response: {response}")
else:
    print("✗ No response from ESP32!")

# Test OPEN_GATE (ini harusnya punya visual feedback dari servo)
print("\n[STEP 4] Sending OPEN_GATE command (check servo movement)...")
time.sleep(1)
cmd = '{"cmd": "OPEN_GATE", "plate": "B2156TOR"}\n'
ser.write(cmd.encode())
print(f"Sent: {cmd.strip()}")

time.sleep(2)
if ser.in_waiting > 0:
    response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
    print(f"Response: {response}")
else:
    print("✗ No response from ESP32!")

ser.close()
print("\n[DONE] Test selesai. Analisis:")
print("- Apakah ada response dari ESP32?")
print("- Apakah buzzer bunyi saat BUZZER_ON?")
print("- Apakah servo bergerak saat OPEN_GATE?")
