// ═══════════════════════════════════════════════════════════════
//  FocusFlow V3 — Sleep Staging Pipeline (NEW Feature)
//  Step 8 of the implementation plan.
//
//  Clinical sleep staging uses 30-second epochs (AASM standard).
//  This module buffers incoming BrainChunks and classifies each
//  epoch into: Wake, N1, N2, N3 (Deep), or REM.
// ═══════════════════════════════════════════════════════════════

use serde::{Deserialize, Serialize};
use super::features;

/// Sleep stage classification (AASM standard).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SleepStage {
    Wake,
    N1,   // Light drowsiness
    N2,   // Light sleep (spindles present)
    N3,   // Deep sleep (delta dominant)
    REM,  // Rapid eye movement (dreaming)
    Unknown,
}

impl std::fmt::Display for SleepStage {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SleepStage::Wake => write!(f, "Wake"),
            SleepStage::N1 => write!(f, "N1"),
            SleepStage::N2 => write!(f, "N2"),
            SleepStage::N3 => write!(f, "N3"),
            SleepStage::REM => write!(f, "REM"),
            SleepStage::Unknown => write!(f, "Unknown"),
        }
    }
}

/// Result of classifying a single 30-second epoch.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EpochResult {
    pub epoch_number: u32,
    pub stage: SleepStage,
    pub delta_ratio: f64,    // % of power in 0.5-4Hz
    pub theta_ratio: f64,    // % of power in 4-8Hz
    pub alpha_ratio: f64,    // % of power in 8-13Hz
    pub beta_ratio: f64,     // % of power in 13-30Hz
    pub spindle_detected: bool,
    pub rem_detected: bool,
}

/// The rolling 30-second epoch buffer.
/// Accumulates samples until a full epoch (30s * sample_rate) is ready.
pub struct SleepPipeline {
    buffer: Vec<f64>,
    frontal_buffer: Vec<f64>,  // AF7/AF8 for REM detection
    sample_rate: u32,
    epoch_size: usize,         // 30 * sample_rate
    epoch_count: u32,
}

impl SleepPipeline {
    pub fn new(sample_rate: u32) -> Self {
        let epoch_size = 30 * sample_rate as usize; // 30s * 256Hz = 7680 samples
        Self {
            buffer: Vec::with_capacity(epoch_size),
            frontal_buffer: Vec::with_capacity(epoch_size),
            sample_rate,
            epoch_size,
            epoch_count: 0,
        }
    }

    /// Push new EEG samples into the buffer.
    pub fn push_samples(&mut self, temporal_samples: &[f64], frontal_samples: &[f64]) {
        self.buffer.extend_from_slice(temporal_samples);
        self.frontal_buffer.extend_from_slice(frontal_samples);
    }

    /// Check if a full 30-second epoch is ready.
    pub fn epoch_ready(&self) -> bool {
        self.buffer.len() >= self.epoch_size
    }

