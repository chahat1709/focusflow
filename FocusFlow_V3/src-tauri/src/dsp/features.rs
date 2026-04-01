// ═══════════════════════════════════════════════════════════════
//  FocusFlow V3 — Feature Extraction (Welch PSD + IAF + TBR)
//  Translated from V2.3 production_server.py.
//  Uses rustfft with nfft=1024 for 0.25Hz resolution (V2.3 Fix #4).
// ═══════════════════════════════════════════════════════════════

use rustfft::{FftPlanner, num_complex::Complex};

/// Welch PSD estimate using Hanning window and nfft=1024.
/// V2.3 Fix #4: 0.25Hz bin resolution (256Hz / 1024 = 0.25Hz).
/// Returns (frequencies, psd_values).
pub fn welch_psd(data: &[f64], fs: f64, nfft: usize) -> (Vec<f64>, Vec<f64>) {
    let n = data.len();
    if n == 0 {
        return (vec![], vec![]);
    }

    // Hanning window
    let window: Vec<f64> = (0..n)
        .map(|i| 0.5 * (1.0 - (2.0 * std::f64::consts::PI * i as f64 / (n as f64 - 1.0)).cos()))
        .collect();

    // Apply window
    let windowed: Vec<f64> = data.iter().zip(window.iter()).map(|(&d, &w)| d * w).collect();

    // Zero-pad to nfft
    let mut padded = vec![Complex::new(0.0_f64, 0.0_f64); nfft];
    for (i, &val) in windowed.iter().enumerate() {
        if i < nfft {
            padded[i] = Complex::new(val, 0.0);
        }
    }

    // FFT
    let mut planner = FftPlanner::<f64>::new();
    let fft = planner.plan_fft_forward(nfft);
    fft.process(&mut padded);

    // Compute one-sided PSD
    let n_freqs = nfft / 2 + 1;
    let window_power: f64 = window.iter().map(|w| w * w).sum::<f64>();
    let scale = 2.0 / (fs * window_power + 1e-10);

    let frequencies: Vec<f64> = (0..n_freqs).map(|i| i as f64 * fs / nfft as f64).collect();
    let psd: Vec<f64> = padded[..n_freqs]
        .iter()
        .map(|c| (c.re * c.re + c.im * c.im) * scale)
        .collect();

    (frequencies, psd)
}

/// Compute band power from PSD for a given frequency range.
pub fn band_power(psd: &[f64], freqs: &[f64], low: f64, high: f64) -> f64 {
    freqs.iter().zip(psd.iter())
        .filter(|(&f, _)| f >= low && f <= high)
        .map(|(_, &p)| p)
        .sum()
}

/// Find Individual Alpha Frequency (IAF) — the peak within 7-13Hz.
/// V2.3 Fix #4: With nfft=1024, resolution is 0.25Hz, allowing smooth
/// IAF tracking instead of 1Hz jumps.
pub fn find_iaf(freqs: &[f64], psd: &[f64]) -> f64 {
    let mut max_power = 0.0_f64;
    let mut iaf = 10.0_f64; // Default IAF

    for (&f, &p) in freqs.iter().zip(psd.iter()) {
        if f >= 7.0 && f <= 13.0 && p > max_power {
            max_power = p;
            iaf = f;
        }
    }

    iaf
}

/// Get IAF-personalized frequency band boundaries.
/// Shifts alpha/theta/beta bands relative to the detected IAF.
pub fn get_iaf_bands(iaf: f64) -> super::FrequencyBands {
    super::FrequencyBands {
        delta: (0.5, (iaf - 6.0).max(2.0)),
        theta: ((iaf - 6.0).max(2.0), iaf - 2.0),
        alpha: (iaf - 2.0, iaf + 2.0),
        beta:  (iaf + 2.0, 30.0),
        gamma: (30.0, 50.0),
    }
}

/// Compute Theta/Beta Ratio (TBR) — clinically validated for attention.
/// High TBR = inattention. We use 1/TBR as the engagement score.
/// V2.3 Fix #9: If EMG detected, TBR is invalidated (returns 0.0).
pub fn compute_tbr(theta_power: f64, beta_power: f64, emg_detected: bool) -> f64 {
    if emg_detected {
        return 0.0; // Invalidated: muscle contamination
    }
    if beta_power > 0.001 {
        theta_power / beta_power
    } else {
        0.0
    }
}

/// Convert TBR to focus metric via Z-score normalization.
/// Z ∈ [-2, +6] SD → Focus ∈ [0, 0.95].
pub fn tbr_to_focus(raw_ratio: f64, baseline_mean: f64, baseline_std: f64) -> f64 {
    if baseline_std < 0.001 {
        return 0.0;
    }
    let z = (raw_ratio - baseline_mean) / baseline_std;
    // Z=0 → 25% (baseline), Z=+2 → 50%, Z=+4 → 75%, Z=+6 → 95%
    let focus = (z + 2.0) / 8.0;
    focus.clamp(0.0, 0.95)
}

// ── Unit Tests ─────────────────────────────────────────────────
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_welch_psd_output_length() {
        let data: Vec<f64> = (0..256).map(|i| (2.0 * std::f64::consts::PI * 10.0 * i as f64 / 256.0).sin()).collect();
        let (freqs, psd) = welch_psd(&data, 256.0, 1024);
        assert_eq!(freqs.len(), 513); // nfft/2 + 1
        assert_eq!(psd.len(), 513);
        // Frequency resolution should be 0.25Hz
        assert!((freqs[1] - freqs[0] - 0.25).abs() < 0.01);
    }

    #[test]
    fn test_find_iaf_detects_10hz_peak() {
        let freqs: Vec<f64> = (0..513).map(|i| i as f64 * 0.25).collect();
        let mut psd = vec![0.1_f64; 513];
        // Place a peak at 10Hz (index = 10/0.25 = 40)
        psd[40] = 10.0;
        let iaf = find_iaf(&freqs, &psd);
        assert!((iaf - 10.0).abs() < 0.5, "IAF should be ~10Hz, got {}", iaf);
    }

    #[test]
    fn test_tbr_invalidated_by_emg() {
        let tbr = compute_tbr(5.0, 2.0, true);
        assert_eq!(tbr, 0.0, "TBR should be 0 when EMG detected");
    }

    #[test]
    fn test_focus_metric_range() {
        let focus = tbr_to_focus(0.5, 0.3, 0.1);
        assert!(focus >= 0.0 && focus <= 0.95, "Focus should be in [0, 0.95]");
    }
}
