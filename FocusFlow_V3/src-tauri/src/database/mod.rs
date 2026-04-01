// ═══════════════════════════════════════════════════════════════
//  FocusFlow V3 — Database Module (Offline-First SQLite + Supabase Sync)
//  Phase 3 of the implementation plan.
//
//  Architecture:
//   1. All DSP output writes to local SQLite first (immune to Wi-Fi drops).
//   2. A background sync daemon pushes unsynchronized rows to Supabase.
//   3. Supabase Row-Level Security (RLS) isolates multi-tenant data.
// ═══════════════════════════════════════════════════════════════

pub mod schema;
pub mod sync;

use serde::{Deserialize, Serialize};

/// A single focus session record.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionRecord {
    pub id: String,
    pub organization_id: Option<String>,
    pub user_id: String,
    pub started_at: String,  // ISO 8601
    pub ended_at: Option<String>,
    pub headset_type: String,
    pub sample_rate: u32,
    pub synced: bool,
}

/// A 30-second epoch summary (for sleep staging or focus tracking).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EpochRecord {
    pub id: String,
    pub session_id: String,
    pub epoch_number: u32,
    pub timestamp: String,
    pub focus_metric: f64,
    pub tbr: f64,
    pub deep_focus_cfc: f64,
    pub emg_detected: bool,
    pub headband_on: bool,
    pub delta_power: f64,
    pub theta_power: f64,
    pub alpha_power: f64,
    pub beta_power: f64,
    pub gamma_power: f64,
    pub mind_state: String,
    pub synced: bool,
}
