
import threading
import time
import os
import csv
import datetime
import logging
import pygame
from flask import Flask, jsonify
from flask_cors import CORS

# v1.1: File Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('focus_flow.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from src.backend.config import state, calib, rec, coach_state, state_lock
from src.backend.core.stream import BeastStreamer

# ... (Previous imports remain, but we only touched lines 370+)
from src.backend.core.processor import processor
# AI Coach Imports
# AI Coach Imports
from src.backend.gamification import gamification
from src.backend.offline_coach import OfflineCoach

# Connection Manager
try:
    from connection_manager import MuseAutopilot
    autopilot = MuseAutopilot()
except ImportError:
    autopilot = None

# App Setup
app = Flask(__name__)
CORS(app)

# --- INIT COACH ---
coach_type = "offline"
coach = OfflineCoach()
voice = None
print("✅ Apps initialized (Offline Mode)")



# --- ROUTES ---
@app.route('/api/focus')
def get_focus():
    with state_lock:
        # Accumulate Session Stats
        if state.get('recording'):
            state['session_focus_sum'] = state.get('session_focus_sum', 0) + state['focus']
            state['session_samples'] = state.get('session_samples', 0) + 1
            
        data = {
            'focus': state['focus'],
            'connected': state['connected'],
            'signal_ok': state['connected'],
            'calibrating': state['calibrating'],
            'progress': calib['progress'],
            'bpm': state['bpm'],
            'hrv': state['hrv'],
            'posture': state['posture'],
            'iaf': state['iaf'],
            'blinks': state['blink_count'],
            'horseshoe': state['horseshoe'],
            'raw': state['raw_trace'],
            'gyro': state.get('gyro', {'x':0, 'y':0, 'z':0}),
            'posture_values': state.get('posture_values', {'pitch':0, 'roll':0}),
            'error': autopilot.last_error if autopilot else ""
        }
    return jsonify(data)

@app.route('/api/connect')
def trigger_connect():
    if not autopilot: return jsonify({'status': 'error'})
    if autopilot.status == "streaming": return jsonify({'status': 'already_connected'})
    threading.Thread(target=autopilot.start_stream, daemon=True).start()
    return jsonify({'status': 'initiated'})

@app.route('/api/calibrate/start')
def start_calib():
    state['calibrating'] = True
    calib['data'] = []
    calib['progress'] = 0.0
    return jsonify({'ok': True})

