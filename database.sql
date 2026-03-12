-- Schema Database untuk Smart Parking System
-- Menyimpan daftar kendaraan terdaftar, log akses, dan kapasitas parkir

CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate_number TEXT UNIQUE NOT NULL,
    vehicle_type TEXT DEFAULT 'Car',
    is_active INTEGER DEFAULT 1, -- 1: Aktif, 0: Diblokir
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS access_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate_number TEXT NOT NULL,
    action TEXT NOT NULL, -- 'ENTRY' atau 'EXIT'
    status TEXT NOT NULL, -- 'ALLOWED' atau 'DENIED'
    image_path TEXT, -- Path ke foto plat saat deteksi
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parking_capacity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    total_slots INTEGER DEFAULT 20,
    occupied_slots INTEGER DEFAULT 0
);

-- Insert default capacity
INSERT INTO parking_capacity (total_slots, occupied_slots) VALUES (20, 0);
