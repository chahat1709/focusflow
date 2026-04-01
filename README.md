# FocusFlow — Real-Time Neurofeedback System for Muse 2

> **Verified Indigenous Core Technology. An Educational EEG focus scoring platform built through the lens of a Vibe Coder—combining vision, intuition, and deep AI-collaboration to bypass vendor SDKs and build a native machine.**

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey) ![Hardware](https://img.shields.io/badge/Hardware-Muse%202%20EEG-purple) ![Status](https://img.shields.io/badge/Status-Indigenous%20Core%20Tech-brightgreen)

---

## 🧠 What Is FocusFlow?

FocusFlow is a **standalone, offline, Educational EEG** neurofeedback platform that turns the Muse 2 EEG headband into a focus assessment tool for schools, clinics, and educational labs. 

It represents the pinnacle of **AI-assisted engineering**: using vision and high-level strategy to develop low-level signal processing that traditionally requires an entire team of embedded developers. 

**No cloud. No subscription. No vendor SDKs. Just the engine. Runs on any Windows machine.**

---

## 🔬 Scientific Pipeline (5-Stage DSP)

| Stage | Algorithm | Purpose |
|---|---|---|
| **Stage 1** | 4th-order Butterworth Bandpass (1-45Hz) + Dual Notch (50/60Hz) | Remove DC drift and power-line noise |
| **Stage 2** | Common Average Reference (CAR) | Spatial noise cancellation across all 4 electrodes |
| **Stage 3** | IMU Motion Mask (Accelerometer-gated) | Veto EEG samples during head movement |
| **Stage 4** | Lightweight ASR (z-threshold spike rejection) | Replace artifact samples without discarding the window |
| **Stage 5** | Welch PSD + IAF Calibration + Z-Score Focus Metric | Personalized, normalized focus score per individual |

**Bonus:** Cross-Frequency Coupling (Alpha-Gamma CFC via Hilbert Transform) generates a secondary "Deep Focus" metric — typically only available in $30,000+ lab-grade EEG amplifiers.

---

## ⚡ Key Features

- 🔗 **Dual connection strategy** — Direct BLE via `bleak` (primary) + `muselsl/pylsl` LSL stream (fallback)
- 📊 **Live 4-channel EEG dashboard** with real-time band power visualization
- 🎯 **IAF-personalized focus score** — calibrates to each individual's brain in 15 seconds
- 👁️ **Blink & EMG artifact rejection** — clinically accurate, not distorted by eye movements
- ❤️ **Real-time BPM** from Muse 2 PPG optical heart rate sensor
- 🏫 **School management system** — Schools → Classes → Students hierarchy
- 📄 **Automated PDF reports** — generated per session, per student
- 🧘 **Mind State Classifier** — Calm / Neutral / Active (similar to Muse app, but open)
- 💊 **Headband contact detection** — debounced, signal-quality-based (not spectral)
- 🖥️ **Single `.exe` distribution** — zero install for end-users

---

## 🏗️ Tech Stack

- **Backend:** Python 3.11, `asyncio`, `aiohttp`
- **Hardware:** `bleak` (Direct BLE) + `muselsl/pylsl` (LSL fallback), GATT UUID subscription
- **DSP:** `numpy`, `scipy.signal`
- **Database:** Supabase (cloud)
- **Frontend:** Vanilla JavaScript, hardware-accelerated CSS3
- **Distribution:** PyInstaller single-file `.exe`

---

## 🖥️ Screenshots

> *Dashboard with live EEG, focus score, and electrode contact map.*

---

## 📂 Repository Structure

```
focusflow/
├── production_server.py     # Core async server + 5-stage DSP pipeline
├── muse_ble.py              # Direct BLE driver for Muse 2 (GATT)
├── database.py              # Student/school management
├── dashboard.html           # Real-time frontend
├── dashboard_therapeutic.js # UI logic and session control
├── reporting.py             # PDF report generation
└── BUILD_EXE.bat            # PyInstaller build script
```

---

## 💼 Licensing & Acquisition

This project is available for:

| Type | Details |
|---|---|
| **Binary License** | One-time fee. Compiled `.exe` for a single organization. |
| **Full IP Transfer** | Complete source code + all rights. Ideal for integration into a commercial product. |
| **Research License** | For academic institutions. Custom pricing available. |

> **Interested in licensing or acquiring this technology?**
> 📧 Contact: chahatjain1315@gmail.com
> 🔗 LinkedIn: [linkedin.com/in/chahatjain1315](https://linkedin.com/in/chahatjain1315)

---

## ⚠️ License

Copyright © 2025-2026 Chahat Jain. All Rights Reserved.

This is proprietary software. See [LICENSE](./LICENSE) for full terms.
Unauthorized use, copying, or distribution is strictly prohibited.

---

*Verified Indigenous Core Technology. Built through Vision and AI-Collaboration.*
