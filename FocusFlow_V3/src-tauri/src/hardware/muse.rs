// ═══════════════════════════════════════════════════════════════
//  FocusFlow V3 — Muse 2 BLE Connector
//  Implements HeadsetProvider for the InteraXon Muse 2 headband.
//  Translated from V2.3 Python `muse_ble.py`.
// ═══════════════════════════════════════════════════════════════

#![allow(dead_code)]

use super::{BrainChunk, Channel, ConnectionStatus, HardwareError, HeadsetProvider};
use tokio::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};
use btleplug::api::{Central, Manager as _, Peripheral as _, ScanFilter, WriteType};
use btleplug::platform::{Manager, Peripheral, Adapter};
use futures::stream::StreamExt;
use std::time::Duration;
use uuid::Uuid;

// ── Muse 2 BLE Protocol Constants ──────────────────────────────
const MUSE_SERVICE_UUID: &str = "0000fe8d-0000-1000-8000-00805f9b34fb";
const CONTROL_UUID: &str = "273e0001-4c4d-454d-96be-f03bac821358";
const EEG_TP9_UUID:  &str = "273e0003-4c4d-454d-96be-f03bac821358";
const EEG_AF7_UUID:  &str = "273e0004-4c4d-454d-96be-f03bac821358";
const EEG_AF8_UUID:  &str = "273e0005-4c4d-454d-96be-f03bac821358";
const EEG_TP10_UUID: &str = "273e0006-4c4d-454d-96be-f03bac821358";

const CMD_START: &[u8] = &[0x02, 0x73, 0x0a];       // 's' Start streaming
const CMD_STOP:  &[u8] = &[0x02, 0x68, 0x0a];       // 'h' Stop streaming
const CMD_PRESET_P21: &[u8] = &[0x04, 0x70, 0x32, 0x31, 0x0a]; // 'p21'

// ── Packet Parser ──────────────────────────────────────────────
/// Parse a 20-byte Muse EEG notification into 12 samples (µV).
/// Format: 2-byte counter + 12 × 12-bit unsigned values (big-endian).
pub fn parse_eeg_packet(raw: &[u8]) -> Vec<f64> {
    if raw.len() < 20 {
        return vec![];
    }

    let mut samples = Vec::with_capacity(12);
    let mut bit_buffer: u64 = 0;
    let mut bits_in_buffer: u32 = 0;

    // Skip first 2 bytes (packet counter)
    for &byte_val in &raw[2..] {
        bit_buffer = (bit_buffer << 8) | byte_val as u64;
        bits_in_buffer += 8;

        while bits_in_buffer >= 12 {
            bits_in_buffer -= 12;
            let sample_raw = ((bit_buffer >> bits_in_buffer) & 0xFFF) as i32;
            // Convert 12-bit unsigned to microvolts
            // Center at 2048, scale by 0.48828125 µV/LSB
            let uv = (sample_raw - 2048) as f64 * 0.48828125;
            samples.push(uv);
        }
    }

    samples.truncate(12); // Exactly 12 samples per packet
    samples
}

// ── Muse Connector Struct ──────────────────────────────────────
pub struct MuseConnector {
    status: Arc<Mutex<ConnectionStatus>>,
    peripheral: Arc<tokio::sync::Mutex<Option<Peripheral>>>,
}

impl MuseConnector {
    pub fn new() -> Self {
        Self {
            status: Arc::new(Mutex::new(ConnectionStatus::Disconnected)),
            peripheral: Arc::new(tokio::sync::Mutex::new(None)),
        }
    }

    fn set_status(&self, s: ConnectionStatus) {
        if let Ok(mut status) = self.status.lock() {
            *status = s;
        }
    }

    fn now_us() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_micros() as u64
    }

    async fn get_central(&self) -> Result<Adapter, HardwareError> {
        let manager = Manager::new().await.map_err(|e| HardwareError::BleError(e.to_string()))?;
        let adapters = manager.adapters().await.map_err(|e| HardwareError::BleError(e.to_string()))?;
        adapters.into_iter().next().ok_or_else(|| HardwareError::BleError("No Bluetooth adapter found".into()))
    }
}

