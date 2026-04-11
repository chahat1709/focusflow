pub mod filters;
pub mod nlms;
pub mod artifacts;
pub mod features;
pub mod sleep_pipeline;

use std::collections::{HashMap, VecDeque};
use serde::{Deserialize, Serialize};
use crate::hardware::BrainChunk;

/// Universal channel naming for Muse 2.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Channel {
    TP9,
    AF7,
    AF8,
    TP10,
    AUX,
}

/// Frequency band definitions.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FrequencyBands {
    pub delta: (f64, f64),
    pub theta: (f64, f64),
    pub alpha: (f64, f64),
    pub beta:  (f64, f64),
    pub gamma: (f64, f64),
}

impl Default for FrequencyBands {
    fn default() -> Self {
        Self {
            delta: (0.5, 4.0),
            theta: (4.0, 8.0),
            alpha: (8.0, 13.0),
            beta:  (13.0, 30.0),
            gamma: (30.0, 50.0),
        }
    }
}

/// DSP output snapshot.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DspSnapshot {
    pub timestamp_ms: u64,
    pub focus_metric: f64,
    pub deep_focus_cfc: f64,
    pub tbr: f64,
    pub headband_on: bool,
    pub emg_detected: bool,
    pub blink_count: usize,
    pub band_powers: BandPowers,
    pub mind_state: MindState,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BandPowers {
    pub delta: f64,
    pub theta: f64,
    pub alpha: f64,
    pub beta:  f64,
    pub gamma: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MindState {
    Active,
    Neutral,
    Calm,
}

/// The stateful DSP engine.
/// Maintains filter states and rolling windows across chunks.
/// Each channel has its own bandpass filter pair (4th-order = 2 cascaded biquads)
/// and its own rolling sample window.
pub struct SignalProcessor {
    pub fs: f64,
    /// Two cascaded biquad sections per channel (4th-order Butterworth 1-45Hz)
    pub filters: HashMap<Channel, (filters::IirFilter, filters::IirFilter)>,
    /// Rolling sample window per channel (1024 samples = 4 seconds @ 256Hz)
    pub windows: HashMap<Channel, VecDeque<f64>>,
    /// How many new samples have arrived since the last FFT computation
    pub samples_since_fft: HashMap<Channel, usize>,
    pub window_size: usize,
    pub bands: FrequencyBands,
    /// Blink detector state (persists across chunks)
    pub blink_state: artifacts::BlinkDetectorState,
    /// Latest computed snapshot (cached to avoid redundant FFTs)
    last_snapshot: Option<DspSnapshot>,
    /// Baseline calibration state
    pub baseline: BaselineState,
}

/// Tracks baseline TBR statistics for focus metric calibration.
/// During the first 30 seconds, collects TBR values.
/// After calibration, uses the computed mean/std for z-score normalization.
pub struct BaselineState {
    pub tbr_samples: Vec<f64>,
    pub calibrated: bool,
    pub mean: f64,
    pub std: f64,
    /// Number of samples needed for calibration (30s * ~1 update/sec)
    pub required_samples: usize,
}

impl BaselineState {
    pub fn new() -> Self {
        Self {
            tbr_samples: Vec::with_capacity(30),
            calibrated: false,
            mean: 1.5,  // Fallback defaults until calibrated
            std: 0.5,
            required_samples: 30,
        }
    }

    /// Add a TBR observation. Returns true if calibration just completed.
    pub fn observe(&mut self, tbr: f64) -> bool {
        if self.calibrated || tbr <= 0.0 {
            return false;
        }
        self.tbr_samples.push(tbr);
        if self.tbr_samples.len() >= self.required_samples {
            self.finalize();
            return true;
        }
        false
    }

    fn finalize(&mut self) {
        let n = self.tbr_samples.len() as f64;
        if n < 2.0 { return; }
        self.mean = self.tbr_samples.iter().sum::<f64>() / n;
        let variance = self.tbr_samples.iter()
            .map(|x| (x - self.mean).powi(2))
            .sum::<f64>() / n;
        self.std = variance.sqrt().max(0.01);
        self.calibrated = true;
    }
}

impl SignalProcessor {
    pub fn new(fs: f64, window_size: usize) -> Self {
        let mut filters_map = HashMap::new();
        let mut windows = HashMap::new();
        let mut samples_since_fft = HashMap::new();

        for ch in [Channel::TP9, Channel::AF7, Channel::AF8, Channel::TP10].iter() {
            // Create two cascaded biquad sections for 4th-order bandpass
            let pair = filters::make_bandpass_pair(1.0, 45.0, fs);
            filters_map.insert(*ch, pair);
            windows.insert(*ch, VecDeque::with_capacity(window_size));
            samples_since_fft.insert(*ch, 0usize);
        }

        Self {
            fs,
            filters: filters_map,
            windows,
            samples_since_fft,
            window_size,
            bands: FrequencyBands::default(),
            blink_state: artifacts::BlinkDetectorState::new(),
            last_snapshot: None,
            baseline: BaselineState::new(),
        }
    }

    /// Process a single BrainChunk from the hardware layer.
    /// Each BrainChunk contains samples from ONE channel only.
    /// Returns a new DspSnapshot when enough data has arrived for analysis.
    pub fn process_chunk(&mut self, chunk: BrainChunk) -> Option<DspSnapshot> {
        // Map the hardware channel to our DSP channel enum
        let dsp_channel = match chunk.channel {
            crate::hardware::Channel::TP9  => Channel::TP9,
            crate::hardware::Channel::AF7  => Channel::AF7,
            crate::hardware::Channel::AF8  => Channel::AF8,
            crate::hardware::Channel::TP10 => Channel::TP10,
            _ => return self.last_snapshot.clone(), // AUX/other channels: skip
        };

        // 1. Filter and buffer ALL samples from this chunk into the correct channel
        let n_new = chunk.samples_uv.len();
        for &sample in &chunk.samples_uv {
            let filtered = if let Some((f1, f2)) = self.filters.get_mut(&dsp_channel) {
                let s1 = f1.process_sample(sample);
                f2.process_sample(s1)
            } else {
                sample
            };

            if let Some(win) = self.windows.get_mut(&dsp_channel) {
                win.push_back(filtered);
                while win.len() > self.window_size {
                    win.pop_front();
                }
            }
        }

        // Track new samples for FFT throttling
        if let Some(count) = self.samples_since_fft.get_mut(&dsp_channel) {
            *count += n_new;
        }

        // 2. Only recompute FFT when AF7 has accumulated ~256 new samples (~1 second)
        //    This prevents running 85 FFTs/sec and limits to ~1 FFT/sec.
        let af7_new = self.samples_since_fft.get(&Channel::AF7).copied().unwrap_or(0);
        if af7_new < 256 {
            return self.last_snapshot.clone();
        }

        // Reset the counter for AF7
        if let Some(count) = self.samples_since_fft.get_mut(&Channel::AF7) {
            *count = 0;
        }

        // 3. Gate: AF7 must have ≥256 samples before we attempt any FFT.
        //    This is a latency guard — it does not restrict which channels
        //    contribute to the PSD (see step 4 below).
        let _af7_gating = self.windows.get(&Channel::AF7)?;
        if _af7_gating.len() < 256 {
            return None; // Not enough data yet (need at least 1 second)
        }

        // 4. Compute PSD as a straight average across all available channels.
        //
        // Rationale: a single electrode captures spatially local activity and
        // is susceptible to local artifacts (jaw muscle, hair contact resistance).
        // Averaging 4 channels reduces noise power by √N = 2× (for N=4 channels)
        // via the law of large numbers, exactly as done in clinical EEG systems.
        //
        // We only include channels that have ≥256 samples in their window to
        // avoid biasing the average with partially-filled buffers.
        let analysis_channels = [Channel::TP9, Channel::AF7, Channel::AF8, Channel::TP10];
        let mut psd_sum: Vec<f64> = Vec::new();
        let mut freqs_out: Vec<f64> = Vec::new();
        let mut n_valid: usize = 0;

        for ch in &analysis_channels {
            if let Some(win) = self.windows.get(ch) {
                if win.len() >= 256 {
                    let ch_data: Vec<f64> = win.iter().cloned().collect();
                    let (freqs, psd) = features::welch_psd(&ch_data, self.fs, 1024);
                    if !psd.is_empty() {
                        if psd_sum.is_empty() {
                            psd_sum  = psd;
                            freqs_out = freqs;
                        } else {
                            // Accumulate — we'll divide by n_valid below
                            for (acc, p) in psd_sum.iter_mut().zip(psd.iter()) {
                                *acc += p;
                            }
                        }
                        n_valid += 1;
                    }
                }
            }
        }

        if n_valid == 0 || psd_sum.is_empty() {
            return self.last_snapshot.clone();
        }

        // Normalise sum → mean PSD
        let n_f = n_valid as f64;
        let psd: Vec<f64> = psd_sum.iter().map(|p| p / n_f).collect();
        let freqs = freqs_out;


        // 5. IAF-personalized band powers
        let iaf = features::find_iaf(&freqs, &psd);
        let bands = features::get_iaf_bands(iaf);

        let delta_p = features::band_power(&psd, &freqs, bands.delta.0, bands.delta.1);
        let theta_p = features::band_power(&psd, &freqs, bands.theta.0, bands.theta.1);
        let alpha_p = features::band_power(&psd, &freqs, bands.alpha.0, bands.alpha.1);
        let beta_p  = features::band_power(&psd, &freqs, bands.beta.0, bands.beta.1);
        let gamma_p = features::band_power(&psd, &freqs, bands.gamma.0, bands.gamma.1);
        let total_power = delta_p + theta_p + alpha_p + beta_p + gamma_p + 1e-10;

        // 6. Artifact detection — using the REAL detectors we already wrote
        let emg_result = artifacts::detect_emg(&psd, &freqs);
        let headband_on = !artifacts::powerline_antenna_check(&psd, &freqs);

        // Blink detection from AF7 + AF8 frontal channels
        let af7_raw: Vec<f64> = self.windows.get(&Channel::AF7)
            .map(|w| w.iter().cloned().collect()).unwrap_or_default();
        let af8_raw: Vec<f64> = self.windows.get(&Channel::AF8)
            .map(|w| w.iter().cloned().collect()).unwrap_or_default();
        let blink_zones = artifacts::detect_blinks(&af7_raw, &af8_raw, &mut self.blink_state);

        // 7. Compute TBR with EMG gating
        let tbr = features::compute_tbr(theta_p, beta_p, emg_result.emg_detected);

        // 8. Baseline calibration — observe TBR values during first 30 seconds
        self.baseline.observe(tbr);
        let focus = features::tbr_to_focus(tbr, self.baseline.mean, self.baseline.std);

        // 9. Mind state classification
        let mind_state = if !headband_on {
            MindState::Neutral // Can't classify if headband is off
        } else if beta_p > alpha_p && beta_p > theta_p {
            MindState::Active
        } else if alpha_p > beta_p && alpha_p > theta_p {
            MindState::Calm
        } else {
            MindState::Neutral
        };

        let snapshot = DspSnapshot {
            timestamp_ms: chunk.timestamp_us / 1000,
            focus_metric: focus,
            deep_focus_cfc: 0.0, // AMI: future work
            tbr,
            headband_on,
            emg_detected: emg_result.emg_detected,
            blink_count: blink_zones.len(),
            band_powers: BandPowers {
                delta: delta_p / total_power,
                theta: theta_p / total_power,
                alpha: alpha_p / total_power,
                beta:  beta_p / total_power,
                gamma: gamma_p / total_power,
            },
            mind_state,
        };

        self.last_snapshot = Some(snapshot.clone());
        Some(snapshot)
    }
}

