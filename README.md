# Smart Parking System 🚗

Sistem manajemen parkir otomatis yang menggunakan teknologi **Optical Character Recognition (OCR)** dan **Computer Vision** untuk mendeteksi nomor kendaraan dan mengontrol akses pintu masuk parkir secara otomatis.

## 📋 Daftar Isi
- [Fitur Utama](#fitur-utama)
- [Teknologi yang Digunakan](#teknologi-yang-digunakan)
- [Prasyarat Instalasi](#prasyarat-instalasi)
- [Instalasi](#instalasi)
- [Struktur Proyek](#struktur-proyek)
- [Konfigurasi](#konfigurasi)
- [Cara Penggunaan](#cara-penggunaan)
- [Penjelasan Backend](#penjelasan-backend)
- [Dokumentasi API](#dokumentasi-api)

---

## ✨ Fitur Utama

1. **Deteksi Plat Nomor Real-time**
   - Menggunakan model ONNX untuk deteksi plat kendaraan
   - Pemrosesan video real-time dari kamera
   - Akurasi tinggi dengan confidence threshold yang dapat dikonfigurasi

2. **Optical Character Recognition (OCR)**
   - Ekstraksi teks dari plat nomor yang terdeteksi
   - Menggunakan EasyOCR untuk akurasi maksimal
   - Validasi minimal 5 karakter untuk hasil yang valid

3. **Sistem Kontrol Pintu Otomatis**
   - Komunikasi serial dengan Arduino/microcontroller
   - Perintah OPEN_GATE untuk akses yang diizinkan
   - Perintah DENY_GATE untuk akses yang ditolak
   - Auto-close gate setelah delay yang dapat dikonfigurasi

4. **Backend API**
   - Endpoint untuk verifikasi nomor plat
   - Integrasi database untuk check status kendaraan
   - Response status (ALLOWED/DENIED) dengan pesan

5. **Threading & Multithreading**
   - Background thread untuk deteksi tanpa blocking kamera
   - Shared state management dengan thread-safe locks
   - Real-time display dengan overlay visual

6. **WebSocket Support**
   - Live streaming data detection
   - CORS-enabled API
   - Komunikasi dua arah dengan client

---

## 🛠 Teknologi yang Digunakan

### Backend & Processing
- **Python 3.7+** - Bahasa pemrograman utama
- **Flask** - Web framework untuk API
- **Flask-CORS** - Cross-Origin Resource Sharing
- **Flask-SocketIO** - WebSocket real-time communication
- **OpenCV (cv2)** - Computer vision dan image processing
- **EasyOCR** - Optical Character Recognition
- **ONNX Runtime** - Model inference untuk deteksi plat

### Hardware Communication
- **PySerial** - Komunikasi serial dengan Arduino/microcontroller
- **numpy** - Numerical computing untuk image processing

### Struktur Database
- **SQLite/MySQL** - Untuk penyimpanan data plat nomor yang terdaftar
- **SQL queries** - Query management untuk verifikasi

---

## 📦 Prasyarat Instalasi

Sebelum memulai, pastikan Anda memiliki:

### Hardware Requirements
- **Webcam/IP Camera** - Untuk capture video
- **Arduino/Microcontroller** - Untuk kontrol motor pintu (opsional)
- **PC/Laptop/Raspberry Pi** - Dengan processor yang cukup powerful

### Software Requirements
- **Python 3.7 atau lebih tinggi**
- **pip** - Python package manager
- **OpenCV library**
- **CUDA 11.0+** (opsional, untuk GPU acceleration)

### System Requirements
- **RAM minimal**: 4GB (8GB direkomendasikan)
- **Storage**: 2GB untuk model dan dependencies
-   **RAM minimal**: 4GB (8GB direkomendasikan)
-   **Storage**: 2GB untuk model dan dependencies
-   **Internet connection**: Untuk download library

---

## ⚙️ Instalasi

### 1. Clone Repository
```bash
git clone https://github.com/farissakhi/smart-parking-system.git
cd smart-parking-system
```

### 2. Create Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Additional Dependencies (Tesseract OCR)
Pastikan **Tesseract OCR** terinstall di sistem Anda untuk pembacaan teks plat nomor.
- Download: [Tesseract OCR for Windows](https://github.com/UB-Mannheim/tesseract/wiki)

---

## ⚠️ PENTING: Untuk Kolaborator (Frontend)

Jika Anda mengerjakan bagian Frontend tanpa memegang hardware (ESP32), jangan khawatir:

1.  **Tanpa ESP32**: Backend tetap bisa dijalankan. Abaikan peringatan `WARNING: Could not connect to ESP32`. Pintu gerbang akan disimulasikan lewat log terminal.
2.  **Model AI**: Kamu butuh file `plate_model.onnx` di folder `models/`. Karena file ini >100MB, file ini tidak ada di GitHub. Silakan minta filenya ke owner.
3.  **Database**: Jalankan `database.sql` untuk inisialisasi tabel di SQLite.

---

## 📖 Dokumentasi Detail
Untuk penjelasan lebih mendalam tentang struktur kode dan cara kerja backend, silakan baca:
👉 **[Documentation Guide (docs/README.md)](docs/README.md)**