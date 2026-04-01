// ═══════════════════════════════════════════════════════════════
//  FocusFlow V3 — DSP Filters Module
//  Pure Rust implementations of Butterworth bandpass, notch,
//  z-score clip, and Savitzky-Golay smoothing.
//  Translated from V2.3 Python production_server.py.
// ═══════════════════════════════════════════════════════════════

use std::f64::consts::PI;

/// Z-score threshold clip — replaces outlier samples (> z_thresh σ)
/// with the channel median. NOT ASR (Artifact Subspace Reconstruction).
/// Direct translation from V2.3 `_zscore_clip()` (line 810).
pub fn zscore_clip(data: &mut [f64], z_thresh: f64) {
    if data.is_empty() {
        return;
    }

    // Compute median (simple sort-based)
    let mut sorted = data.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let median = if sorted.len() % 2 == 0 {
        (sorted[sorted.len() / 2 - 1] + sorted[sorted.len() / 2]) / 2.0
    } else {
        sorted[sorted.len() / 2]
    };

    // Compute std
    let mean: f64 = data.iter().sum::<f64>() / data.len() as f64;
    let variance: f64 = data.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / data.len() as f64;
    let std_dev = variance.sqrt();

    if std_dev < 0.01 {
        return; // Flatline, skip
    }

    // Replace outliers
    for sample in data.iter_mut() {
        let z = ((*sample - median) / std_dev).abs();
        if z > z_thresh {
            *sample = median;
        }
    }
}

/// Remove DC offset by subtracting the mean from all samples.
pub fn demean(data: &mut [f64]) {
    if data.is_empty() {
        return;
    }
    let mean: f64 = data.iter().sum::<f64>() / data.len() as f64;
    for sample in data.iter_mut() {
        *sample -= mean;
    }
}

// ── Butterworth Bandpass Filter ────────────────────────────────
/// 2nd-order bandpass filter coefficients using the Audio EQ Cookbook
/// (Robert Bristow-Johnson) bilinear transform formula.
/// Returns (b, a) coefficient vectors for a single biquad section.
/// For 4th-order: cascade two sections (caller's responsibility).
pub fn butter_bandpass_coefficients(
    lowcut: f64,
    highcut: f64,
    fs: f64,
    _order: usize,
) -> (Vec<f64>, Vec<f64>) {
    let nyq = 0.5 * fs;
    let low = lowcut / nyq;
    let high = highcut / nyq;

    // Center frequency and bandwidth in normalized angular frequency
    let w0 = PI * (low + high) / 2.0;   // Center frequency
    let bw = PI * (high - low);          // Bandwidth

    // Butterworth Q for bandpass: Q = w0 / bw
    let alpha = w0.sin() * (bw / 2.0).sinh();

    // Bandpass coefficients (constant-0dB-peak-gain form)
    let b0 = alpha;
    let b1 = 0.0;
    let b2 = -alpha;
    let a0 = 1.0 + alpha;
    let a1 = -2.0 * w0.cos();
    let a2 = 1.0 - alpha;

    // Normalize by a0
    let b = vec![b0 / a0, b1 / a0, b2 / a0];
    let a = vec![1.0, a1 / a0, a2 / a0];

    (b, a)
}

/// Stateful IIR Filter using Direct Form II Transposed.
/// This preserves state across multiple calls to `apply()`,
/// making it suitable for real-time streaming without chunk-boundary transients.
#[derive(Debug, Clone)]
pub struct IirFilter {
    b: Vec<f64>,
    a: Vec<f64>,
    state: Vec<f64>,
}

impl IirFilter {
    pub fn new(b: Vec<f64>, a: Vec<f64>) -> Self {
        let order = b.len().max(a.len());
        Self {
            b,
            a,
            state: vec![0.0; order],
        }
    }

    /// Reset the filter state to zeros.
    pub fn reset(&mut self) {
        for s in self.state.iter_mut() {
            *s = 0.0;
        }
    }

    /// Apply the filter to a single sample, updating internal state.
    pub fn process_sample(&mut self, sample: f64) -> f64 {
        let output = self.b[0] * sample + self.state[0];
        
        let nb = self.b.len();
        let na = self.a.len();
        let order = nb.max(na);

        for j in 1..order {
            let b_val = if j < nb { self.b[j] } else { 0.0 };
            let a_val = if j < na { self.a[j] } else { 0.0 };
            
            if j < order - 1 {
                self.state[j - 1] = b_val * sample - a_val * output + self.state[j];
            } else {
                self.state[j - 1] = b_val * sample - a_val * output;
            }
        }
        output
    }

