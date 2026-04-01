// ═══════════════════════════════════════════════════════════════
//  FocusFlow V3 — Artifact Detection Suite (Rust)
//  Translated from V2.3 production_server.py:
//    - EMG Cross-Correlation (line 882)
//    - Blink Detector (line 901)
//    - Powerline Antenna Check (line 1142)
//    - IMU Motion Mask (line 833)
// ═══════════════════════════════════════════════════════════════

/// Result of EMG detection.
/// V2.3 Fix #9: Muscle-Beta "Fake Focus" prevention.
pub struct EmgResult {
    pub emg_detected: bool,
    pub avg_emg: f64,
    pub avg_beta_high: f64,
}

/// V2.3 Fix #9: EMG-Beta cross-correlation check.
/// Checks for simultaneous spike in 20-30Hz (Beta) AND 40-100Hz (pure EMG).
/// If both spike together, the Beta band is actually EMG bleed from jaw
/// clenching — flag as EMG and invalidate TBR for this chunk.
/// Direct translation from V2.3 `_detect_emg()` (line 882).
pub fn detect_emg(psd: &[f64], freqs: &[f64]) -> EmgResult {
    // Pure EMG band (40-100Hz)
    let emg_values: Vec<f64> = freqs.iter().zip(psd.iter())
        .filter(|(&f, _)| f >= 40.0 && f <= 100.0)
        .map(|(_, &p)| p)
        .collect();

    // Beta-EMG bleed zone (20-30Hz)
    let beta_high_values: Vec<f64> = freqs.iter().zip(psd.iter())
        .filter(|(&f, _)| f >= 20.0 && f <= 30.0)
        .map(|(_, &p)| p)
        .collect();

    if emg_values.is_empty() || beta_high_values.is_empty() {
        return EmgResult {
            emg_detected: false,
            avg_emg: 0.0,
            avg_beta_high: 0.0,
        };
    }

    let avg_emg: f64 = emg_values.iter().sum::<f64>() / emg_values.len() as f64;
    let avg_beta_high: f64 = beta_high_values.iter().sum::<f64>() / beta_high_values.len() as f64;

    // Cross-correlation: if both EMG and Beta-high are elevated simultaneously
    let emg_detected = if avg_emg > 1.5 && avg_beta_high > avg_emg * 0.6 {
        true // Jaw clench: invalidate TBR
    } else {
        avg_emg > 2.5 // Legacy: pure high-frequency EMG alone
    };

    EmgResult {
        emg_detected,
        avg_emg,
        avg_beta_high,
    }
}

/// Blink zone: start and end sample indices to exclude.
#[derive(Debug, Clone)]
pub struct BlinkZone {
    pub start: usize,
    pub end: usize,
}

/// Persistent state for the adaptive blink detector.
pub struct BlinkDetectorState {
    pub running_std: f64,
}

impl BlinkDetectorState {
    pub fn new() -> Self {
        Self { running_std: 50.0 } // Initial conservative estimate
    }
}

/// V2.3 Blink detector with relative threshold (3× running std).
/// Adapts to subject-specific impedance instead of using a fixed 100µV.
/// Direct translation from V2.3 `_detect_blinks()` (line 901).
pub fn detect_blinks(
    af7_data: &[f64],
    af8_data: &[f64],
    state: &mut BlinkDetectorState,
) -> Vec<BlinkZone> {
    let mut blink_zones = Vec::new();
    let n = af7_data.len().min(af8_data.len());
    if n == 0 {
        return blink_zones;
    }

    // Combined frontal channel amplitude
    let combined: Vec<f64> = (0..n)
        .map(|i| (af7_data[i].abs() + af8_data[i].abs()) / 2.0)
        .collect();

    // Update running std with EMA (adapts to each subject)
    let current_std = std_dev(&combined);
    state.running_std = 0.95 * state.running_std + 0.05 * current_std;
    let threshold = (30.0_f64).max(3.0 * state.running_std); // Floor at 30µV

    let mut in_blink = false;
    let mut start: usize = 0;

    for i in 0..n {
        if combined[i] > threshold && !in_blink {
            start = if i >= 25 { i - 25 } else { 0 }; // 100ms before
            in_blink = true;
        } else if combined[i] < threshold * 0.5 && in_blink {
            let end = (i + 25).min(n); // 100ms after
            blink_zones.push(BlinkZone { start, end });
            in_blink = false;
        }
    }

    if in_blink {
        blink_zones.push(BlinkZone { start, end: n });
    }

    blink_zones
}

