import time
import serial
from config import SERIAL_PORT, BAUD_RATE

print("=" * 60)
print("SERVO & BUZZER POWER DIAGNOSTIC TEST")
print("=" * 60)

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
time.sleep(2)

# Clear startup messages
if ser.in_waiting > 0:
    ser.read(ser.in_waiting)

print("\n[QUESTION 1] Apakah buzzer dan servo punya power supply sendiri?")
print("  A. Ya, punya power supply eksternal (5V/12V)")
print("  B. Tidak, ambil dari ESP32 pin")
print("\nAnswer A = Normal (expected)")
print("Answer B = MASALAH! ESP32 GPIO hanya 40mA\n")

print("[TEST 1] Cek servo PWM signal...")
print("Sending: OPEN_GATE")
cmd = '{"cmd": "OPEN_GATE", "plate": "TEST"}\n'
ser.write(cmd.encode())

time.sleep(0.5)
if ser.in_waiting > 0:
    response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
    print(f"Response: {response.strip()}")

print("\nApakah servo bunyi? (vibrate/noise)")
print("  - Bunyi tapi tidak bergerak = POWER LEMAH (masalah #1)")
print("  - Tidak bunyi sama sekali = PIN ERROR atau tidak connected")
print("  - Bergerak normal = OK\n")

time.sleep(6)

print("[TEST 2] Cek buzzer signal...")
print("Sending: BUZZER_ON")
cmd = '{"cmd": "BUZZER_ON", "plate": "TEST"}\n'
ser.write(cmd.encode())

time.sleep(0.5)
if ser.in_waiting > 0:
    response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
    print(f"Response: {response.strip()}")

print("\nApakah buzzer bunyi?")
print("  - Tidak bunyi = POWER LEMAH (masalah #2)")
print("  - Bunyi = OK\n")

time.sleep(1)
print("Sending: BUZZER_OFF")
cmd = '{"cmd": "BUZZER_OFF"}\n'
ser.write(cmd.encode())

ser.close()

print("\n" + "=" * 60)
print("DIAGNOSIS SUMMARY:")
print("=" * 60)
print("\nJika servo bunyi tapi tidak bergerak + buzzer tidak bunyi,")
print("KEMUNGKINAN BESAR: Power supply terlalu lemah!")
print("\nSOLUSI:")
print("1. Gunakan external power supply (5V atau 12V) untuk servo & buzzer")
print("2. Jangan ambil power langsung dari ESP32 GPIO")
print("3. Gunakan MOSFET/Relay untuk switch high-current loads")
print("\nCek file: hardware_wiring.txt untuk diagram koneksi yang benar")
