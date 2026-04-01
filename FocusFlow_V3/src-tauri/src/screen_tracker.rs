// ═══════════════════════════════════════════════════════════════
//  FocusFlow V3 — Session Screen Tracker (Windows)
//  Step 14 of the implementation plan.
//
//  Polls the active foreground window every 5 seconds and logs
//  the app name alongside EEG focus metrics in the local SQLite.
//  Only active during Pomodoro sessions (not full-day).
// ═══════════════════════════════════════════════════════════════

use serde::{Deserialize, Serialize};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

/// A single screen activity record.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScreenActivity {
    pub timestamp: u64,       // Unix timestamp ms
    pub app_name: String,     // e.g., "Code.exe"
    pub window_title: String, // e.g., "production_server.py - VS Code"
    pub focus_metric: f64,    // EEG focus at this moment
    pub duration_secs: u64,   // How long this app was in foreground
}

/// Tracks the current session's app usage.
pub struct ScreenTracker {
    pub active: bool,
    pub poll_interval: Duration,
    pub history: Vec<ScreenActivity>,
    last_app: String,
    last_switch_time: u64,
}

impl ScreenTracker {
    pub fn new() -> Self {
        Self {
            active: false,
            poll_interval: Duration::from_secs(5),
            history: Vec::new(),
            last_app: String::new(),
            last_switch_time: Self::now_ms(),
        }
    }

    fn now_ms() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64
    }

    /// Start tracking screen activity for a session.
    pub fn start(&mut self) {
        self.active = true;
        self.history.clear();
        self.last_app = String::new();
        self.last_switch_time = Self::now_ms();
    }

    /// Stop tracking and return the activity log.
    pub fn stop(&mut self) -> Vec<ScreenActivity> {
        self.active = false;
        self.flush_current();
        std::mem::take(&mut self.history)
    }

    /// Record a foreground window observation.
    /// Called every 5 seconds by the polling loop.
    pub fn record(&mut self, app_name: &str, window_title: &str, current_focus: f64) {
        if !self.active {
            return;
        }

        let now = Self::now_ms();

        // If the app changed, finalize the previous entry
        if app_name != self.last_app && !self.last_app.is_empty() {
            let duration = (now - self.last_switch_time) / 1000;
            self.history.push(ScreenActivity {
                timestamp: self.last_switch_time,
                app_name: self.last_app.clone(),
                window_title: window_title.to_string(),
                focus_metric: current_focus,
                duration_secs: duration,
            });
            self.last_switch_time = now;
        }

        self.last_app = app_name.to_string();
    }

    /// Flush the current app to history (on session end).
    fn flush_current(&mut self) {
        if !self.last_app.is_empty() {
            let now = Self::now_ms();
            let duration = (now - self.last_switch_time) / 1000;
            self.history.push(ScreenActivity {
                timestamp: self.last_switch_time,
                app_name: self.last_app.clone(),
                window_title: String::new(),
                focus_metric: 0.0,
                duration_secs: duration,
            });
        }
    }

    /// Generate a per-app focus summary.
    /// Output: "VS Code: avg 85% focus, 45min | Chrome: avg 35% focus, 15min"
    pub fn summarize(&self) -> Vec<AppFocusSummary> {
        let mut map: std::collections::HashMap<String, (f64, u64, u32)> = std::collections::HashMap::new();

        for entry in &self.history {
            let e = map.entry(entry.app_name.clone()).or_insert((0.0, 0, 0));
            e.0 += entry.focus_metric;
            e.1 += entry.duration_secs;
            e.2 += 1;
        }

        map.into_iter()
            .map(|(app, (total_focus, total_secs, count))| AppFocusSummary {
                app_name: app,
                avg_focus: if count > 0 { total_focus / count as f64 } else { 0.0 },
                total_seconds: total_secs,
            })
            .collect()
    }
}

/// Summary of focus per application.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppFocusSummary {
    pub app_name: String,
    pub avg_focus: f64,
    pub total_seconds: u64,
}

/// Get the foreground window info on Windows.
/// Uses the Windows API: `GetForegroundWindow()` + `GetWindowText()`.
///
/// NOTE: This requires the `windows-rs` crate in production.
/// For the scaffold, we return a placeholder.
#[cfg(target_os = "windows")]
pub fn get_foreground_window() -> (String, String) {
    // TODO: Wire up windows-rs API calls:
    // unsafe {
    //     let hwnd = GetForegroundWindow();
    //     let mut title = [0u16; 256];
    //     GetWindowTextW(hwnd, &mut title);
    //     // Parse process name from hwnd
    // }
    ("Unknown.exe".to_string(), "FocusFlow V3 — Scaffold".to_string())
}

#[cfg(not(target_os = "windows"))]
pub fn get_foreground_window() -> (String, String) {
    ("Unknown".to_string(), "Screen tracking not supported on this OS".to_string())
}

// ── Unit Tests ─────────────────────────────────────────────────
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tracker_starts_and_stops() {
        let mut tracker = ScreenTracker::new();
        tracker.start();
        assert!(tracker.active);
        tracker.record("Code.exe", "main.rs - VS Code", 0.85);
        tracker.record("Code.exe", "main.rs - VS Code", 0.80);
        tracker.record("Chrome.exe", "YouTube", 0.30);
        let history = tracker.stop();
        assert!(!tracker.active);
        assert!(!history.is_empty());
    }

    #[test]
    fn test_summarize_groups_by_app() {
        let mut tracker = ScreenTracker::new();
        // Manually push history entries for a deterministic test
        tracker.history.push(ScreenActivity {
            timestamp: 1000,
            app_name: "Code.exe".into(),
            window_title: "file.rs".into(),
            focus_metric: 0.85,
            duration_secs: 120,
        });
        tracker.history.push(ScreenActivity {
            timestamp: 2000,
            app_name: "Chrome.exe".into(),
            window_title: "YouTube".into(),
            focus_metric: 0.30,
            duration_secs: 60,
        });
        let summary = tracker.summarize();
        assert_eq!(summary.len(), 2, "Should have two apps: Code and Chrome");
    }
}