/// Parse a UUID string constant.
/// Uses .expect() instead of .unwrap() so that a typo in any BLE constant
/// produces a readable panic message pointing directly to this file,
/// rather than an opaque thread panic with no context.
fn parse_uuid(s: &str) -> Uuid {
    Uuid::parse_str(s)
        .unwrap_or_else(|e| panic!("Invalid UUID constant '{}' in muse.rs: {}", s, e))
}

impl HeadsetProvider for MuseConnector {
    fn name(&self) -> &str {
        "Muse 2"
    }

    fn sample_rate(&self) -> u32 {
        256 // Muse 2 native rate
    }

    fn channel_count(&self) -> usize {
        4 // TP9, AF7, AF8, TP10
    }

    fn channels(&self) -> Vec<Channel> {
        vec![Channel::TP9, Channel::AF7, Channel::AF8, Channel::TP10]
    }

    async fn scan(&self, timeout_secs: u64) -> Result<Vec<String>, HardwareError> {
        self.set_status(ConnectionStatus::Scanning);
        log::info!("Scanning for Muse 2 devices...");
        
        let central = self.get_central().await?;
        central.start_scan(ScanFilter { services: vec![parse_uuid(MUSE_SERVICE_UUID)] })
            .await
            .map_err(|e| HardwareError::BleError(e.to_string()))?;
        
        tokio::time::sleep(Duration::from_secs(timeout_secs)).await;
        
        let mut found_devices = Vec::new();
        for peripheral in central.peripherals().await.unwrap_or_default() {
            if let Ok(Some(props)) = peripheral.properties().await {
                if let Some(name) = props.local_name {
                    if name.starts_with("Muse-") {
                        found_devices.push(peripheral.id().to_string());
                    }
                }
            }
        }
        
        self.set_status(ConnectionStatus::Disconnected);
        Ok(found_devices)
    }

    async fn connect(&self, device_id: &str) -> Result<(), HardwareError> {
        self.set_status(ConnectionStatus::Connecting);
        log::info!("Connecting to Muse 2: {device_id}");
        
        let central = self.get_central().await?;
        let peripherals = central.peripherals().await.map_err(|e| HardwareError::BleError(e.to_string()))?;
        
        let mut target_peripheral = None;
        for p in peripherals {
            if p.id().to_string() == device_id {
                target_peripheral = Some(p);
                break;
            }
        }
        
        let peripheral = target_peripheral.ok_or_else(|| HardwareError::ConnectionFailed("Device not found".into()))?;
        
        peripheral.connect().await.map_err(|e| HardwareError::ConnectionFailed(e.to_string()))?;
        peripheral.discover_services().await.map_err(|e| HardwareError::ConnectionFailed(e.to_string()))?;
        
        let mut p_lock = self.peripheral.lock().await;
        *p_lock = Some(peripheral);
        
        self.set_status(ConnectionStatus::Connected);
        log::info!("Connected to Muse 2 successfully");
        Ok(())
    }

    async fn disconnect(&self) -> Result<(), HardwareError> {
        let mut p_lock = self.peripheral.lock().await;
        if let Some(peripheral) = p_lock.as_ref() {
            let _ = peripheral.disconnect().await;
        }
        *p_lock = None;
        self.set_status(ConnectionStatus::Disconnected);
        log::info!("Disconnected from Muse 2");
        Ok(())
    }

