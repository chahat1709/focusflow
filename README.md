# FlowState (Medical Edition v2.0)

A therapeutic neurofeedback application for Muse 2/S devices, designed for clinical-grade focus training and anxiety reduction.

## 🌟 Key Features (v2.0)

### 🧠 **Medical-Grade Biofeedback**
- **Real-Time Visualization**: Delta, Theta, Alpha, Beta, Gamma brainwaves.
- **Clinical Filtering**: 50Hz/60Hz Dual Notch Filters (scipy.signal) for artifact removal.
- **Head Motion**: 3-Axis Gyroscope tracking for posture correction.

### 🔊 **Immersive Audio Layer**
- **Procedural Soundscapes**: "Storm to Calm" audio engine.
- **Binaural Interaction**: Wind intensity controlled by your real-time Focus Score.

### 📊 **Analytics & History**
- **Session Tracking**: Automatic logging of every meditation session.
- **Progress Graphs**: Visual history of Focus Scores and duration.
- **Achievements**: Gamified milestones (7-day streaks, 30-min endurance).

### 🏥 **Therapeutic UI**
- **Privacy First**: All data stored LOCALLY (`user_stats.json`). No cloud upload.
- **Dark Mode**: OLED-optimized interface for low visual stress.

## 🚀 How to Run

### Option 1: Development Mode
1. Ensure your Muse is paired via Windows Settings.
2. Run `RUN_PROJECT.bat`.
3. Click **"Connect"** in the dashboard.

### Option 2: Standalone App
1. Navigate to `dist/FlowState`.
2. Run `FlowState.exe`.
3. (Optional) Use `FlowState_Setup.exe` to install to your computer.

## ⚠️ Troubleshooting

**"Device Not Found" or "Process Died"**
- Windows Bluetooth can "hold" the connection.
- **Solution**: Go to Settings > Bluetooth > Remove Device. Turn Muse OFF/ON. Click Connect in App.

**"No Data / 0%"**
- Ensure you chose "Connect" inside the app, not just in Windows.
- Check "Settings" tab to adjust Sensitivity (default 50%).

## 🏗️ Build Instructions
To re-build the executable:
```bash
pyinstaller --clean flowstate.spec
```
To build installer:
```bash
makensis installer.nsi
```
