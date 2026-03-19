# Project Breakdown & Guide 🚧

Dokumentasi ini ditujukan untuk pengembang yang ingin memahami lebih dalam tentang logika di balik Smart Parking System.

## 📁 Struktur File & Folder

### Core Logic
*   **`backend.py`**: Entry point utama untuk Flask server. Mengatur API endpoints dan komunikasi SocketIO dengan Frontend.
*   **`main.py`**: Script utama yang menjalankan deteksi kamera. Menghubungkan kamera, detektor plat, dan komunikasi serial.
*   **`detection.py`**: Menggunakan ONNX Runtime untuk menjalankan model YOLO. Outputnya adalah koordinat kotak (bounding box) plat nomor.
*   **`ocr.py`**: Mengolah gambar plat nomor menjadi teks menggunakan model OCR ONNX (onnxruntime).

### Utilities & Config
*   **`config.py`**: Tempat mengatur variabel global seperti path database, resolusi kamera, dan confidence threshold.
*   **`serial_comm.py`**: Menangani pengiriman data JSON ke ESP32 melalui port Serial.
*   **`database.sql`**: Skema database awal untuk menyimpan data akses kendaraan.

### Assets & Temporary
*   **`models/`**: Tempat menaruh file `.onnx`.
*   **`uploads/`**: Foto hasil capture kendaraan akan disimpan di sini untuk dilihat di Dashboard Admin.

## 🛠 Panduan Pengembangan Frontend

1.  **Endpoints Backend**:
    *   `GET /admin`: Dashboard admin default.
    *   `POST /verify`: Endpoint untuk verifikasi plat.
    *   `WebSocket`: Mengirim event `detection_result` setiap kali ada plat yang terbaca.
2.  **Asset Gambar**:
    *   Setiap kali kendaraan terdeteksi, fotonya disimpan di folder `uploads/` dan linknya dikirim melalui WebSocket.

## 💡 Troubleshooting
*   **Kamera tidak terbuka**: Pastikan tidak ada aplikasi lain (seperti Zoom/Teams) yang sedang menggunakan webcam. Ubah index kamera di `config.py` jika perlu.
*   **Error OCR**: Pastikan file model OCR ONNX tersedia di folder `models/` dan path-nya benar di `config.py`.
