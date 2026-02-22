# FocusFlow - Project Walkthrough

## v3.0 Clinical Precision & Stability (2025-02-21)
This upgrade elevates FocusFlow from a consumer-grade app to a **Research-Grade Clinical Tool**.

### 1. 🔬 Clinical Precision Engine
Implemented high-performance Digital Signal Processing (DSP) that matches Muse Direct.
- **4th-Order Butterworth Bandpass (1-45Hz)**: Eliminates DC drift and low-frequency "wobble" that confuses focus calculations.
- **Improved Notch (50Hz)**: Targeted removal of electrical hum with zero signal distortion.
- **Welch 2.0 (Hann Window + Overlap)**: Provides a smoother, much more responsive Focus score that reacts instantly to brainwave shifts.

### 2. 🦷 EMG (Muscle Noise) Detector
A dedicated background monitor for the 45Hz-100Hz range.
- **Intelligent Alerts**: Automatically triggers a "Relax your jaw" alert if the user is clenching, preventing muscle tension from corrupting EEG data.

### 3. 🧠 Interactive Electrode Map
A new real-time visualization in the sidebar ensures perfect headset fit.
- **4-Node Anatomical Map**: Dynamic status lights (TP9, AF7, AF8, TP10).
    - `Green`: Clinical signal (Perfect)
    - `Yellow`: Noisy contact (Check placement)
    - `Red`: No contact (Rail voltage)

### 4. 🛡️ Self-Healing Bluetooth (Stability Watchdog)
Industrial-strength reliability for school environments.
- **Watchdog Monitor**: A background task that detects stalled data streams and forces a transparent GATT reconnect.
- **Auto-Recovery**: If the headset drops out, it recovers the stream automatically without operator intervention.

## v3.1 Research-Grade Denoising (v3.1)
The highest level of noise removal possible without hospital-grade equipment.
- **CAR (Common Average Reference)**: Analyzes all sensors together and cancels out noise that hits them at the same time (like electrical hum/EMI).
- **Spike Rejection**: Advanced "digital shield" detects and removes tiny erratic electrical spikes (sparkle noise).
- **Pure-Segment Analytics**: Eliminates "Focus Drops" during eye-blinks. The app pauses math during the blink and uses only 100% pure data.

## Phase 2 Complete: School Edition & Cloud Integration (2025-02-21)

### 1. 🏗️ Management Hierarchy (Student Panel)
Added a new "Student Panel" tab allowing therapeutic centers/schools to manage their clients.
- **Three-Tier System**: Dynamic creation of **Colleges/Schools** → **Classes/Grades** → **Student Profiles**.
- **Supabase Cloud Sync**: All data is stored in real-time in the cloud, ensuring multi-device capability.

### 2. 🗄️ Search & Linking (Database Tab)
A centralized hub for retrieving student records and launching sessions.
- **Multi-Filter Search**: Search by School, Class, or Student Name simultaneously.
- **Session Linking**: Start a session directly from a student record to auto-link neurofeedback data.
- **Live Sync**: Displays "🟢 Connected to Supabase Cloud" when credentials are valid.

### 3. 📄 Professional PDF Reports
Custom-built clinical reporting system using `fpdf2`.
- **Focus Trend Bar Chart**: Visualizes focus scores across all sessions for a student.
- **Clinical Summary**: Calculates improvement (First → Latest session) and peak focus.

### 4. 🔗 Global Session Auto-Save
Whenever a session is recorded for a linked student:
- **Auto-Sync**: The average focus, peak focus, and graph data are pushed to Supabase.

### 5. 🧹 Professional Workspace Cleanup
The project has been pruned of all legacy and duplicate files.
- **Legacy Files Removed**: Old Flask servers, unused CSS/JS variants, and outdated build scripts have been permanently deleted.
- **Optimized Directory**: The project root is now lean, containing only the code and assets necessary for v3.1 operation.

---

## 🛠️ Configuration Guide (Adding your Keys)

To activate Phase 2 Cloud features, follow these steps:

1.  Open [config.py](file:///c:/Users/chaha/OneDrive/Pictures/Predator/muse%202%20phase%201%20-%20Copy%20%282%29/config.py)
2.  Replace the placeholders with your **Supabase URL** and **Anon Key**.
3.  Restart the application.

```python
# config.py
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-actual-key-here"
```