@app.route('/api/session/start')
def start_rec():
    f = None  # v1.1: Track file handle for cleanup
    try:
        if state['recording']: return jsonify({'status': 'already_recording'})
        
        # Create Recordings Directory
        if not os.path.exists('recordings'):
            os.makedirs('recordings')
            
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"recordings/session_{timestamp}.csv"
        
        # Open File
        f = open(filename, 'w', newline='')
        writer = csv.writer(f)
        
        # Write Generic Header for Multi-Sensor Data
        writer.writerow(['Timestamp', 'Type', 'Ch1', 'Ch2', 'Ch3', 'Ch4', 'Metric'])
        f.flush()  # PHASE 4: Ensure header is written immediately
        
        with state_lock:
            state['recording'] = True
            rec['file'] = f
            rec['writer'] = writer
            state['session_start'] = datetime.datetime.now()
            state['session_focus_sum'] = 0
            state['session_samples'] = 0
            rec['last_flush'] = time.time()  # Track flush timing
            
        logger.info(f"SESSION RECORDING STARTED: {filename}")
        return jsonify({'status': 'started', 'file': filename})
    except Exception as e:
        if f:  # v1.1: Close file handle on error
            f.close()
        logger.error(f"Recording start failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/session/stop')
def stop_rec():
    try:
        if not state['recording']: return jsonify({'status': 'not_recording'})
        
        with state_lock:
            state['recording'] = False
            if rec['file']:
                rec['file'].flush()
                rec['file'].close()
                rec['file'] = None
                rec['writer'] = None
                
        print("💾 SESSION RECORDING SAVED.")
        return jsonify({'status': 'stopped'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# v1.1: Version API
@app.route('/api/version')
def get_version():
    return jsonify({
        'version': '1.1',
        'build_date': '2026-02-08',
        'app_name': 'Focus Flow'
    })

# PHASE 6: Connection Control API
_streamer_instance = None  # Will be injected by launcher

@app.route('/api/system/connect')
def system_connect():
    """Manual trigger for Muse connection"""
    global _streamer_instance
    try:
        if _streamer_instance is None:
            return jsonify({'status': 'error', 'message': 'Streamer not initialized'})
        
        _streamer_instance.start_connection()
        return jsonify({'status': 'scanning', 'message': 'Searching for Muse...'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/system/disconnect')
def system_disconnect():
    """Stop Muse connection"""
    global _streamer_instance
    try:
        if _streamer_instance:
            _streamer_instance.stop_connection()
        return jsonify({'status': 'disconnected'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/system/status')
def system_status():
    """Get connection status"""
    global _streamer_instance
    try:
        if _streamer_instance is None:
            return jsonify({'status': 'idle', 'state': 'not_initialized'})
        
        return jsonify({
            'status': 'ok',
            'connection_state': _streamer_instance.connection_state,
            'backend_connected': state.get('connected', False)
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/session/report')
def get_session_report():
    """Generates a post-session analysis"""
    if 'session_start' not in state:
        return jsonify({'report': "No recent session found. Start a session to generate insights."})
    
    duration = (datetime.datetime.now() - state['session_start']).seconds / 60.0 # Minutes
    avg_focus = (state.get('session_focus_sum', 0) / max(state.get('session_samples', 1), 1)) * 100
    
    stats = {
        'duration_mins': round(duration, 1),
        'avg_focus': round(avg_focus, 1),
        'calm_score': 85, # Placeholder or calc from alpha
        'interruptions': state['blink_count'] # Approximation
    }
    
    # Use the active coach (Gemini or Offline)
    if coach:
        summary = coach.generate_summary(stats)
        return jsonify({'report': summary})
    
    
    if coach:
        summary = coach.generate_summary(stats)
        return jsonify({'report': summary})
    
    return jsonify({'report': "AI Coach not operational."})

@app.route('/api/connect')
def api_connect():
    """Trigger Hardware Connection (Async)"""
    if autopilot:
        if autopilot.status == "connected":
            return jsonify({'status': 'already_connected'})
        
        # Run in thread to prevent blocking the server during Scan
        def background_connect():
            print("🚀 BACKGROUND: Starting Muse Stream...")
            autopilot.start_stream()
            
        threading.Thread(target=background_connect, daemon=True).start()
        return jsonify({'status': 'initiated', 'message': 'Scan started in background'})
    
    return jsonify({'status': 'error', 'message': 'Autopilot not initialized'})

@app.route('/api/disconnect')
def api_disconnect():
    """Stop the Muse Stream"""
    if autopilot:
        autopilot.stop()
        return jsonify({'status': 'disconnected'})
    return jsonify({'status': 'error', 'message': 'No autopilot'})

@app.route('/api/status')
def get_status():
    autopilot_status = "disabled"
    autopilot_error = ""
    return jsonify({
        'connected': state['connected'],
        'signal_ok': state['connected'],
        'calibrated': not state['calibrating'] and calib['baseline_mean'] != 0.8,
        'blinks': state['blink_count'],
        'recording': state['recording'],
        'ai_coach': AI_COACH_AVAILABLE,
        'connection_status': autopilot_status,
        'connection_error': autopilot_error,
        'device_name': autopilot.device_name if autopilot else "Muse Device",
        'battery_level': autopilot.battery_level if autopilot and autopilot.battery_level > 0 else state.get('battery', -1),
        'mental_state': state.get('mental_state', 'Calibrating...'), 
        'firmware': "Virtual Engine v1.1.0",
        # ESSENTIAL DATA LINK
        'focus': round(state.get('focus', 0) * 100), # 0-100
        'bpm': int(state.get('bpm', 0)),
        'hrv': int(state.get('hrv', 50)),
        'bands': state.get('bands', {}),
        'posture_values': state.get('posture_values', {'pitch': 0, 'roll': 0}),
        'artifact_event': state.get('artifact_event', None),
        'fatigue': state.get('fatigue', 0),
        'valence': state.get('valence', 0),
        'coherence': state.get('coherence', 0)
    })

@app.route('/api/raw_data')
def get_raw_data():
    """
    RAW SENSOR DATA ENDPOINT
    Returns unprocessed values directly from Muse hardware
    """
    with state_lock:
        return jsonify({
            'timestamp': time.time(),
            'connected': state['connected'],
            
            # RAW SENSOR VALUES (Real hardware data)
            'eeg': {
                'tp9': state['raw_eeg'][0],  # Left ear (µV)
                'af7': state['raw_eeg'][1],  # Left forehead (µV)
                'af8': state['raw_eeg'][2],  # Right forehead (µV)
                'tp10': state['raw_eeg'][3]  # Right ear (µV)
            },
            'ppg': {
                'ambient': state['raw_ppg'][0],
                'infrared': state['raw_ppg'][1],
                'red': state['raw_ppg'][2]
            },
            'accelerometer': {
                'x': state['raw_acc'][0],  # g
                'y': state['raw_acc'][1],
                'z': state['raw_acc'][2]
            },
            'gyroscope': {
                'x': state['raw_gyro'][0],  # deg/s
                'y': state['raw_gyro'][1],
                'z': state['raw_gyro'][2]
            },
            
            # DERIVED METRICS
            'heart_rate': state['bpm'],
            'hrv_rmssd': state['rmssd'],
            'hrv_ready': state['hrv_ready'],
            'motion_magnitude': state['motion_level'],
            
            # MULTI-MODAL FOCUS COMPONENTS
            'focus_score': state['focus'],
            'focus_components': state['focus_components'],
            
            # EEG BANDS
            'bands': state['bands']
        })


# === AI COACH ROUTES ===
@app.route('/api/coach/insight')
def get_coach_insight():
    if not AI_COACH_AVAILABLE or not coach:
        return jsonify({'message': 'AI Coach dormant.', 'active': False})
    
    with state_lock:
        # Get live metrics
        focus = state['focus']
        bpm = state['bpm']
        posture = state['posture']
        iaf = state['iaf']
        hrv = state.get('hrv', 50)
        # Extract alpha power safely
        alpha = state['bands'].get('alpha', 0.5) if state.get('bands') else 0.5
        
    try:
        # Ask Gemini (or Offline Rule Engine)
        advice = coach.get_guidance(focus, alpha, bpm, posture, iaf, hrv)
        
        # Determine if we should speak it (TTS)
        should_speak = False
        if voice and state.get('audio_enabled', False):
             # Only speak if message is urgent or infrequent?
             # For now, let frontend trigger speech or handle it there.
             # Actually, Python backend has the pyttsx3 voice engine.
             # voice.speak(advice) # Let's keep it silent text for now unless requested
             pass

        return jsonify({'message': advice, 'active': True})
    except Exception as e:
        return jsonify({'error': str(e), 'active': False})

# === CALIBRATION ROUTES ===
@app.route('/api/calibrate/start', methods=['POST'])
def start_calibration():
    with state_lock:
        state['calibrating'] = True
        state['calibration_buffer'] = []
    return jsonify({'status': 'started'})

@app.route('/api/calibrate/status')
def calibration_status():
    with state_lock:
        progress = 0
        if 'calibration_buffer' in state:
            progress = min(100, int((len(state['calibration_buffer']) / 600) * 100))
        done = not state.get('calibrating', False) and progress >= 100
        
    return jsonify({'progress': progress, 'done': done})

@app.route('/api/calibrate/cancel', methods=['POST'])
def cancel_calibration():
    with state_lock:
        state['calibrating'] = False
        state['calibration_buffer'] = []
    return jsonify({'status': 'cancelled'})

# === GAMIFICATION ROUTES ===
@app.route('/api/gamification/stats')
def get_gamification_stats():
    """Get user statistics and achievements"""
    return jsonify(gamification.get_stats())

@app.route('/api/history')
def get_history():
    """Get raw session logs for Analytics"""
    return jsonify({'history': gamification.get_history()})

# === SETTINGS ROUTES ===
CONFIG_FILE = 'config.json'
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f: return json.load(f)
    return {'notch_freq': 50, 'audio_volume': 50, 'sensitivity': 50}

def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f: json.dump(cfg, f)

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    from flask import request
    if request.method == 'GET':
        return jsonify(load_config())
    
    # POST
    data = request.json
    cfg = load_config()
    cfg.update(data)
    save_config(cfg)
    
    # Apply Settings immediately
    # (In a real app, we'd update the running Processor instance here)
    print(f"⚙️ SETTINGS UPDATED: {cfg}")
    return jsonify({'success': True, 'config': cfg})

@app.route('/api/gamification/record', methods=['POST'])
def record_gamification_session():
    """Record session completion"""
    from flask import request
    data = request.json
    duration = data.get('duration', 0)
    avg_focus = data.get('avg_focus', 0)
    peak_focus = data.get('peak_focus', 0)
    new_achievements = gamification.record_session(duration, avg_focus, peak_focus)
    return jsonify({'new_achievements': new_achievements})

# === BLUETOOTH ROUTES ===
from src.backend.bluetooth_manager import scan_for_muse, connect_to_muse, get_battery

@app.route('/api/bluetooth/scan')
def bluetooth_scan():
    """Scan for Muse devices"""
    devices = scan_for_muse()
    return jsonify({'devices': devices})

@app.route('/api/bluetooth/connect', methods=['POST'])
def bluetooth_connect():
    """Connect to a Muse device"""
    from flask import request
    address = request.json.get('address')
    success = connect_to_muse(address)
    return jsonify({'success': success})

@app.route('/api/bluetooth/battery')
def bluetooth_battery():
    """Get battery level"""
    battery = get_battery()
    return jsonify({'battery': battery if battery is not None else -1})


# === OSC BROADCASTER ===
try:
    from pythonosc import udp_client
    osc_client = udp_client.SimpleUDPClient("127.0.0.1", 5000)
    OSC_AVAILABLE = True
    print("✅ OSC Streaming Active on 127.0.0.1:5000")
except ImportError:
    OSC_AVAILABLE = False
    print("⚠️ OSC Disabled (pip install python-osc)")

def osc_worker():
    """Background thread to broadcast data"""
    while True:
        if OSC_AVAILABLE and state['connected']:
            try:
                # Broadcast EEG
                for band, power in state['bands'].items():
                    osc_client.send_message(f"/muse/elements/{band}_absolute", power)
                
                # Broadcast Focus/State
                osc_client.send_message("/muse/focus", state['focus'])
                osc_client.send_message("/muse/bpm", float(state['bpm']))
                
                # Broadcast Motion
                if 'gyro' in state:
                    osc_client.send_message("/muse/gyro/x", state['gyro']['x'])
                    osc_client.send_message("/muse/gyro/y", state['gyro']['y'])
                    osc_client.send_message("/muse/gyro/z", state['gyro']['z'])
                
                if 'posture_values' in state:
                    osc_client.send_message("/muse/acc/pitch", state['posture_values']['pitch'])
                    osc_client.send_message("/muse/acc/roll", state['posture_values']['roll'])

            except: pass
        time.sleep(0.05) # 20Hz update rate

# Start OSC Thread
if OSC_AVAILABLE:
    threading.Thread(target=osc_worker, daemon=True).start()


if __name__ == "__main__":
    # Start Beast Engine
    t = BeastStreamer()
    t.start()
    
    # Medical Safe-Shutdown
    import atexit
    def cleanup():
        print("🛑 STOPPING BEAST (Medical Safe-Shutdown)...")
        t.stop()
        t.join(timeout=1)
        if autopilot: autopilot.stop_stream()
        print("✅ Shutdown Complete.")
def start_server():
    """Entry point for the monolithic launcher"""
    atexit.register(cleanup)
    # Start Flask
    port = int(os.environ.get('PORT', 5001))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)).start()
    
    print(f"\n🚀 SENSOR LINK ACTIVE on http://localhost:{port}")
    print("   (Medical Core Online)")
    
    print("🚀 ENTERPRISE SERVER STARTED (HEADLESS)")
    
    # Start Muse Streamer
    # Allow imports to work
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    print("🚀 Starting Backend Server on Port 5001...")
    
    # Run server without threading first to test
    # Re-enable debug=True for better error visibility if needed, but False for production
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    start_server()
