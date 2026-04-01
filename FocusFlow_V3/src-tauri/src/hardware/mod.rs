// ═══════════════════════════════════════════════════════════════
//  FocusFlow V3 — Hardware Abstraction Layer
//  This module defines the universal trait that ALL headset
//  connectors must implement. This is how we escape vendor lock-in.
// ═══════════════════════════════════════════════════════════════

pub mod muse;
pub mod openbci;

use serde::{Deserialize, Serialize};
use std::fmt;
use tokio::sync::mpsc;

// ── Channel Identifier ──────────────────────────────────────────
/// Represents individual EEG electrode positions.
/// This enum is hardware-agnostic: Muse uses 4 channels,
/// OpenBCI Cyton uses up to 8.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Channel {
    // Muse 2 channels
    TP9,
    AF7,
    AF8,
    TP10,
    // OpenBCI extended channels
    Fp1,
    Fp2,
    C3,
    C4,
    // Generic fallback
    Aux(u8),
}

impl fmt::Display for Channel {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Channel::TP9 => write!(f, "TP9"),
            Channel::AF7 => write!(f, "AF7"),
            Channel::AF8 => write!(f, "AF8"),
            Channel::TP10 => write!(f, "TP10"),
            Channel::Fp1 => write!(f, "Fp1"),
            Channel::Fp2 => write!(f, "Fp2"),
            Channel::C3 => write!(f, "C3"),
            Channel::C4 => write!(f, "C4"),
            Channel::Aux(n) => write!(f, "AUX{}", n),
        }
    }
}

// ── BrainChunk: The Universal Data Packet ───────────────────────
/// Every headset connector must emit data in this format.
/// The DSP pipeline only ever sees `BrainChunk` — it never knows
/// whether the data came from a Muse, OpenBCI, or Neurosity.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BrainChunk {
    /// Timestamp in microseconds since epoch (from `std::time::Instant`)
    pub timestamp_us: u64,

    /// Which electrode produced this data
    pub channel: Channel,

    /// EEG samples in microvolts (µV).
    /// Muse sends 12 samples per packet, OpenBCI sends 1-8.
    pub samples_uv: Vec<f64>,
}

// ── Headset Connection Status ───────────────────────────────────
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ConnectionStatus {
    Disconnected,
    Scanning,
    Connecting,
    Connected,
    Streaming,
    Error,
}

// ── Hardware Error Type ─────────────────────────────────────────
#[derive(Debug, Clone)]
pub enum HardwareError {
    NotFound(String),
    ConnectionFailed(String),
    StreamError(String),
    Timeout,
    Unsupported(String),
    BleError(String),
}

impl fmt::Display for HardwareError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            HardwareError::NotFound(msg) => write!(f, "Device not found: {}", msg),
            HardwareError::ConnectionFailed(msg) => write!(f, "Connection failed: {}", msg),
            HardwareError::StreamError(msg) => write!(f, "Stream error: {}", msg),
            HardwareError::Timeout => write!(f, "Operation timed out"),
            HardwareError::Unsupported(msg) => write!(f, "Unsupported: {}", msg),
            HardwareError::BleError(msg) => write!(f, "Bluetooth LE Error: {}", msg),
        }
    }
}

impl std::error::Error for HardwareError {}

// ═══════════════════════════════════════════════════════════════
//  THE CORE TRAIT: HeadsetProvider
//  ANY new headset connector (Muse, OpenBCI, Neurosity, etc.)
//  MUST implement this trait. The DSP engine only calls these
//  methods — it never touches hardware-specific code directly.
// ═══════════════════════════════════════════════════════════════
#[allow(async_fn_in_trait)]
pub trait HeadsetProvider: Send + Sync {
    /// Human-readable name of the headset (e.g., "Muse 2", "OpenBCI Cyton").
    fn name(&self) -> &str;

    /// The native sampling rate of this hardware in Hz.
    /// Muse 2 = 256, OpenBCI Cyton = 250, Neurosity Crown = 256.
    fn sample_rate(&self) -> u32;

    /// Number of EEG channels this device provides.
    /// Muse 2 = 4, OpenBCI Cyton = 8.
    fn channel_count(&self) -> usize;

    /// List of channels this device supports.
    fn channels(&self) -> Vec<Channel>;

    /// Scan for nearby devices and return their addresses/names.
    async fn scan(&self, timeout_secs: u64) -> Result<Vec<String>, HardwareError>;

    /// Connect to the headset (by MAC address or name).
    async fn connect(&self, device_id: &str) -> Result<(), HardwareError>;

    /// Disconnect from the headset.
    async fn disconnect(&self) -> Result<(), HardwareError>;

    /// Start streaming EEG data. Sends `BrainChunk` packets through
    /// the provided `mpsc::Sender`. The DSP pipeline listens on the
    /// receiving end of this channel.
    async fn stream(&self, tx: mpsc::Sender<BrainChunk>) -> Result<(), HardwareError>;

    /// Current connection status.
    fn status(&self) -> ConnectionStatus;
}
