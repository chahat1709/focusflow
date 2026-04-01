// ═══════════════════════════════════════════════════════════════
//  FocusFlow V3 — OpenBCI Cyton Connector
//  Implements HeadsetProvider for the OpenBCI Cyton board.
//  Reads 8-channel EEG data over USB Serial (250 Hz).
// ═══════════════════════════════════════════════════════════════

use super::{BrainChunk, Channel, ConnectionStatus, HardwareError, HeadsetProvider};
use tokio::sync::mpsc;
use std::sync::{Arc, Mutex};

pub struct OpenBCIConnector {
    status: Arc<Mutex<ConnectionStatus>>,
    port_name: Arc<Mutex<Option<String>>>,
}

impl OpenBCIConnector {
    pub fn new() -> Self {
        Self {
            status: Arc::new(Mutex::new(ConnectionStatus::Disconnected)),
            port_name: Arc::new(Mutex::new(None)),
        }
    }

    fn set_status(&self, s: ConnectionStatus) {
        if let Ok(mut status) = self.status.lock() {
            *status = s;
        }
    }
}

impl HeadsetProvider for OpenBCIConnector {
    fn name(&self) -> &str {
        "OpenBCI Cyton"
    }

    fn sample_rate(&self) -> u32 {
        250 // OpenBCI Cyton native rate
    }

    fn channel_count(&self) -> usize {
        8
    }

    fn channels(&self) -> Vec<Channel> {
        vec![
            Channel::Fp1, Channel::Fp2,
            Channel::C3,  Channel::C4,
            Channel::TP9, Channel::TP10,
            Channel::AF7, Channel::AF8,
        ]
    }

    async fn scan(&self, _timeout_secs: u64) -> Result<Vec<String>, HardwareError> {
        self.set_status(ConnectionStatus::Scanning);
        // TODO: Use `serialport::available_ports()` to find OpenBCI dongles
        log::info!("Scanning for OpenBCI Cyton serial ports...");
        Err(HardwareError::Unsupported(
            "Serial port scan not yet wired — Phase 1 scaffold".into(),
        ))
    }

    async fn connect(&self, device_id: &str) -> Result<(), HardwareError> {
        self.set_status(ConnectionStatus::Connecting);
        log::info!("Connecting to OpenBCI Cyton on port: {device_id}");
        if let Ok(mut port) = self.port_name.lock() {
            *port = Some(device_id.to_string());
        }
        // TODO: Open serial port at 115200 baud, send 'b' to start streaming
        Err(HardwareError::Unsupported(
            "Serial connect not yet wired — Phase 1 scaffold".into(),
        ))
    }

    async fn disconnect(&self) -> Result<(), HardwareError> {
        self.set_status(ConnectionStatus::Disconnected);
        // TODO: Send 's' to stop streaming, close serial port
        log::info!("Disconnected from OpenBCI Cyton");
        Ok(())
    }

    async fn stream(&self, _tx: mpsc::Sender<BrainChunk>) -> Result<(), HardwareError> {
        self.set_status(ConnectionStatus::Streaming);
        // TODO: Read 33-byte OpenBCI packets from serial, parse 24-bit ADC values,
        //       convert to µV, and send as BrainChunks
        log::info!("OpenBCI Cyton streaming started");
        Err(HardwareError::Unsupported(
            "Serial stream not yet wired — Phase 1 scaffold".into(),
        ))
    }

    fn status(&self) -> ConnectionStatus {
        self.status.lock().map(|s| *s).unwrap_or(ConnectionStatus::Error)
    }
}