/// V2.3 Fix #7: Powerline-ratio headband detection.
/// When an electrode lifts off the skin, it turns into an RF antenna,
/// picking up massive 50/60Hz from the room's wiring.
/// If >60% of the total PSD power is in 48-52Hz or 58-62Hz bins,
/// the headband is off the head.
/// Direct translation from V2.3 (line 1142).
pub fn powerline_antenna_check(psd: &[f64], freqs: &[f64]) -> bool {
    if psd.is_empty() || freqs.is_empty() {
        return true; // Assume off-head if no data
    }

    let total_power: f64 = psd.iter().sum();
    if total_power < 1e-10 {
        return true;
    }

    // Sum power in the 48-52Hz and 58-62Hz bands
    let pline_power: f64 = freqs.iter().zip(psd.iter())
        .filter(|(&f, _)| (f >= 48.0 && f <= 52.0) || (f >= 58.0 && f <= 62.0))
        .map(|(_, &p)| p)
        .sum();

    let ratio = pline_power / (total_power + 1e-10);

    // >60% powerline energy = electrode off-head (antenna mode)
    ratio > 0.60
}

/// IMU motion mask: returns a boolean vector where `true` = safe sample.
/// Flags samples where movement magnitude exceeds median + 3*std.
/// Direct translation from V2.3 `_imu_motion_mask()` (line 833).
pub fn imu_motion_mask(imu_magnitudes: &[f64]) -> Vec<bool> {
    let n = imu_magnitudes.len();
    if n < 2 {
        return vec![true; n];
    }

    let median = sorted_median(imu_magnitudes);
    let std = std_dev(imu_magnitudes);
    let threshold = median + 3.0 * std;

    imu_magnitudes.iter().map(|&m| m <= threshold).collect()
}

// ── Helper Functions ───────────────────────────────────────────

fn std_dev(data: &[f64]) -> f64 {
    if data.is_empty() {
        return 0.0;
    }
    let mean: f64 = data.iter().sum::<f64>() / data.len() as f64;
    let variance: f64 = data.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / data.len() as f64;
    variance.sqrt()
}

fn sorted_median(data: &[f64]) -> f64 {
    let mut sorted = data.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    if sorted.len() % 2 == 0 {
        (sorted[sorted.len() / 2 - 1] + sorted[sorted.len() / 2]) / 2.0
    } else {
        sorted[sorted.len() / 2]
    }
}

// ── Unit Tests ─────────────────────────────────────────────────
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_emg_cross_correlation_detects_jaw_clench() {
        // Simulate PSD where both EMG band and Beta-high spike together
        let freqs: Vec<f64> = (0..128).map(|i| i as f64).collect();
        let mut psd = vec![0.1_f64; 128];
        // Spike ACROSS the entire Beta-high band (20-30Hz) — simulates muscle bleed
        for i in 20..=30 {
            psd[i] = 5.0;
        }
        // Spike ACROSS the entire EMG band (40-100Hz) — simulates jaw clench
        for i in 40..=100 {
            psd[i] = 4.0;
        }

        let result = detect_emg(&psd, &freqs);
        assert!(result.emg_detected, "Should detect EMG from cross-correlation");
    }

    #[test]
    fn test_emg_no_false_positive_on_clean_signal() {
        let freqs: Vec<f64> = (0..128).map(|i| i as f64).collect();
        let psd = vec![0.1_f64; 128]; // Low, uniform power

        let result = detect_emg(&psd, &freqs);
        assert!(!result.emg_detected, "Should not flag clean signal as EMG");
    }

    #[test]
    fn test_powerline_antenna_detects_off_head() {
        let freqs: Vec<f64> = (0..128).map(|i| i as f64).collect();
        let mut psd = vec![0.01_f64; 128];
        // Massive 50Hz spike (electrode off-head, acting as antenna)
        psd[50] = 100.0;

        assert!(powerline_antenna_check(&psd, &freqs), "Should detect antenna mode");
    }

    #[test]
    fn test_powerline_passes_on_head() {
        let freqs: Vec<f64> = (0..128).map(|i| i as f64).collect();
        let psd = vec![1.0_f64; 128]; // Even power distribution

        assert!(!powerline_antenna_check(&psd, &freqs), "Should pass when on-head");
    }

    #[test]
    fn test_blink_detector_finds_spikes() {
        let mut af7 = vec![5.0_f64; 256];
        let mut af8 = vec![5.0_f64; 256];
        // Insert a massive blink artifact at samples 100-120
        for i in 100..120 {
            af7[i] = 500.0;
            af8[i] = 500.0;
        }
        let mut state = BlinkDetectorState::new();
        let zones = detect_blinks(&af7, &af8, &mut state);
        assert!(!zones.is_empty(), "Should detect at least one blink zone");
    }

    #[test]
    fn test_imu_motion_mask() {
        let mut magnitudes = vec![0.1_f64; 512];
        // Insert a head movement spike
        magnitudes[200] = 5.0;
        let mask = imu_motion_mask(&magnitudes);
        assert!(!mask[200], "Motion spike should be masked");
        assert!(mask[100], "Quiet sample should pass");
    }
}
