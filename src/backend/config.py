import numpy as np
import threading

# --- CONSTANTS ---
FS = 256 # EEG Sample Rate
PPG_FS = 64 # PPG usually lower
ACC_FS = 50 # Accel usually lower
EEG_WIN_LEN = 2 # Seconds
BUFF_SIZE = FS * EEG_WIN_LEN

# Frequency Brackets
brackets = {
    'delta': [0.5, 4],
    'theta': [4, 8],
    'alpha': [8, 13],
    'beta': [13, 30],
    'gamma': [30, 50]
}

# --- GLOBAL STATE ---
# GLOBAL STATE (Thread-Safe Dictionary)
# Use 'with state_lock:' when reading/writing 'state' to prevent race conditions
state_lock = threading.Lock()

state = {
    'focus': 0.5,
    'bpm': 0,
    'posture': 'Good', # Good, Slouch, Distracted
    'iaf': 10.0, # Default Alpha Peak
    'bands': {'delta': 0, 'theta': 0, 'alpha': 0, 'beta': 0, 'gamma': 0},
    'horseshoe': [4, 4, 4, 4], # 4=Disconnected
    'raw_trace': [],
    'connected': False,
    'calibrating': True,
    'recording': False,
    'blink_count': 0,
    'signal_ok': False,
    'hrv': 50,
    'motion_level': 0,
    
    # ARTIFACT TRIGGERS
    'blink': False,       # True if Blink detected (Spike)
    'jaw_clench': False,  # True if Jaw Clench detected (High Freq Noise)
    
    # RAW SENSOR DATA (Real hardware values)
    'raw_eeg': [0.0, 0.0, 0.0, 0.0],  # [TP9, AF7, AF8, TP10] in µV
    'raw_ppg': [0.0, 0.0, 0.0],  # [Ambient, IR, Red]
    'raw_gyro': [0.0, 0.0, 0.0],  # [x, y, z] in deg/s
    'raw_acc': [0.0, 0.0, 0.0],  # [x, y, z] in g
    
    # HRV METRICS
    'rmssd': 0,  # Root Mean Square of Successive Differences (ms)
    'hrv_ready': False,  # True when we have enough data
    
    # FOCUS COMPONENTS (for transparency)
    'focus_components': {
        'eeg_factor': 0.5,
        'hrv_factor': 0.5,
        'stillness_factor': 0.5,
        'mood_factor': 0.5
    }
}

# AI Coach state
coach_state = {
    'last_coaching_time': 0,
    'session_start_time': 0,
    'session_peak_focus': 0,
    'session_focus_sum': 0,
    'session_samples': 0
}

# Buffers
buffers = {
    'eeg': np.zeros((BUFF_SIZE, 4)),
    'ppg': np.zeros((PPG_FS * 10, 3)), # 10s buffer for HR
    'acc': np.zeros((50, 3))
}
indices = {'eeg': 0, 'ppg': 0, 'acc': 0}

# Recording Handle
rec = {'file': None, 'writer': None, 'start': None}

# Calibration Data
calib = {'data': [], 'progress': 0.0, 'baseline_mean': 0.8, 'baseline_std': 0.4}
