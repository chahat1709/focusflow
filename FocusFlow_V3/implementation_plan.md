# FocusFlow V3.0 — Master Blueprint & Implementation Plan
*The single source of truth for the Enterprise Rust/Tauri Rewrite.*

---

## 🎯 V3.0 Mission Statement
V2.3 (Python) validated the DSP math. V3.0 solves the **four fatal flaws** that prevent V2.3 from becoming a real product:

| Fatal Flaw | V2.3 Reality | V3.0 Solution |
|---|---|---|
| Malware Flagging | 280MB PyInstaller EXE, opens localhost ports | 15MB Tauri native installer, zero ports |
| Hardware Lock-In | Hardcoded for Muse 2 only | Rust `HeadsetProvider` trait (Muse, OpenBCI, Neurosity) |
| Single-Player DB | Local SQLite, no multi-user isolation | Supabase RLS Multi-Tenancy |
| No Sleep/Screen Features | Focus-only, 1-second epochs | 30s Sleep Staging + Session Screen Tracker |

---

## 🏗️ PHASE 1: Rust Repository Core

### Step 1: Init the Tauri Workspace
- Command: `npx create-tauri-app@latest ./ --template react-ts`
- This generates `/src-tauri` (Rust backend) and `/src` (React/TypeScript frontend).

### Step 2: Define the `HeadsetProvider` Trait (Hardware Abstraction)
- Create `src-tauri/src/hardware/mod.rs`.
- Define the universal `BrainChunk` struct (timestamp, channel enum, `Vec<f64>` values).
- Define the Rust trait:
```rust
pub trait HeadsetProvider {
    fn connect(&self) -> Result<(), BleError>;
    fn disconnect(&self);
    fn stream(&self, tx: mpsc::Sender<BrainChunk>);
    fn sample_rate(&self) -> u32;
}
```

### Step 3: Build the Muse BLE Connector
- Use the `btleplug` Rust crate (cross-platform async BLE).
- Replicate `muse_ble.py` logic: connect to UUID `fe8d`, subscribe to `273e0003`...`0006`.
- Write the bit-shifting parser in Rust to extract 12-bit unsigned packet data.

### Step 4: Build the OpenBCI Connector
- Implement `HeadsetProvider` for USB Serial via the `serialport` crate.
- Parse OpenBCI Cyton 8-channel data (250Hz).

---

## 🧠 PHASE 2: DSP Math Translation (Python → Rust)
*Reference file: `../production_server.py` (V2.3 verified math).*

### Step 5: Core Signal Processing
- Crates: `rustfft`, `ndarray`, `realfft`.
- Translate `_zscore_clip` into generic Rust `Vec<f64>` operations.

### Step 6: NLMS Adaptive Kernel
- Convert the Python `@njit` block into native Rust.
- Implement the 6-harmonic reference matrix generator.
- Preserve the 2.5s **death-lock timeout** (`frozen_count` logic, 640 samples @ 256Hz).

### Step 7: Artifact Suite
- **Powerline Antenna Check:** 50/60Hz ratio > 60% = headband off.
- **Blink Detector:** 3x running standard deviation tracking.
- **EMG Cross-Correlation:** 20-30Hz vs 40-100Hz simultaneous spike = invalidate TBR.

### Step 8: 30-Second Sleep Staging Engine (NEW)
- Build `sleep_pipeline.rs` that buffers 30s of `BrainChunk` data.
- **Deep Sleep (N3):** Delta (0.5–4Hz) > 20% of epoch.
- **Light Sleep (N2):** Spindle detection (11–16Hz micro-bursts ~0.5s).
- **REM:** Use AF7/AF8 blink-detector to isolate Rapid Eye Movements.

---

## ☁️ PHASE 3: Supabase Multi-Tenancy & Sync

### Step 9: Supabase RLS Setup
- Tables: `Organizations`, `Users`, `Sessions`, `Epochs`.
- SQL Policy: `CREATE POLICY "Isolate Labs" ON Sessions FOR SELECT USING (auth.jwt() ->> 'org_id' = organization_id);`

### Step 10: Offline-First SQLite Cache
- Use Rust `sqlx` crate → local SQLite in `%LocalAppData%/FocusFlow/`.
- All DSP output writes locally first (immune to Wi-Fi drops).

### Step 11: Background Sync Daemon
- Async `tokio` thread checks connectivity every 60s.
- Batch-uploads rows where `synced = 0` to Supabase REST API with JWT.

---

## 🔬 PHASE 3.5: Mathematical Hardening (Academic Grade)

### Step 11b: Stateful SignalProcessor (Causality Fix)
- **Problem:** `filtfilt` is non-causal; stateless filters cause transients.
- **Fix:** Create a `SignalProcessor` struct in `dsp/mod.rs` that persists between chunks.
- **Components:**
    - `Map<Channel, IirFilter>`: Persistent Direct-Form II state for 1-45Hz Bandpass.
    - `Map<Channel, VecDeque<f64>>`: 4-second (1024 sample) rolling buffers for true 0.25Hz resolution.
    - `EMGDetector`: Cross-correlation logic between 13-30Hz and 30-100Hz.
    - `SnapshotGenerator`: Converts processed arrays into `DspSnapshot`.

---

## 🖥️ PHASE 4: React/Tauri Frontend

### Step 12: Dashboard UI
- React + TailwindCSS + `recharts` for clinical data visualization.
- Dark mode by default, responsive layout.

### Step 13: Rust-to-React IPC
- Replace HTTP/SSE with Tauri native events: `app.emit_all("dsp-stream", payload)`.
- React: `listen("dsp-stream", (e) => updateCharts(e.payload));`

### Step 14: Session Screen Tracker (NEW)
- Windows: Use `windows-rs` crate to call `GetForegroundWindow()` every 5s.
- Log active app title alongside focus metrics in SQLite.
- Dashboard overlay: Focus Trendline on App Timeline.

### Step 15: Final Binary Build
- Command: `cargo tauri build`
- Target: Single `.msi` installer < 20MB.
- Verify Windows Defender does NOT flag it.

---

## 💰 Valuation Impact
| Metric | V2.3 (Now) | V3.0 (After) |
|---|---|---|
| Binary Size | 280MB | ~15MB |
| Hardware Support | Muse 2 only | Muse + OpenBCI + Neurosity |
| Multi-User | ❌ | ✅ (RLS) |
| Sleep Tracking | ❌ | ✅ (30s Epochs) |
| Screen Correlation | ❌ | ✅ (Win32 API) |
| Sell Price (B2B IP) | $24,000 | $250,000+ |
| SaaS Potential (ARR) | $0 | $300,000/yr @ 50 labs |
