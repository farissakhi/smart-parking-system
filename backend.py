from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import sqlite3
import datetime
import os

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

DB_PATH = 'parking_system.db'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ============================================================
# Database Helpers
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database. Deletes old DB if schema changed."""
    need_init = not os.path.exists(DB_PATH)

    if not need_init:
        # Check if schema is up-to-date (parking_capacity table exists)
        try:
            conn = get_db()
            conn.execute('SELECT * FROM parking_capacity LIMIT 1')
            conn.close()
        except sqlite3.OperationalError:
            print("Schema outdated. Re-initializing database...")
            conn.close()
            os.remove(DB_PATH)
            need_init = True

    if need_init:
        print("Initializing database...")
        with open('database.sql', 'r') as f:
            schema = f.read()
        conn = get_db()
        conn.executescript(schema)
        conn.commit()
        conn.close()
        print("Database initialized successfully.")

    # Migration: Add is_inside to vehicles if missing
    conn = get_db()
    try:
        conn.execute('SELECT is_inside FROM vehicles LIMIT 1')
    except sqlite3.OperationalError:
        print("Migrating: Adding is_inside column to vehicles...")
        conn.execute('ALTER TABLE vehicles ADD COLUMN is_inside INTEGER DEFAULT 0')
        conn.commit()
    conn.close()

def get_capacity():
    conn = get_db()
    cap = conn.execute('SELECT * FROM parking_capacity LIMIT 1').fetchone()
    conn.close()
    return dict(cap) if cap else {'total_slots': 20, 'occupied_slots': 0}

# ============================================================
# Admin Page
# ============================================================

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

# ============================================================
# Vehicle CRUD
# ============================================================

@app.route('/api/vehicles', methods=['GET'])
def list_vehicles():
    conn = get_db()
    vehicles = conn.execute('SELECT * FROM vehicles ORDER BY created_at DESC').fetchall()
    conn.close()
    return jsonify([dict(v) for v in vehicles])

@app.route('/api/vehicles', methods=['POST'])
def register_vehicle():
    data = request.json
    plate = data.get('plate_number', '').replace(' ', '').upper()
    v_type = data.get('vehicle_type', 'Car')

    if not plate:
        return jsonify({'status': 'error', 'message': 'Plate number is required'}), 400

    try:
        conn = get_db()
        conn.execute('INSERT INTO vehicles (plate_number, vehicle_type) VALUES (?, ?)', (plate, v_type))
        conn.commit()
        conn.close()

        # Notify connected clients
        socketio.emit('vehicle_update', {'action': 'added', 'plate': plate})

        return jsonify({'status': 'success', 'message': f'Vehicle {plate} registered successfully'})
    except sqlite3.IntegrityError:
        return jsonify({'status': 'error', 'message': 'Vehicle already registered'}), 400

@app.route('/api/vehicles/<int:vehicle_id>', methods=['PUT'])
def update_vehicle(vehicle_id):
    data = request.json
    plate = data.get('plate_number', '').replace(' ', '').upper()
    v_type = data.get('vehicle_type')

    if not plate:
        return jsonify({'status': 'error', 'message': 'Plate number is required'}), 400

    conn = get_db()
    vehicle = conn.execute('SELECT * FROM vehicles WHERE id = ?', (vehicle_id,)).fetchone()
    if not vehicle:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Vehicle not found'}), 404

    try:
        conn.execute('UPDATE vehicles SET plate_number = ?, vehicle_type = ? WHERE id = ?',
                      (plate, v_type or vehicle['vehicle_type'], vehicle_id))
        conn.commit()
        conn.close()
        socketio.emit('vehicle_update', {'action': 'updated', 'plate': plate})
        return jsonify({'status': 'success', 'message': f'Vehicle {plate} updated'})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Plate number already exists'}), 400

@app.route('/api/vehicles/<int:vehicle_id>', methods=['DELETE'])
def delete_vehicle(vehicle_id):
    conn = get_db()
    vehicle = conn.execute('SELECT * FROM vehicles WHERE id = ?', (vehicle_id,)).fetchone()
    if not vehicle:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Vehicle not found'}), 404

    conn.execute('DELETE FROM vehicles WHERE id = ?', (vehicle_id,))
    conn.commit()
    conn.close()
    socketio.emit('vehicle_update', {'action': 'deleted', 'id': vehicle_id})
    return jsonify({'status': 'success', 'message': 'Vehicle deleted'})

@app.route('/api/vehicles/<int:vehicle_id>/toggle', methods=['POST'])
def toggle_vehicle(vehicle_id):
    conn = get_db()
    vehicle = conn.execute('SELECT * FROM vehicles WHERE id = ?', (vehicle_id,)).fetchone()
    if not vehicle:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Vehicle not found'}), 404

    new_status = 0 if vehicle['is_active'] else 1
    conn.execute('UPDATE vehicles SET is_active = ? WHERE id = ?', (new_status, vehicle_id))
    conn.commit()
    conn.close()

    label = 'activated' if new_status else 'blocked'
    socketio.emit('vehicle_update', {'action': label, 'plate': vehicle['plate_number']})
    return jsonify({'status': 'success', 'message': f"Vehicle {vehicle['plate_number']} {label}"})

# ============================================================
# Plate Check (called by main.py / camera system)
# ============================================================

@app.route('/api/check-plate', methods=['POST'])
def check_plate():
    data = request.json
    plate_number = data.get('plate_number', '').replace(' ', '').upper()

    if not plate_number:
        return jsonify({'status': 'error', 'message': 'No plate number provided'}), 400

    conn = get_db()
    vehicle = conn.execute('SELECT * FROM vehicles WHERE plate_number = ? AND is_active = 1', (plate_number,)).fetchone()

    # Check capacity
    capacity = conn.execute('SELECT * FROM parking_capacity LIMIT 1').fetchone()
    is_full = capacity and capacity['occupied_slots'] >= capacity['total_slots']

    action = 'ENTRY' # Default

    if vehicle and not is_full:
        action = 'EXIT' if vehicle['is_inside'] else 'ENTRY'
        status = 'ALLOWED'
        message = f"{action} Granted: {plate_number}"
    elif vehicle and is_full:
        status = 'DENIED'
        message = 'Parking Full'
    else:
        status = 'DENIED'
        message = 'Access Denied: Unregistered Vehicle'

    # Log the access attempt
    conn.execute('INSERT INTO access_logs (plate_number, action, status) VALUES (?, ?, ?)',
                 (plate_number, action, status))
    conn.commit()

    # Get updated capacity
    cap = conn.execute('SELECT * FROM parking_capacity LIMIT 1').fetchone()
    conn.close()

    result = {
        'status': status,
        'message': message,
        'plate': plate_number,
        'action': action
    }

    # Real-time push to all connected dashboards
    socketio.emit('plate_detected', {
        **result,
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

    return jsonify(result)

# ============================================================
# Access Logs
# ============================================================

@app.route('/api/logs', methods=['GET'])
def list_logs():
    conn = get_db()
    logs = conn.execute('SELECT * FROM access_logs ORDER BY timestamp DESC LIMIT 100').fetchall()
    conn.close()
    return jsonify([dict(l) for l in logs])

@app.route('/api/logs/stats', methods=['GET'])
def get_log_stats():
    conn = get_db()
    stats = conn.execute('''
        SELECT strftime('%H', timestamp) as hour, COUNT(*) as count 
        FROM access_logs 
        WHERE status = 'ALLOWED' 
        GROUP BY hour 
        ORDER BY hour
    ''').fetchall()
    conn.close()
    return jsonify([dict(s) for s in stats])

# ============================================================
# Parking Capacity
# ============================================================

@app.route('/api/occupancy/increment', methods=['POST'])
def increment_occupancy():
    conn = get_db()
    conn.execute('UPDATE parking_capacity SET occupied_slots = occupied_slots + 1 WHERE id = 1')
    conn.commit()
    cap = conn.execute('SELECT * FROM parking_capacity LIMIT 1').fetchone()
    conn.close()
    socketio.emit('capacity_update', dict(cap))
    return jsonify({'status': 'success', **dict(cap)})

@app.route('/api/occupancy/decrement', methods=['POST'])
def decrement_occupancy():
    conn = get_db()
    conn.execute('UPDATE parking_capacity SET occupied_slots = CASE WHEN occupied_slots > 0 THEN occupied_slots - 1 ELSE 0 END WHERE id = 1')
    conn.commit()
    cap = conn.execute('SELECT * FROM parking_capacity LIMIT 1').fetchone()
    conn.close()
    socketio.emit('capacity_update', dict(cap))
    return jsonify({'status': 'success', **dict(cap)})

@app.route('/api/occupancy/confirm-passage', methods=['POST'])
def confirm_passage():
    data = request.json
    plate = data.get('plate_number')
    if not plate:
        return jsonify({'status': 'error', 'message': 'Missing plate'}), 400
        
    conn = get_db()
    vehicle = conn.execute('SELECT * FROM vehicles WHERE plate_number = ?', (plate,)).fetchone()
    if not vehicle:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Vehicle not found'}), 404
        
    # Toggle logic
    is_entering = not vehicle['is_inside']
    new_status = 1 if is_entering else 0
    action = 'ENTRY' if is_entering else 'EXIT'
    
    conn.execute('UPDATE vehicles SET is_inside = ? WHERE plate_number = ?', (new_status, plate))
    
    if is_entering:
        conn.execute('UPDATE parking_capacity SET occupied_slots = occupied_slots + 1 WHERE id = 1')
    else:
        conn.execute('UPDATE parking_capacity SET occupied_slots = CASE WHEN occupied_slots > 0 THEN occupied_slots - 1 ELSE 0 END WHERE id = 1')
        
    conn.commit()
    cap = conn.execute('SELECT * FROM parking_capacity LIMIT 1').fetchone()
    conn.close()
    
    socketio.emit('capacity_update', dict(cap))
    socketio.emit('vehicle_update', {'action': 'status_change', 'plate': plate, 'is_inside': new_status})
    
    return jsonify({'status': 'success', 'action': action, 'is_inside': new_status, **dict(cap)})

@app.route('/api/capacity', methods=['GET'])
def get_parking_capacity():
    return jsonify(get_capacity())

@app.route('/api/capacity', methods=['PUT'])
def update_capacity():
    data = request.json
    total = data.get('total_slots')
    occupied = data.get('occupied_slots')

    conn = get_db()
    cap = conn.execute('SELECT * FROM parking_capacity LIMIT 1').fetchone()

    new_total = total if total is not None else cap['total_slots']
    new_occupied = occupied if occupied is not None else cap['occupied_slots']

    conn.execute('UPDATE parking_capacity SET total_slots = ?, occupied_slots = ? WHERE id = 1',
                 (new_total, new_occupied))
    conn.commit()

    updated = conn.execute('SELECT * FROM parking_capacity LIMIT 1').fetchone()
    conn.close()

    socketio.emit('capacity_update', dict(updated))
    return jsonify({'status': 'success', **dict(updated)})

# ============================================================
# Manual Gate Control
# ============================================================

@app.route('/api/gate/open', methods=['POST'])
def gate_open():
    socketio.emit('gate_command', {'action': 'OPEN'})
    return jsonify({'status': 'success', 'message': 'Gate opened manually'})

@app.route('/api/gate/close', methods=['POST'])
def gate_close():
    socketio.emit('gate_command', {'action': 'CLOSE'})
    return jsonify({'status': 'success', 'message': 'Gate closed manually'})

# ============================================================
# SocketIO Events
# ============================================================

@socketio.on('connect')
def handle_connect():
    print('Client connected to dashboard')
    emit('capacity_update', get_capacity())

# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    init_db()
    print("=" * 50)
    print("  Smart Parking System - Backend")
    print("  Admin Dashboard: http://localhost:5000/admin")
    print("=" * 50)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
