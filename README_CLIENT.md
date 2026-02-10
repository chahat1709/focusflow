# Focus Flow v1.1 - EEG Monitoring & Focus Analysis

Professional neurofeedback application for real-time EEG monitoring and focus metric calculation using Muse headband.

---

## 🎯 What is Focus Flow?

Focus Flow connects to your Muse EEG headband and provides:
- **Real-time EEG readings** from 4 channels (TP9, AF7, AF8, TP10)
- **Live focus metric calculation** based on brainwave patterns
- **Heart rate (BPM) monitoring**
- **Interactive dashboard** with live data visualization

---

## 📋 System Requirements

- **Operating System:** Windows 10/11
- **Python:** Version 3.12 or higher
- **Bluetooth:** Built-in or USB Bluetooth adapter
- **Muse Headband:** Muse 2 or compatible model
- **RAM:** Minimum 4GB
- **Disk Space:** 500MB free

---

## 🚀 Quick Start (One-Click)

### 1. Installation
Just double-click **`Setup_FocusFlow.bat`**.
*   It automatically installs Python (if needed).
*   It installs all required libraries.
*   It creates a **"Launch Focus Flow"** shortcut on your Desktop.

### 2. Launching
*   Double-click the **"Launch Focus Flow"** shortcut on your Desktop.
*   Or double-click **`start_app_monolith.py`**.

### 3. Updates
To update the app in the future:
1.  Paste the new files into this folder.
2.  Double-click **`Update_App.bat`**.

---

## 🔧 Manual Setup (Detail)
If you prefer manual control:
1.  Install Python 3.12+ (Tick "Add to PATH").
2.  Open Terminal > `pip install -r requirements.txt`.
3.  Run `python start_app_monolith.py`.

5. **Your browser will open automatically** with the dashboard at: `http://localhost:8000`

6. **Click "Connect Muse"** button and select your headband from the list

7. **Monitor live data:**
   - EEG waveforms for each channel
   - Focus metric (0-100 scale)
   - Heart rate (BPM)

### To Stop the Application:

- Press `Ctrl+C` in the PowerShell/Command Prompt window
- Or close the terminal window

---

## 🔧 Troubleshooting

### "Python is not recognized..."
**Solution:** Python was not added to PATH during installation.
- Uninstall Python
- Reinstall and **CHECK "Add Python to PATH"**

### "Module not found" errors
**Solution:** Dependencies not installed.
- Run: `pip install flask flask-cors pylsl bleak python-osc numpy scipy pygame`

### Browser doesn't open automatically
**Solution:** Open manually.
- Go to: `http://localhost:8000` in any browser

### "Connection refused" error
**Solution:** Backend didn't start.
- Check terminal for error messages
- Ensure no other app is using port 5001 or 8000

### Muse headband not connecting
**Solutions:**
- Ensure Muse is powered on and charged
- Enable Bluetooth on your computer
- Try turning Bluetooth off/on
- Restart the Muse headband
- Move closer to your computer (within 3 feet)

### Dashboard shows no data
**Solutions:**
- Check that "Connected" status shows green
- Ensure Muse headband is properly positioned on your head
- Click "Connect Muse" again
- Restart the application

---

## 📁 Important Files

| File | Purpose |
|------|---------|
| `start_app_monolith.py` | Main application launcher |
| `dashboard.html` | Dashboard interface |
| `config.json` | Application settings |
| `src/` | Core application code |
| `assets/` | UI assets and styles |

⚠️ **Do NOT delete or modify these files unless you know what you're doing.**

---

## 🛡️ Security & Privacy

- **All data stays on your computer** - no cloud uploads
- **No internet connection required** after initial setup
- **Session data** saved locally in `session_data/` folder

---

## 📊 Session Data

EEG recordings are automatically saved as CSV files in the `session_data/` folder with timestamps.

Format: `session_YYYYMMDD_HHMMSS.csv`

---

## 💡 Tips for Best Results

1. **Headband Placement:** Ensure all electrodes touch your skin
2. **Stay Still:** Minimize movement during readings
3. **Quiet Environment:** Reduce external distractions
4. **Hydration:** Well-hydrated skin improves signal quality

---

## 📞 Support

If you encounter issues not covered in this guide:
- Check that all steps were followed exactly
- Ensure Python 3.12+ is correctly installed
- Verify all dependencies are installed
- Try restarting your computer

---

## 📝 Version Information

**Version:** 1.1  
**Release Date:** February 2026  
**Python Required:** 3.12+  
**Supported Devices:** Muse 2, Muse S

---

**Enjoy your Focus Flow experience!** 🧠✨