    /// Classify the current epoch and drain the buffer.
    /// Returns None if not enough data yet.
    pub fn classify_epoch(&mut self) -> Option<EpochResult> {
        if !self.epoch_ready() {
            return None;
        }

        // Extract exactly one epoch worth of data
        let epoch_data: Vec<f64> = self.buffer.drain(..self.epoch_size).collect();
        let frontal_data: Vec<f64> = if self.frontal_buffer.len() >= self.epoch_size {
            self.frontal_buffer.drain(..self.epoch_size).collect()
        } else {
            vec![0.0; self.epoch_size]
        };

        self.epoch_count += 1;

        // Compute PSD for this epoch
        let (freqs, psd) = features::welch_psd(&epoch_data, self.sample_rate as f64, 1024);

        // Band powers
        let delta_p = features::band_power(&psd, &freqs, 0.5, 4.0);
        let theta_p = features::band_power(&psd, &freqs, 4.0, 8.0);
        let alpha_p = features::band_power(&psd, &freqs, 8.0, 13.0);
        let beta_p  = features::band_power(&psd, &freqs, 13.0, 30.0);
        let total = delta_p + theta_p + alpha_p + beta_p + 1e-10;

        let delta_ratio = delta_p / total;
        let theta_ratio = theta_p / total;
        let alpha_ratio = alpha_p / total;
        let beta_ratio  = beta_p / total;

        // Sleep spindle detection (11-16Hz micro-bursts ~0.5s)
        let spindle_power = features::band_power(&psd, &freqs, 11.0, 16.0);
        let spindle_detected = spindle_power / total > 0.08; // >8% of total = spindle present

        // REM detection: high-frequency eye movement on frontal channels
        let frontal_std = std_dev(&frontal_data);
        let frontal_mean = frontal_data.iter().sum::<f64>() / frontal_data.len() as f64;
        let rapid_movements = frontal_data.iter()
            .filter(|&&v| (v - frontal_mean).abs() > 2.5 * frontal_std)
            .count();
        let rem_detected = rapid_movements > (self.epoch_size / 20); // >5% of samples = REM

        // Classification logic (AASM-inspired heuristics)
        let stage = if alpha_ratio > 0.35 || beta_ratio > 0.30 {
            SleepStage::Wake
        } else if delta_ratio > 0.20 {
            SleepStage::N3  // Deep sleep: >20% delta
        } else if spindle_detected && delta_ratio < 0.20 {
            SleepStage::N2  // Light sleep with spindles
        } else if rem_detected && alpha_ratio < 0.15 {
            SleepStage::REM // REM: low alpha + rapid eye movements
        } else if theta_ratio > 0.30 {
            SleepStage::N1  // Drowsiness: theta dominant
        } else {
            SleepStage::Unknown
        };

        Some(EpochResult {
            epoch_number: self.epoch_count,
            stage,
            delta_ratio,
            theta_ratio,
            alpha_ratio,
            beta_ratio,
            spindle_detected,
            rem_detected,
        })
    }
}

fn std_dev(data: &[f64]) -> f64 {
    if data.is_empty() { return 1.0; }
    let mean = data.iter().sum::<f64>() / data.len() as f64;
    let var = data.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / data.len() as f64;
    var.sqrt().max(1e-10)
}

// ── Unit Tests ─────────────────────────────────────────────────
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_epoch_size_at_256hz() {
        let pipeline = SleepPipeline::new(256);
        assert_eq!(pipeline.epoch_size, 7680); // 30s * 256Hz
    }

    #[test]
    fn test_epoch_not_ready_until_full() {
        let mut pipeline = SleepPipeline::new(256);
        pipeline.push_samples(&vec![0.0; 1000], &vec![0.0; 1000]);
        assert!(!pipeline.epoch_ready());
    }

    #[test]
    fn test_epoch_classifies_when_full() {
        let mut pipeline = SleepPipeline::new(256);
        // Push exactly 30s of data (7680 samples)
        let temporal = vec![0.5; 7680];
        let frontal = vec![0.5; 7680];
        pipeline.push_samples(&temporal, &frontal);
        assert!(pipeline.epoch_ready());

        let result = pipeline.classify_epoch();
        assert!(result.is_some());
        assert_eq!(result.unwrap().epoch_number, 1);
    }

    #[test]
    fn test_deep_sleep_detection() {
        let mut pipeline = SleepPipeline::new(256);
        // Generate a 2Hz delta wave (deep sleep signature)
        let temporal: Vec<f64> = (0..7680)
            .map(|i| (2.0 * std::f64::consts::PI * 2.0 * i as f64 / 256.0).sin() * 50.0)
            .collect();
        let frontal = vec![0.0; 7680];
        pipeline.push_samples(&temporal, &frontal);

        let result = pipeline.classify_epoch().unwrap();
        assert_eq!(result.stage, SleepStage::N3, "Pure delta wave should classify as N3 (Deep Sleep)");
        assert!(result.delta_ratio > 0.20, "Delta ratio should be >20%");
    }
}
