# FocusFlow V3 — Real-Time EEG Neurofeedback Engine

> **A production-grade Brain-Computer Interface built in Rust + Tauri.**  
> Streams live EEG from a Muse 2 headband, runs a full clinical DSP pipeline,  
> and visualises focus metrics in real-time — all in a single native desktop app.

[![Rust](https://img.shields.io/badge/Backend-Rust-orange?logo=rust)](https://www.rust-lang.org/)
[![Tauri](https://img.shields.io/badge/Framework-Tauri%20v2-blue?logo=tauri)](https://tauri.app/)
[![Tests](https://img.shields.io/badge/Tests-34%20passing-brightgreen)]()
[![License](https://img.shields.io/badge/License-MIT-lightgrey)]()

---

## Architecture

```
Muse 2 Headband (BLE, 256 Hz)
        │
        │  btleplug (Rust async BLE driver)
        ▼
┌─────────────────────────────────────┐
│     Hardware Abstraction Layer      │  hardware/mod.rs
│  HeadsetProvider trait — vendor     │  hardware/muse.rs
│  agnostic (Muse / OpenBCI / Crown)  │
└────────────────┬────────────────────┘
                 │  BrainChunk { channel, samples_uv, timestamp_us }
                 ▼
┌─────────────────────────────────────┐
│         DSP Engine (Rust)           │
│                                     │
│  1. Butterworth Bandpass (1–45 Hz)  │  dsp/filters.rs
│     4th-order, bilinear transform   │
│     Pre-warped analog frequencies   │
│                                     │
│  2. NLMS Adaptive Notch Filter      │  dsp/nlms.rs
│     50/60 Hz powerline removal      │
│     6 harmonics, 2 taps             │
│     Death-lock guard (2.5s gate)    │
│                                     │
│  3. Artifact Detection              │  dsp/artifacts.rs
│     EMG (jaw clench / jaw grind)    │
│     Blink detection (AF7+AF8)       │
│     Powerline antenna check         │
│                                     │
│  4. Welch PSD (1024-point FFT)      │  dsp/features.rs
│     4-channel averaged spectrum     │
│     IAF-personalised band borders   │
│                                     │
│  5. Focus Metric (TBR z-score)      │  dsp/features.rs
│     30s baseline calibration        │
│     theta/beta ratio, EMG-gated     │
│                                     │
│  6. Sleep Staging (AASM epochs)     │  dsp/sleep_pipeline.rs
│     30s epochs, N1/N2/N3/REM/Wake  │
└────────────────┬────────────────────┘
                 │  DspSnapshot (Tauri IPC event: "dsp-snapshot")
                 ▼
┌─────────────────────────────────────┐
│     Frontend Dashboard (JS)         │
│  Chart.js live band-power plots     │
│  Focus ring, mind-state badge       │
│  Session recording & analytics      │
└─────────────────────────────────────┘
```

---

## Mathematical Hardening (v3.1)

This codebase underwent a **deep algorithmic audit** in April 2026.  
Nine bugs were identified and patched. All 34 unit tests pass.

| Severity | File | Bug | Fix |
|---|---|---|---|
| 🔴 Critical | `features.rs` | TBR→Focus z-score was **inverted** (high theta = 95% focus) | Inverted to `(mean − raw) / std` |
| 🔴 Critical | `filters.rs` | Audio EQ Cookbook formula (peaking resonator) used instead of Butterworth | Full bilinear-transform derivation with pre-warped analog frequencies |
| 🔴 Critical | `nlms.rs` | Death-lock counter accumulated forever on clean data | Counter now halves exponentially on clean chunks |
| 🟡 Arch | `mod.rs` | Only AF7 used for PSD — 75% of sensor data ignored | Averaged across all 4 channels (2× SNR improvement) |
| 🟡 Arch | `lib.rs` | MutexGuard held across full connection + stream setup | Scoped to drop before DSP background task spawns |
| 🟡 Arch | `dashboard.js` | `focus_metric` divided by 100 again (was always 0%) | Removed erroneous `/100.0` |
| 🟢 Minor | `artifacts.rs` | Blink EMA alpha=0.05 (60s adaptation lag) | Changed to 0.2 (5s adaptation) |
| 🟢 Minor | `muse.rs` | `.unwrap()` on UUID parse — silent crash on typo | `.unwrap_or_else` with descriptive message |
| 🟢 Minor | `sleep_pipeline.rs` | `std_dev([])` returned `1.0` → false REM detections | Returns `INFINITY` so threshold collapses |

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Desktop shell | Tauri v2 | Native window, IPC bridge, zero-copy event emission |
| Backend | Rust (async Tokio) | Hard real-time DSP, BLE hardware driver |
| BLE driver | `btleplug` | Cross-platform Bluetooth LE for Muse 2 |
| Signal processing | Custom IIR engine | Butterworth bandpass, NLMS adaptive notch |
| Spectral analysis | Welch's method (1024-pt FFT) | Band power extraction, IAF personalisation |
| Frontend | Vanilla JS + Chart.js | Real-time EEG visualisation |

---

## Setup

```bash
# Prerequisites: Rust (1.75+), Node.js 18+, Tauri CLI
npm install
npm run tauri dev
```

Hardware: InteraXon **Muse 2** headband (BLE). Power on and press Connect.

---

## Unit Tests

```bash
cd src-tauri
cargo test
# Expected: 34 passed; 0 failed
```

---

## Research Context

FocusFlow V3 is designed as a platform for studying **adaptive neurofeedback** —  
the use of real-time EEG to help users learn to consciously shift their own  
brain states. The DSP pipeline implements the same signal chain used in  
published BCI research:

- **Butterworth bandpass** (bilinear transform) — the industry standard for  
  physiological signal conditioning
- **Welch's method** — reduces spectral variance vs. single FFT by 50%
- **IAF personalisation** — individual alpha frequency shifts band borders  
  to account for the ~1 Hz natural variation between subjects
- **NLMS adaptive filtering** — converges to each environment's powerline  
  interference without manual configuration

---

*Built by [Chahat Jain](https://github.com/chahat1709) · Perplexity AI Research Residency 2026*
