// ═══════════════════════════════════════════════════════════════
//  FocusFlow V3 — NLMS Adaptive Notch Filter (Rust)
//  Direct translation of V2.3 `_nlms_adaptive_kernel()` (line 45).
//  This is the mathematical heart of the DSP pipeline.
//
//  The algorithm: For each sample, build a reference vector from
//  6 harmonics of the powerline frequency (50/60Hz), compute the
//  noise estimate via dot product with weights, subtract it from
//  the signal, and update weights using NLMS.
//
//  V2.3 FIX #10: Death-lock timeout — if the derivative gate
//  freezes weights for >2.5s (640 samples @ 256Hz), force a
//  weight reset to allow rapid re-convergence.
// ═══════════════════════════════════════════════════════════════

use std::f64::consts::PI;

/// Result of the NLMS adaptive filter kernel.
pub struct NlmsResult {
    /// Cleaned signal with powerline noise removed
    pub cleaned: Vec<f64>,
    /// Final adaptive filter weights (persisted for next chunk)
    pub final_weights: Vec<f64>,
    /// Reference history tail for next chunk (eliminates zero-padding)
    pub new_ref_history: Vec<Vec<f64>>,
    /// Number of samples where the derivative gate was frozen
    pub frozen_count: u64,
}

/// Persistent state for the NLMS filter (per-channel).
#[derive(Clone)]
pub struct NlmsState {
    pub weights: Vec<f64>,
    pub ref_history: Vec<Vec<f64>>,
    pub phases: Vec<f64>,
    pub frozen_steps: u64,
}

impl NlmsState {
    pub fn new(n_harmonics: usize, n_taps: usize) -> Self {
        let total_taps = n_harmonics * n_taps;
        Self {
            weights: vec![0.0; total_taps],
            ref_history: vec![vec![0.0; n_taps - 1]; n_harmonics],
            phases: vec![0.0; n_harmonics],
            frozen_steps: 0,
        }
    }
}

/// Generate the sinusoidal reference matrix for NLMS.
/// Each row is a harmonic of the powerline frequency.
/// Uses persistent phase accumulation across chunks.
pub fn generate_ref_matrix(
    n_samples: usize,
    base_freq: f64,
    fs: f64,
    n_harmonics: usize,
    phases: &mut [f64],
) -> Vec<Vec<f64>> {
    let mut matrix = vec![vec![0.0_f64; n_samples]; n_harmonics];

    for h in 0..n_harmonics {
        let freq = base_freq * (h as f64 + 1.0);
        let phase_step = 2.0 * PI * freq / fs;
        for i in 0..n_samples {
            // Two columns per harmonic (sin + cos) packed sequentially
            matrix[h][i] = (phases[h] + phase_step * i as f64).sin();
        }
        // Persist phase for next chunk (avoid discontinuity)
        phases[h] += phase_step * n_samples as f64;
        phases[h] %= 2.0 * PI;
    }

    matrix
}

