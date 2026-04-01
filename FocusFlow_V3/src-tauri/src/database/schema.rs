// ═══════════════════════════════════════════════════════════════
//  FocusFlow V3 — SQLite Local Schema
//  Creates the offline-first database in %LocalAppData%/FocusFlow/
//  All DSP output writes here FIRST before syncing to Supabase.
// ═══════════════════════════════════════════════════════════════

/// SQL statements for creating the local SQLite schema.
/// These mirror the Supabase Postgres tables but with an extra
/// `synced` column to track which rows have been uploaded.

pub const CREATE_ORGANIZATIONS_TABLE: &str = r#"
    CREATE TABLE IF NOT EXISTS organizations (
        id          TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );
"#;

pub const CREATE_USERS_TABLE: &str = r#"
    CREATE TABLE IF NOT EXISTS users (
        id              TEXT PRIMARY KEY,
        organization_id TEXT REFERENCES organizations(id),
        email           TEXT,
        display_name    TEXT,
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );
"#;

pub const CREATE_SESSIONS_TABLE: &str = r#"
    CREATE TABLE IF NOT EXISTS sessions (
        id              TEXT PRIMARY KEY,
        user_id         TEXT NOT NULL REFERENCES users(id),
        organization_id TEXT REFERENCES organizations(id),
        started_at      TEXT NOT NULL,
        ended_at        TEXT,
        headset_type    TEXT NOT NULL,
        sample_rate     INTEGER NOT NULL,
        synced          INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );
"#;

pub const CREATE_EPOCHS_TABLE: &str = r#"
    CREATE TABLE IF NOT EXISTS epochs (
        id              TEXT PRIMARY KEY,
        session_id      TEXT NOT NULL REFERENCES sessions(id),
        epoch_number    INTEGER NOT NULL,
        timestamp       TEXT NOT NULL,
        focus_metric    REAL NOT NULL DEFAULT 0.0,
        tbr             REAL NOT NULL DEFAULT 0.0,
        deep_focus_cfc  REAL NOT NULL DEFAULT 0.0,
        emg_detected    INTEGER NOT NULL DEFAULT 0,
        headband_on     INTEGER NOT NULL DEFAULT 1,
        delta_power     REAL NOT NULL DEFAULT 0.0,
        theta_power     REAL NOT NULL DEFAULT 0.0,
        alpha_power     REAL NOT NULL DEFAULT 0.0,
        beta_power      REAL NOT NULL DEFAULT 0.0,
        gamma_power     REAL NOT NULL DEFAULT 0.0,
        mind_state      TEXT NOT NULL DEFAULT 'Neutral',
        synced          INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );
"#;

/// Supabase Row-Level Security (RLS) policies.
/// These are applied on the Supabase Postgres dashboard to enforce
/// multi-tenant data isolation.
///
/// Example SQL to run in the Supabase SQL Editor:
///
/// ```sql
/// -- Enable RLS on all tables
/// ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
/// ALTER TABLE epochs ENABLE ROW LEVEL SECURITY;
///
/// -- Policy: Users can only see sessions from their own organization
/// CREATE POLICY "Isolate by Organization" ON sessions
///     FOR ALL
///     USING (organization_id = (auth.jwt() ->> 'org_id')::text);
///
/// -- Policy: Users can only see epochs from their own sessions
/// CREATE POLICY "Isolate Epochs by Org" ON epochs
///     FOR ALL
///     USING (
///         session_id IN (
///             SELECT id FROM sessions
///             WHERE organization_id = (auth.jwt() ->> 'org_id')::text
///         )
///     );
///
/// -- Policy: Organization admins can see all org data
/// CREATE POLICY "Admin Full Access" ON sessions
///     FOR ALL
///     USING (
///         auth.jwt() ->> 'role' = 'admin'
///         AND organization_id = (auth.jwt() ->> 'org_id')::text
///     );
/// ```
pub const SUPABASE_RLS_DOCUMENTATION: &str = "See comments above for RLS SQL policies";

/// All table creation statements in order.
pub const ALL_TABLES: &[&str] = &[
    CREATE_ORGANIZATIONS_TABLE,
    CREATE_USERS_TABLE,
    CREATE_SESSIONS_TABLE,
    CREATE_EPOCHS_TABLE,
];