    async fn stream(&self, tx: mpsc::Sender<BrainChunk>) -> Result<(), HardwareError> {
        self.set_status(ConnectionStatus::Streaming);
        log::info!("Initializing Muse 2 streaming...");
        
        let p_lock = self.peripheral.lock().await;
        let peripheral = p_lock.as_ref().ok_or_else(|| HardwareError::ConnectionFailed("Not connected".into()))?;
        
        let chars = peripheral.characteristics();
        
        // 1. Subscribe to EEG characteristics
        let eeg_uuids = [
            parse_uuid(EEG_TP9_UUID), parse_uuid(EEG_AF7_UUID), 
            parse_uuid(EEG_AF8_UUID), parse_uuid(EEG_TP10_UUID)
        ];
        
        for uuid in &eeg_uuids {
            if let Some(c) = chars.iter().find(|c| c.uuid == *uuid) {
                peripheral.subscribe(c).await.map_err(|e| HardwareError::BleError(e.to_string()))?;
            }
        }
        
        // 2. Start streaming command
        let control_uuid = parse_uuid(CONTROL_UUID);
        if let Some(control_char) = chars.iter().find(|c| c.uuid == control_uuid) {
            peripheral.write(control_char, CMD_PRESET_P21, WriteType::WithoutResponse)
                .await.map_err(|e| HardwareError::BleError(e.to_string()))?;
            tokio::time::sleep(Duration::from_millis(100)).await;
            peripheral.write(control_char, CMD_START, WriteType::WithoutResponse)
                .await.map_err(|e| HardwareError::BleError(e.to_string()))?;
        } else {
            return Err(HardwareError::BleError("Control characteristic not found".into()));
        }
        
        // 3. Process incoming notifications
        let mut notification_stream = peripheral.notifications().await.map_err(|e| HardwareError::BleError(e.to_string()))?;
        
        log::info!("Muse 2 streaming started. Waiting for packets...");
        
        // Pre-parse UUIDs for reliable matching (avoid string formatting mismatches)
        let uuid_tp9  = parse_uuid(EEG_TP9_UUID);
        let uuid_af7  = parse_uuid(EEG_AF7_UUID);
        let uuid_af8  = parse_uuid(EEG_AF8_UUID);
        let uuid_tp10 = parse_uuid(EEG_TP10_UUID);
        
        // Spawn a task to handle the stream so we don't block
        let tx_clone = tx.clone();
        tokio::spawn(async move {
            while let Some(data) = notification_stream.next().await {
                let channel = if data.uuid == uuid_tp9 {
                    Channel::TP9
                } else if data.uuid == uuid_af7 {
                    Channel::AF7
                } else if data.uuid == uuid_af8 {
                    Channel::AF8
                } else if data.uuid == uuid_tp10 {
                    Channel::TP10
                } else {
                    continue;
                };
                
                let samples_uv = parse_eeg_packet(&data.value);
                if !samples_uv.is_empty() {
                    let chunk = BrainChunk {
                        timestamp_us: MuseConnector::now_us(),
                        channel,
                        samples_uv,
                    };
                    if tx_clone.send(chunk).await.is_err() {
                        break; // Receiver dropped, stop streaming
                    }
                }
            }
        });

        Ok(())
    }

    fn status(&self) -> ConnectionStatus {
        self.status.lock().map(|s| *s).unwrap_or(ConnectionStatus::Error)
    }
}

// ── Unit Tests ─────────────────────────────────────────────────
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_eeg_packet_length() {
        // A valid 20-byte Muse EEG packet should produce exactly 12 samples
        let fake_packet: Vec<u8> = vec![0u8; 20];
        let samples = parse_eeg_packet(&fake_packet);
        assert_eq!(samples.len(), 12);
    }

    #[test]
    fn test_parse_eeg_packet_too_short() {
        let short_packet: Vec<u8> = vec![0u8; 10];
        let samples = parse_eeg_packet(&short_packet);
        assert!(samples.is_empty());
    }

    #[test]
    fn test_muse_connector_metadata() {
        let muse = MuseConnector::new();
        assert_eq!(muse.name(), "Muse 2");
        assert_eq!(muse.sample_rate(), 256);
        assert_eq!(muse.channel_count(), 4);
        assert_eq!(muse.channels().len(), 4);
    }
}