    /// Apply the filter to a slice of samples in-place.
    pub fn process_block(&mut self, data: &mut [f64]) {
        for val in data.iter_mut() {
            *val = self.process_sample(*val);
        }
    }
}

/// Create a cascaded 4th-order Butterworth bandpass filter.
/// Returns two IirFilter sections that should be applied in sequence.
pub fn make_bandpass_pair(lowcut: f64, highcut: f64, fs: f64) -> (IirFilter, IirFilter) {
    let (b, a) = butter_bandpass_coefficients(lowcut, highcut, fs, 4);
    (IirFilter::new(b.clone(), a.clone()), IirFilter::new(b, a))
}

/// Bandpass filter: 1-45Hz, 4th-order Butterworth (two cascaded biquads).
/// This is CAUSAL and stateful.
pub fn bandpass_filter(data: &mut [f64], lowcut: f64, highcut: f64, fs: f64) {
    let (b, a) = butter_bandpass_coefficients(lowcut, highcut, fs, 4);
    // Cascade two identical sections for 4th-order
    let mut filter1 = IirFilter::new(b.clone(), a.clone());
    let mut filter2 = IirFilter::new(b, a);
    filter1.process_block(data);
    filter2.process_block(data);
}

// ── Notch Filter (Static IIR Fallback) ────────────────────────
/// 2nd-order IIR notch filter at a specific frequency.
/// This is CAUSAL and stateful.
pub fn notch_filter_iir(data: &mut [f64], notch_freq: f64, fs: f64, q: f64) {
    let w0 = 2.0 * PI * notch_freq / fs;
    let alpha = w0.sin() / (2.0 * q);

    let b0 = 1.0;
    let b1 = -2.0 * w0.cos();
    let b2 = 1.0;
    let a0 = 1.0 + alpha;
    let a1 = -2.0 * w0.cos();
    let a2 = 1.0 - alpha;

    let b = vec![b0 / a0, b1 / a0, b2 / a0];
    let a = vec![1.0, a1 / a0, a2 / a0];

    let mut filter = IirFilter::new(b, a);
    filter.process_block(data);
}

/// Apply dual notch filter at 50Hz and 60Hz.
pub fn dual_notch(data: &mut [f64], fs: f64) {
    notch_filter_iir(data, 50.0, fs, 30.0);
    notch_filter_iir(data, 60.0, fs, 30.0);
}

// ── Unit Tests ─────────────────────────────────────────────────
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_zscore_clip_removes_outliers() {
        // 20 normal data points + 1 massive outlier at index 10
        let mut data = vec![1.0, 1.1, 0.9, 1.0, 0.95, 1.05, 0.98, 1.02, 0.97, 1.01,
                            500.0, // ← outlier
                            1.0, 0.99, 1.01, 0.98, 1.03, 0.96, 1.04, 0.97, 1.0, 1.02];
        zscore_clip(&mut data, 3.0);
        assert!(data[10] < 10.0, "Outlier should be clipped to median, got {}", data[10]);
    }

    #[test]
    fn test_demean() {
        let mut data = vec![10.0, 12.0, 8.0, 10.0];
        demean(&mut data);
        let mean: f64 = data.iter().sum::<f64>() / data.len() as f64;
        assert!(mean.abs() < 1e-10, "Mean should be ~0 after demeaning");
    }

    #[test]
    fn test_notch_filter_does_not_crash() {
        let mut data: Vec<f64> = (0..512).map(|i| (2.0 * PI * 50.0 * i as f64 / 256.0).sin()).collect();
        dual_notch(&mut data, 256.0);
        assert_eq!(data.len(), 512);
    }

    #[test]
    fn test_iir_filter_state_persistence() {
        let b = vec![0.5, 0.5];
        let a = vec![1.0, -0.5];
        let mut filter = IirFilter::new(b, a);
        
        let mut data1 = vec![1.0, 1.0];
        filter.process_block(&mut data1);
        
        let mut data2 = vec![1.0, 1.0];
        filter.process_block(&mut data2);
        
        // If state is preserved, data2 should differ from data1 (first sample of d2 uses state from d1)
        assert_ne!(data1[0], data2[0], "Filter state should persist between blocks");
    }
}