/// The core NLMS adaptive filter kernel.
/// Direct translation from V2.3 Python `@njit` function (line 46-115).
///
/// # Arguments
/// * `data` - Input EEG signal (1D, f64)
/// * `ref_matrix` - Reference sinusoids [n_harmonics][n_samples]
/// * `ref_history` - Previous chunk's tail [n_harmonics][hist_len]
/// * `n_taps` - Number of FIR taps per harmonic
/// * `mu` - NLMS step size (learning rate)
/// * `deriv_thresh` - Derivative threshold for gated freeze
/// * `init_weights` - Initial/persisted weights
pub fn nlms_adaptive_kernel(
    data: &[f64],
    ref_matrix: &[Vec<f64>],
    ref_history: &[Vec<f64>],
    n_taps: usize,
    mu: f64,
    deriv_thresh: f64,
    init_weights: &[f64],
) -> NlmsResult {
    let n_samples = data.len();
    let n_harmonics = ref_matrix.len();
    let total_taps = n_harmonics * n_taps;
    let hist_len = if n_taps > 1 { n_taps - 1 } else { 0 };

    // Initialize weights
    let mut w: Vec<f64> = if init_weights.len() == total_taps {
        init_weights.to_vec()
    } else {
        vec![0.0; total_taps]
    };

    let mut cleaned = vec![0.0_f64; n_samples];
    let mut frozen_count: u64 = 0;

    for i in 0..n_samples {
        // Build reference vector x (across all harmonics and taps)
        let mut x = vec![0.0_f64; total_taps];
        for h in 0..n_harmonics {
            for t_idx in 0..n_taps {
                let idx = i as isize - t_idx as isize;
                if idx >= 0 {
                    x[h * n_taps + t_idx] = ref_matrix[h][idx as usize];
                } else {
                    let hist_idx = hist_len as isize + idx;
                    if hist_idx >= 0
                        && (hist_idx as usize) < ref_history[h].len()
                    {
                        x[h * n_taps + t_idx] = ref_history[h][hist_idx as usize];
                    }
                    // else: remains 0.0 (zero-pad)
                }
            }
        }

        // Compute noise estimate: dot(w, x)
        let mut noise_est = 0.0_f64;
        for j in 0..total_taps {
            noise_est += w[j] * x[j];
        }

        // Error = signal - estimated noise
        let error = data[i] - noise_est;
        cleaned[i] = error;

        // Derivative-based gated freeze
        let mut is_transient = false;
        if i > 0 {
            let deriv = (data[i] - data[i - 1]).abs();
            if deriv > deriv_thresh {
                is_transient = true;
                frozen_count += 1;
            }
        }

        // Update weights (only if not a transient)
        if !is_transient {
            let mut norm: f64 = x.iter().map(|xi| xi * xi).sum();
            norm += 1e-10; // Regularization (prevent division by zero)
            let step = mu * error / norm;
            for j in 0..total_taps {
                w[j] += step * x[j];
            }
        }
    }

    // Save tail for next chunk
    let mut new_ref_history = vec![vec![0.0_f64; hist_len]; n_harmonics];
    if n_samples >= hist_len {
        for h in 0..n_harmonics {
            for t_idx in 0..hist_len {
                new_ref_history[h][t_idx] = ref_matrix[h][n_samples - hist_len + t_idx];
            }
        }
    }

    NlmsResult {
        cleaned,
        final_weights: w,
        new_ref_history,
        frozen_count,
    }
}

/// V2.3 Fix #10: Check if death-lock threshold exceeded.
/// If frozen for >2.5s (640 samples @ 256Hz), reset weights.
pub const DEATH_LOCK_THRESHOLD: u64 = 640; // 2.5s @ 256Hz

pub fn check_death_lock(state: &mut NlmsState, chunk_frozen: u64) -> bool {
    state.frozen_steps += chunk_frozen;
    if state.frozen_steps >= DEATH_LOCK_THRESHOLD {
        // Reset weights to zero — force rapid re-convergence
        for w in state.weights.iter_mut() {
            *w = 0.0;
        }
        state.frozen_steps = 0;
        true // death-lock was triggered
    } else {
        false
    }
}

// ── Unit Tests ─────────────────────────────────────────────────
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ref_matrix_generation() {
        let mut phases = vec![0.0; 6];
        let matrix = generate_ref_matrix(256, 50.0, 256.0, 6, &mut phases);
        assert_eq!(matrix.len(), 6); // 6 harmonics
        assert_eq!(matrix[0].len(), 256); // 256 samples
    }

    #[test]
    fn test_nlms_kernel_output_length() {
        let data: Vec<f64> = vec![0.0; 256];
        let ref_matrix = vec![vec![0.0; 256]; 6];
        let ref_history = vec![vec![0.0; 1]; 6];
        let weights = vec![0.0; 12]; // 6 harmonics * 2 taps

        let result = nlms_adaptive_kernel(
            &data, &ref_matrix, &ref_history, 2, 0.1, 50.0, &weights,
        );

        assert_eq!(result.cleaned.len(), 256);
        assert_eq!(result.final_weights.len(), 12);
    }

    #[test]
    fn test_death_lock_triggers_reset() {
        let mut state = NlmsState::new(6, 2);
        state.weights = vec![1.0; 12]; // Non-zero weights
        state.frozen_steps = 600;

        let triggered = check_death_lock(&mut state, 50); // 600 + 50 = 650 > 640
        assert!(triggered);
        assert!(state.weights.iter().all(|&w| w == 0.0), "Weights should be reset to 0");
        assert_eq!(state.frozen_steps, 0, "Counter should reset");
    }

    #[test]
    fn test_death_lock_does_not_trigger_below_threshold() {
        let mut state = NlmsState::new(6, 2);
        state.frozen_steps = 100;

        let triggered = check_death_lock(&mut state, 50); // 100 + 50 = 150 < 640
        assert!(!triggered);
        assert_eq!(state.frozen_steps, 150);
    }
}
