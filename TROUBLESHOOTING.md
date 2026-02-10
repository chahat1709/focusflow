# 🛠️ Muse 2 Troubleshooting Guide

## 🚨 Critical: "Signal Frozen" / "Zombie Stream"
**Symptoms:**
- Dashboard says **ONLINE**.
- Graphs are flatlined (0.0).
- Probe report says: `💀 ZOMBIE CONFIRMED: Stream Active but ALL ZEROS`.
- Or Probe report says: `❌ TIMEOUT (No Data Flows)`.

**Cause:**
The Muse device firmware has crashed or "locked up" internally. It maintains the Bluetooth connection but stops sending data packets. This often happens if the device disconnects abruptly while streaming.

**✅ The Fix (Hard Reset):**
Since the power button often becomes unresponsive in this state:
1.  **Disconnect USB:** Ensure the device is not plugged in.
2.  **Force Shutdown:** Hold the Power Button for **45-60 seconds**. Ignore any LED flashes. Keep holding until it is completely dark.
3.  **Wait:** Leave it off for 10 seconds.
4.  **Restart:** Turn it back on normally.
5.  **Restart Software:** Run `RUN_PROJECT.bat` again.

**💀 Last Resort (If Button Fails):**
If the power button does nothing, you must let the battery drain completely. Leave the device on the shelf for 4-8 hours until the LED goes out. Charge it for 30mins and try again.

---

## ⚠️ Connection Issues
**"No Signals Found" during scan:**
1.  Ensure Bluetooth is ON.
2.  Hold the Muse power button for 5 seconds until LEDs enter "Pairing Mode" (cascading lights).
3.  Check if another app (Official Muse App) is open on your phone or PC. **Kill it.** The Muse can only connect to one app at a time.

**"Bluetooth Hardware Error":**
1.  Toggle Windows Bluetooth OFF and ON.
2.  If persistent, reboot the PC. The Windows BLE stack can sometimes freeze.

---

## 📉 Signal Quality
**"Noisy" / "Jittery" Signal:**
- **Forehead Contact:** Wipe your forehead with a damp cloth (water/alcohol). Skin oils block the signal.
- **Hair Interference:** Ensure no hair is trapped under the ear sensors (Rubber pieces).
- **Notch Filter:** Ensure the backend is running. The 50Hz/60Hz notch filter is essential for removing mains hum.

## 📊 Developer Diagnostics
Run the probe tool to see the raw state of the hardware:
```bash
python probe_lsl.py
```
This will tell you if the LSL stream is visible and if data is actually flowing.
