# FocusFlow v3.1: Enterprise Technical Specification

## 1. Tech Stack & Architecture
FocusFlow is engineered as a high-concurrency, low-latency neurofeedback infrastructure. It utilizes a hybrid asynchronous architecture to ensure real-time signal fidelity.

*   **Core Backend**: Python 3.11+ leveraging `asyncio` and `aiohttp` for non-blocking I/O.
*   **High-Performance Computing**: `NumPy` and `SciPy` for real-time vector mathematical operations.
*   **Frontend Architecture**: High-speed Vanilla JavaScript (ES6) with hardware-accelerated CSS3 (GPU-composited layers).
*   **Data Serialization**: Custom JSON-based protocol for low-overhead transmission of high-frequency data packets.
*   **Hardware Layer**: `Bleak` (Bluetooth Low Energy) and `PyLSL` (Lab Streaming Layer) for educational-grade time synchronization.

---

## 2. Hardware Integration (Muse 2)
The system employs an industrial-grade BLE stack to interface with the Interaxon Muse 2 hardware.

*   **GATT Protocol**: Direct subscription to EEG characteristic UUIDs, bypassing high-level OS wrappers to minimize jitter.
*   **Stream Parsing**: Real-time bit-shifting and normalization of 12-bit raw EEG ADC values into microvolt (µV) units.
*   **Frequency Band Extraction**: 
    *   Dynamic Fourier Transform (DFT) windows.
    *   **Bands**: Delta (1-4Hz), Theta (4-8Hz), Alpha (8-13Hz), Beta (13-30Hz), Gamma (30-100Hz).
*   **Electrode Topology**: Real-time monitoring of TP9, AF7, AF8, and TP10 sites with a dedicated impedance Checksum.

---

## 3. Core Logic & Algorithms
The "Clinical Brain Engine" uses sophisticated DSP (Digital Signal Processing) to ensure the data is strictly scientific.

*   **Signal Conditioning**: 4th-order Butterworth Bandpass filter (1-45Hz) combined with a 50Hz Notch filter to eradicate DC offset and AC hum.
*   **Common Average Reference (CAR)**: Advanced spatial filtering to eliminate global common-mode noise across the scalp.
*   **Welch PSD Estimation**: Implements Hann Windowing with 50% overlap for superior Power Spectral Density estimation, reducing variance in focus metrics.
*   **Focus Metric calculation**: A weighted spectral ratio algorithm—`Beta Power / (Alpha + Theta)`—normalized against a 10-second rolling Z-score baseline for individualized calibration.

---

## 4. Custom Physics & Interactive Tools
The system features specialized interactive modules designed to convert complex EEG data into intuitive mechanics.

*   **Antigravity UI Mechanics**: A GPU-accelerated "floating" interface that uses linear interpolation (lerp) to map focus scores to vertical momentum. Higher neural focus translates directly to "upward lift" in the UI physics engine.
*   **Glassmorphic Rendering**: Uses back-drop filters and glassmorphism to reduce visual cognitive load, allowing students to maintain focus without UI distraction.
*   **Electrode Diagnostics**: A specialized anatomical UI tool that maps hardware impedance to 3D SVG coordinates, providing immediate feedback on sensor-to-skin connectivity.

---

## 5. Current State of Completion (100% Functional)
*   ✅ **Educational-Grade DSP Pipeline**: CAR, Spike Rejection, and Butterworth filtering.
*   ✅ **Blink-Proof Logic**: Automatic masking of EOG (Eye) artifacts from PSD math.
*   ✅ **Live Dashboard**: Real-time 4-channel EEG plotting and Focus-over-time trends.
*   ✅ **School Management UI**: Hierarchical roster management (Schools/Classes/Students).
*   ✅ **Native Compilation**: Fully functional `.exe` distribution for standalone Windows usage.

---

## 6. Missing Elements (Phase 4 Components)
To maintain the current project's standalone integrity, the following enterprise cloud components are planned for subsequent phases:

*   **Master Admin Web Portal**: Currently, data is managed locally. A centralized, browser-based Next.js portal for remote multi-school administration is **NOT** implemented in this code.
*   **Cloud API (Public Layer)**: While the app has internal connectivity hooks, the public-facing authenticated REST API for external third-party integrations is pending.

---
**Technical Authorization**: Antigravity Precision Engineering 🦾🧠
