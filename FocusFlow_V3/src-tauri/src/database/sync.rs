// ═══════════════════════════════════════════════════════════════
//  FocusFlow V3 — Background Sync Daemon
//  Asynchronously pushes unsynced SQLite rows to Supabase REST API.
//  Runs on a low-priority tokio thread, checking every 60 seconds.
//
//  Phase 3, Step 11 of the implementation plan.
// ═══════════════════════════════════════════════════════════════

use serde::{Deserialize, Serialize};
use std::time::Duration;

/// Configuration for the Supabase sync daemon.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncConfig {
    /// Supabase project URL (e.g., "https://xyz.supabase.co")
    pub supabase_url: String,
    /// Supabase anonymous/service key
    pub supabase_key: String,
    /// How often to check for unsynced rows (in seconds)
    pub sync_interval_secs: u64,
    /// Maximum rows to push per sync cycle
    pub batch_size: usize,
}

impl Default for SyncConfig {
    fn default() -> Self {
        Self {
            supabase_url: String::new(),
            supabase_key: String::new(),
            sync_interval_secs: 60,
            batch_size: 50,
        }
    }
}

/// Status of the sync daemon.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SyncStatus {
    Idle,
    Syncing,
    Error,
    Disabled,
}

/// The sync daemon: checks local SQLite for `synced = 0` rows
/// and batch-uploads them to Supabase REST API with the user's JWT.
///
/// This is a scaffold — the actual HTTP calls require `reqwest`
/// which will be added when the sync is activated.
pub struct SyncDaemon {
    pub config: SyncConfig,
    pub status: SyncStatus,
    pub last_sync_at: Option<String>,
    pub pending_count: u64,
}

impl SyncDaemon {
    pub fn new(config: SyncConfig) -> Self {
        let status = if config.supabase_url.is_empty() {
            SyncStatus::Disabled
        } else {
            SyncStatus::Idle
        };

        Self {
            config,
            status,
            last_sync_at: None,
            pending_count: 0,
        }
    }

    /// Check if sync is configured and enabled.
    pub fn is_enabled(&self) -> bool {
        !self.config.supabase_url.is_empty() && !self.config.supabase_key.is_empty()
    }

    /// Get the sync interval as a Duration.
    pub fn interval(&self) -> Duration {
        Duration::from_secs(self.config.sync_interval_secs)
    }

    /// Placeholder for the sync cycle.
    /// In production, this would:
    /// 1. Query SQLite: SELECT * FROM epochs WHERE synced = 0 LIMIT batch_size
    /// 2. POST each row to Supabase REST API with JWT auth header
    /// 3. On success: UPDATE epochs SET synced = 1 WHERE id = ?
    /// 4. On failure: increment retry counter, back off exponentially
    pub async fn sync_cycle(&mut self) -> Result<u64, String> {
        if !self.is_enabled() {
            return Ok(0);
        }

        self.status = SyncStatus::Syncing;
        log::info!("Sync daemon: checking for unsynced rows...");

        // TODO: Implement actual HTTP sync when reqwest is added
        // For now, return 0 synced rows
        self.status = SyncStatus::Idle;
        Ok(0)
    }
}

// ── Unit Tests ─────────────────────────────────────────────────
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sync_disabled_without_credentials() {
        let daemon = SyncDaemon::new(SyncConfig::default());
        assert_eq!(daemon.status, SyncStatus::Disabled);
        assert!(!daemon.is_enabled());
    }

    #[test]
    fn test_sync_enabled_with_credentials() {
        let config = SyncConfig {
            supabase_url: "https://test.supabase.co".into(),
            supabase_key: "test-key".into(),
            ..Default::default()
        };
        let daemon = SyncDaemon::new(config);
        assert_eq!(daemon.status, SyncStatus::Idle);
        assert!(daemon.is_enabled());
    }

    #[test]
    fn test_sync_interval() {
        let config = SyncConfig {
            sync_interval_secs: 120,
            ..Default::default()
        };
        let daemon = SyncDaemon::new(config);
        assert_eq!(daemon.interval(), Duration::from_secs(120));
    }
}
