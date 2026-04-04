# FocusFlow V3 — Native Real-Time Brain-Computer Interface

> **Status:** 🚧 Active R&D / Engineering Rewrite

A high-performance native desktop application to read, process, and map real-time brainwave data via a connected Muse 2 wearable device. Built entirely from scratch bypassing proprietary SDKs, utilizing custom `Rust` Bluetooth Low Energy (BLE) handlers and native Digital Signal Processing (DSP).

## 🔬 Research Context

**Research Problem:** Existing BCI focus metrics experience >30% temporal drift over 20 minutes due to baseline environmental shifts and sensor fatigue, making long-term therapeutic focus tracking unreliable.

**Working Hypothesis:** Integrating a rolling baseline Z-score calibration in tandem with Individual Alpha Frequency (IAF) filtering will prevent temporal drift without increasing computational latency beyond a strict 50ms constraint.

**Research Goal:** To achieve a 20%+ accuracy retention in sustained focus state classification compared to default middleware (e.g., Muse SDK default metrics).

**Current Progress:** The full DSP pipeline has been architected in Rust, achieving sub-millisecond memory-safe buffer execution. BLE handlers are completely isolated from proprietary middleware. Currently tuning NLMS adaptive filters.

## 🧠 Perplexity Research Proposal Alignment
*This project is part of my portfolio application for the Perplexity AI Research Residency.* 

**Low-Level Edge Execution:** At Perplexity, my core proposal involves building the "Edge-Augmented Answer Engine"—a lightweight background daemon that silently vectorizes the user's active screen context instantly. FocusFlow V3 demonstrates my extreme proficiency in exactly this domain: writing bare-metal, high-performance background services in `Rust` and `Tauri` that can process overwhelming streams of real-time data (256Hz EEG streams) silently in the background without crushing the user's CPU, a mandatory capability for deploying on-device LLM context injection safely.

---

## 🎥 Demonstration

*(GIF Placeholder - Upload a 1-minute screen record of the Native HTMX Dashboard connecting to the Muse headset here)*

## Architecture & DSP Pipeline

*(Draw.io Placeholder - Upload the FocusFlow Architecture Diagram here)*

1. **Hardware Ingestion (Rust + Windows.Devices.Bluetooth):** Raw multi-byte stream parsing mapped exactly to Muse 2 characteristic UUIDs.
2. **Pre-Processing (Digital Signal Processing):** 
   - 4th-order cascaded biquad Butterworth filters (1-50Hz bandpass).
   - NLMS (Normalized Least Mean Squares) Adaptive Notch filtering for 50Hz/60Hz mains noise suppression.
3. **Feature Extraction:** Welch's Method for PSD (Power Spectral Density), extracting Theta, Alpha, Beta, and Gamma ratios.
4. **State Engine:** Causal focus metric calibration (Relative Beta/Theta Ratio calculation) clamped to 1Hz throughput to prevent frontend saturation.
5. **Frontend (HTMX + Tauri):** Lightweight native overlay delivering sub-15ms DOM updates.

## Technical Stack
- **Systems & Hardware:** Rust, Tauri, native BLE APIs
- **Math/DSP:** Rust implementation of cascaded biquads, Fast Fourier Transforms (FFT), Vector math arrays
- **User Interface:** React / HTMX, TailwindCSS 
