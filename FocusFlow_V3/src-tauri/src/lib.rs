// ═══════════════════════════════════════════════════════════════
//  FocusFlow V3 — Library Root
//  Wires all modules together for the Tauri app.
//  Phase 1: hardware | Phase 2: dsp | Phase 3: database
//  Phase 4: screen_tracker + Tauri IPC commands
// ═══════════════════════════════════════════════════════════════

pub mod hardware;
pub mod dsp;
pub mod database;
pub mod screen_tracker;

use serde::Serialize;

use hardware::muse::MuseConnector;
use hardware::{HeadsetProvider, ConnectionStatus};
use std::sync::Arc;
use tokio::sync::Mutex;
use tauri::Emitter;

// ── Application State ──────────────────────────────────────────
pub struct AppState {
    pub muse: Arc<Mutex<MuseConnector>>,
}

// ── Tauri IPC Commands (Step 13) ──────────────────────────────
// These replace HTTP/SSE with native Tauri events.
// React calls: invoke("greet", { name: "Chahat" })
// React listens: listen("dsp-stream", (e) => updateCharts(e.payload))

#[tauri::command]
fn greet(name: &str) -> String {
    format!("FocusFlow V3 — Welcome, {}! DSP Engine Ready.", name)
}

#[tauri::command]
fn get_supported_headsets() -> Vec<String> {
    vec![
        "Muse 2 (BLE, 4ch, 256Hz)".into(),
        "OpenBCI Cyton (Serial, 8ch, 250Hz)".into(),
        "Neurosity Crown (WiFi, 8ch, 256Hz) — Coming Soon".into(),
    ]
}

/// System status for the React dashboard.
#[derive(Serialize)]
struct SystemStatus {
    version: String,
    rust_backend: bool,
    headset_connected: bool,
    database_ready: bool,
    sleep_staging: bool,
    screen_tracker: bool,
}

#[tauri::command]
async fn get_system_status(state: tauri::State<'_, AppState>) -> Result<SystemStatus, String> {
    let muse = state.muse.lock().await;
    let status = muse.status();
    let headset_connected = status == ConnectionStatus::Streaming || status == ConnectionStatus::Connected;
    Ok(SystemStatus {
        version: "3.0.0".into(),
        rust_backend: true,
        headset_connected,
        database_ready: false,  // Not yet integrated
        sleep_staging: false,   // Pipeline exists but not wired
        screen_tracker: cfg!(target_os = "windows"),
    })
}

/// Get the DSP pipeline configuration.
#[derive(Serialize)]
struct DspConfig {
    sample_rate: u32,
    nfft: usize,
    freq_resolution_hz: f64,
    nlms_mu: f64,
    nlms_taps: usize,
    nlms_harmonics: usize,
    death_lock_threshold_samples: u64,
    sleep_epoch_seconds: u32,
}

#[tauri::command]
fn get_dsp_config() -> DspConfig {
    DspConfig {
        sample_rate: 256,
        nfft: 1024,
        freq_resolution_hz: 0.25,
        nlms_mu: 0.1,
        nlms_taps: 2,
        nlms_harmonics: 6,
        death_lock_threshold_samples: dsp::nlms::DEATH_LOCK_THRESHOLD,
        sleep_epoch_seconds: 30,
    }
}

// ── Hardware Integration Commands (Phase 5) ───────────────────
#[tauri::command]
async fn scan_muse(state: tauri::State<'_, AppState>) -> Result<Vec<String>, String> {
    let muse = state.muse.lock().await;
    muse.scan(5).await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn connect_muse(device_id: String, state: tauri::State<'_, AppState>, app: tauri::AppHandle) -> Result<(), String> {
    // Create the channel BEFORE acquiring the lock, so the receiver can be
    // moved into the background task without the lock in scope.
    let (tx, mut rx) = tokio::sync::mpsc::channel(1000);

    // Explicit scope: the MutexGuard is dropped at the closing `}` BEFORE
    // the background task is spawned. This ensures any concurrent call to
    // scan_muse or get_system_status is not blocked by the DSP loop.
    {
        let muse = state.muse.lock().await;
        muse.connect(&device_id).await.map_err(|e| e.to_string())?;
        muse.stream(tx).await.map_err(|e| e.to_string())?;
    } // ← MutexGuard dropped here. All subsequent commands can acquire the lock.

    // Spawn DSP pipeline loop in background (no lock held)
    tauri::async_runtime::spawn(async move {
        // V3.1: Academic-Grade Stateful Signal Processor (256Hz, 4s window)
        let mut processor = dsp::SignalProcessor::new(256.0, 1024);
        while let Some(chunk) = rx.recv().await {
            // Process the chunk via the stateful engine
            if let Some(snapshot) = processor.process_chunk(chunk) {
                // Emit telemetry to frontend every ~1 second for visual smoothness
                let _ = app.emit("dsp-snapshot", snapshot);
            }
        }
    });

    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(AppState {
            muse: Arc::new(Mutex::new(MuseConnector::new())),
        })
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            greet,
            get_supported_headsets,
            get_system_status,
            get_dsp_config,
            scan_muse,
            connect_muse,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
