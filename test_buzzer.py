import time
from serial_comm import SerialComm
from config import SERIAL_PORT, BAUD_RATE

comm = SerialComm(SERIAL_PORT, BAUD_RATE)
time.sleep(2)

print("\n[TEST 1] BUZZER_ON selama 5 detik...")
comm.send_command("BUZZER_ON")
time.sleep(5)
comm.send_command("BUZZER_OFF")

print("\n[TEST 2] Pola beep lambat 3x (1 detik ON / 1 detik OFF)...")
for i in range(3):
    print(f"  Beep #{i+1}")
    comm.send_command("BUZZER_ON")
    time.sleep(1)
    comm.send_command("BUZZER_OFF")
    time.sleep(1)

print("\nTest selesai.")
print("Kalau masih tidak bunyi: kemungkinan buzzer active-low atau passive (butuh PWM tone).")
comm.close()