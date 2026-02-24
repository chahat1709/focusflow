#!/usr/bin/env python3
"""
FocusFlow — Production Neurofeedback Server
Native BLE (bleak/muselsl) + pywebview native window.
Single .exe via PyInstaller.
"""

import asyncio
import json
import logging
import time
import threading
import os
import sys
import math
import signal as signal_mod
from typing import Optional, List
import numpy as np
from dataclasses import dataclass, field, asdict
try:
    from scipy import signal
except ImportError:
    signal = None

from aiohttp import web

# ═══════════════════════════════════════════════════════════════
#  PATH HELPER (PyInstaller)
# ═══════════════════════════════════════════════════════════════
def resource_path(relative_path: str) -> str:
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

# ═══════════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════════
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-7s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger('FocusFlow')

# ═══════════════════════════════════════════════════════════════
#  DIRECT BLE CONNECTOR  (muse_ble.py — uses bleak only)
# ═══════════════════════════════════════════════════════════════
BLE_AVAILABLE = False
try:
    from muse_ble import MuseBLEClient
    BLE_AVAILABLE = True
    logger.info("[OK] Direct BLE connector loaded (muse_ble + bleak)")
except ImportError as e:
    logger.warning(f"Direct BLE not available: {e}")

# ═══════════════════════════════════════════════════════════════
#  LSL FALLBACK  (for BlueMuse / other LSL sources)
# ═══════════════════════════════════════════════════════════════
LSL_AVAILABLE = False
try:
    from pylsl import StreamInlet, resolve_byprop
    LSL_AVAILABLE = True
    logger.info("[OK] pylsl loaded — LSL fallback available")
except ImportError:
    pass

# ═══════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════
class Config:
    HOST = '127.0.0.1'
    PORT = 5077
    LSL_TIMEOUT = 5.0
    LSL_RECONNECT_DELAY = 2.0
    SIMULATION_HZ = 10

config = Config()

# ═══════════════════════════════════════════════════════════════
#  DATA SNAPSHOT
# ═══════════════════════════════════════════════════════════════
@dataclass
class EEGSnapshot:
    focus: float = 0.5
    alpha: float = 0.0
    beta: float = 0.0
    theta: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    signal_ok: bool = False
    connected: bool = False
    timestamp: float = 0.0
    blink_rate: int = 0
    # New sensors
    accel: dict = field(default_factory=lambda: {'x': 0.0, 'y': 0.0, 'z': 0.0})
    gyro: dict = field(default_factory=lambda: {'x': 0.0, 'y': 0.0, 'z': 0.0})
    ppg: dict = field(default_factory=lambda: {'PPG1': 0.0, 'PPG2': 0.0, 'PPG3': 0.0})
    bpm: int = 0
    emg_noise: bool = False
    deep_focus: float = 0.0   # Stage 5: Alpha-Gamma CFC coupling score [0-1]
    headband_on: bool = False  # True when valid EEG contact detected
    mind_state: str = 'unknown'  # 'calm', 'neutral', 'active' (like Muse app)
    mind_state_time: float = 0.0  # Seconds in current state

# ═══════════════════════════════════════════════════════════════
#  DIAGNOSTICS & SIGNAL QUALITY
# ═══════════════════════════════════════════════════════════════
def get_sensor_diagnostics() -> dict:
    """Returns the quality status of each EEG electrode for the UI map.
    In a real scenario, this would check variance/rail voltage.
    """
    # Placeholder: In production_server.py, we'll try to get these from the manager
    # if it's available, otherwise return defaults.
    # For now, we'll assume they are good if connected.
    return {
        'TP9': 'good',
        'AF7': 'good',
        'AF8': 'good',
        'TP10': 'good'
    }

# ═══════════════════════════════════════════════════════════════
#  CONNECTION STATE MACHINE
# ═══════════════════════════════════════════════════════════════
class ConnectionManager:
    """Manages Muse connection lifecycle: scan → connect → stream.
    Uses Direct BLE (MuseBLEClient) as primary strategy.
    """

    def __init__(self):
        self.snapshot = EEGSnapshot()
        self._lock = threading.RLock()  # RLock allows reentrant acquisition (get_snapshot -> get_sensor_diagnostics)
        self._state = 'idle'
        self._ble_client: Optional['MuseBLEClient'] = None
        self._sim_running = False
        self._buffers = {'TP9': [], 'AF7': [], 'AF8': [], 'TP10': []}
        self._ppg_buffer = [] 
        self.MAX_BUF = 512 
        self._main_loop = None 
        self._last_update = 0.0
        
        # Smoothing state
        self._smooth_hist = {
            'focus': 0.5,
            'delta': 0.0, 'theta': 0.0, 'alpha': 0.0, 'beta': 0.0, 'gamma': 0.0
        }
        
        # ── Research-Grade Additions ──
        self._imu_buffer = []       # Raw accel magnitude history (for motion filter)
        # Baseline calibration (first 30s of data)
        self._baseline_samples = []  # Collect baseline engagement ratios
        self._baseline_ratio = None  # User's resting engagement ratio
        self._baseline_std   = 0.1   # Z-score std (computed at baseline end)
        self._baseline_done = False
        self._baseline_start_time = None
        
        # IAF (Individual Alpha Frequency)
        self._iaf = 10.0  # Default 10Hz (will be personalized during baseline)
        self._iaf_bands = None  # Will hold personalized band boundaries
        self._iaf_psd_accumulator = []  # Collect PSDs during baseline for IAF detection
        
        # 50Hz Notch Filter state (IIR biquad)
        self._notch_state = {ch: {'x1': 0, 'x2': 0, 'y1': 0, 'y2': 0} 
                            for ch in ['TP9', 'AF7', 'AF8', 'TP10']}
        
        # Blink tracking
        self._blink_history = []  # List of timestamps when blinks were detected

        # Headband debounce: require N consecutive same-state samples before flipping
        self._headband_stability_counter = 0   # +ve = consecutive valid, -ve = consecutive invalid
        self._headband_confirmed = False        # Stable confirmed state

    def set_loop(self, loop):
        """Set the main asyncio loop (from aiohttp)."""
        self._main_loop = loop

    @property
    def state(self):
        return self._state

    def get_snapshot(self) -> dict:
        with self._lock:
            # Stale check: if no data for > 2 seconds, marks as disconnected/noise
            if self._state == 'connected' and (time.time() - self._last_update > 2.0):
                self.snapshot.signal_ok = False
                self.snapshot.connected = False # Or keep connected but indicate 'no data'
                self.snapshot.focus = 0.0
                self.snapshot.bpm = 0
            
            res = asdict(self.snapshot)
            res['baseline_done'] = self._baseline_done
            # Attach current sensor diagnostics for the electrode map
            res['diagnostics'] = get_sensor_diagnostics()
            return res

    def reset_baseline(self):
        """Reset baseline/IAF calibration for a new student session."""
        with self._lock:
            self._baseline_samples.clear()
            self._baseline_ratio = None
            self._baseline_std = 0.1
            self._baseline_done = False
            self._baseline_start_time = None
            self._iaf = 10.0
            self._iaf_bands = None
            self._iaf_psd_accumulator.clear()
            self._blink_history.clear()
            # Reset smoothing so new student starts clean
            self._smooth_hist = {
                'focus': 0.5,
                'delta': 0.0, 'theta': 0.0, 'alpha': 0.0, 'beta': 0.0, 'gamma': 0.0
            }
            self.snapshot.focus = 0.0
            self.snapshot.mind_state = 'calibrating'
            self.snapshot.mind_state_time = 0.0
            logger.info("BASELINE RESET — new student session calibration starting.")

    # ... (connect/disconnect/start_simulation remain same) ...


    # ── CONNECT ──────────────────────────────────────────────
    def connect(self):
        """Start scanning + connecting in background."""
        if self._state == 'connected' or self._state == 'simulating':
            return {'status': 'already_connected'}
        
        self._state = 'scanning'
        self._buffers = {'TP9': [], 'AF7': [], 'AF8': [], 'TP10': []}
        
        # Run connection flow in a separate thread to avoid blocking API
        threading.Thread(target=self._connect_flow, daemon=True).start()
        return {'status': 'scanning'}

    def disconnect(self):
        """Stop everything."""
        self._sim_running = False
        
        # Disconnect BLE on the main loop
        if self._ble_client and self._main_loop:
            asyncio.run_coroutine_threadsafe(
                self._ble_client.disconnect(),
                self._main_loop
            )
            self._ble_client = None

        self._state = 'idle'
        with self._lock:
            self.snapshot = EEGSnapshot()
        logger.info("Disconnected.")
        return {'status': 'disconnected'}

    def start_simulation(self):
        if self._state == 'connected' or self._state == 'simulating':
            return {'status': 'already_connected'}
        self._sim_running = True
        self._state = 'simulating'
        threading.Thread(target=self._simulate_forever, daemon=True).start()
        return {'status': 'simulating'}

    # ── CONNECTION FLOW ──────────────────────────────────────
    def _connect_flow(self):
        """Connect on user click, auto-reconnect within session on BLE drop.
        Goes idle only after 3 consecutive reconnect failures or user Disconnect.
        
        IMPORTANT: On Windows, Bleak's WinRT BLE backend requires its OWN 
        clean event loop. We use asyncio.run() here (in a background thread)
        which creates a fresh event loop — NOT the aiohttp main loop.
        """
        
        reconnect_failures = 0
        MAX_RECONNECTS = 3

        while self._state != 'idle':
            logger.info(f"Starting connection sequence... (BLE_AVAILABLE:{BLE_AVAILABLE})")
            
            # 1. Try Direct BLE
            if BLE_AVAILABLE:
                try:
                    asyncio.run(self._connect_ble())
                except Exception as e:
                    logger.error(f"BLE Connect Task Error: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                
                # If connected, monitor the connection
                if self._state == 'connected':
                    reconnect_failures = 0  # Reset on successful connect
                    logger.info("Connection established. Monitoring...")
                    while self._state == 'connected':
                        if self._ble_client and not self._ble_client.connected:
                             logger.warning("BLE Client disconnected. Will auto-reconnect...")
                             self._state = 'scanning'
                             break
                        time.sleep(1)
                    if self._state == 'idle':
                        return  # User clicked Disconnect
                    continue  # Auto-reconnect

            # 2. Try LSL (fallback)
            if LSL_AVAILABLE and self._state != 'connected':
                logger.info("Checking for existing LSL stream...")
                if self._try_lsl_connect(timeout=10):
                     while self._state == 'connected':
                         time.sleep(1)
                     continue

            # 3. Failed — count failures
            reconnect_failures += 1
            if reconnect_failures >= MAX_RECONNECTS:
                logger.warning(f"[FAIL] {MAX_RECONNECTS} consecutive connection failures. Going idle.")
                self._state = 'idle'
                return
            
            logger.warning(f"[FAIL] Connection attempt {reconnect_failures}/{MAX_RECONNECTS} failed. Retrying in 3s...")
            self._state = 'scanning'
            time.sleep(3.0)

    async def _connect_ble(self):
        """Async driver for MuseBLEClient. Runs in its OWN event loop via asyncio.run()."""
        logger.info("Connecting via BLE (dedicated loop)...")
        client = MuseBLEClient(
            on_eeg_sample=self._on_ble_data,
            on_imu_sample=self._on_imu_data,
            on_ppg_sample=self._on_ppg_data
        )
        self._ble_client = client
        
        success = await client.auto_connect(max_retries=4, scan_timeout=8.0)
        if success:
            self._state = 'connected'
            with self._lock:
                self.snapshot.connected = True
                self.snapshot.signal_ok = True
            logger.info("[OK] BLE connected (EEG + IMU + PPG streaming).")
            
            # Keep this event loop alive while connected (for keep-alive & notifications)
            while self._ble_client and self._ble_client.connected and self._state == 'connected':
                await asyncio.sleep(1)
            
            logger.info("BLE connection ended in dedicated loop.")
        else:
            self._ble_client = None

    def _on_imu_data(self, sensor_type: str, samples: list):
        """Callback from MuseBLEClient with new IMU data."""
        if not samples: return
        self._last_update = time.time()

        latest = samples[-1]  # Take the most recent sample
        with self._lock:
            if sensor_type == 'accel':
                self.snapshot.accel = latest
                # Stage 3: feed accel [x,y,z] into IMU motion filter buffer
                self._imu_buffer.extend(
                    [[s['x'], s['y'], s['z']] for s in samples
                     if isinstance(s, dict) and 'x' in s]
                )
                # Keep buffer at 512 samples max
                if len(self._imu_buffer) > 512:
                    self._imu_buffer = self._imu_buffer[-512:]
            elif sensor_type == 'gyro':
                self.snapshot.gyro = latest
            self.snapshot.connected = True

    def _on_ppg_data(self, channel_name: str, samples: list):
        """Callback from MuseBLEClient with new PPG data."""
        if not samples: return
        self._last_update = time.time()
        
        val = np.mean(samples)
        with self._lock:
             self.snapshot.ppg[channel_name] = val
             self.snapshot.connected = True
        
        if channel_name == 'PPG2':
            self._ppg_buffer.extend(samples)
            if not hasattr(self, '_ppg_start_t'):
                self._ppg_start_t = time.time()
                self._ppg_sample_count = 0
            
            self._ppg_sample_count += len(samples)
            
            # Recalculate every ~2 seconds (512 samples @ 256Hz)
            if len(self._ppg_buffer) > 512: 
                 # Calculate approx FS
                 elapsed = time.time() - self._ppg_start_t
                 if elapsed > 1.0:
                     est_fs = self._ppg_sample_count / elapsed
                     # Reset counter for next window
                     self._ppg_start_t = time.time()
                     self._ppg_sample_count = 0
                 else:
                     est_fs = 256.0 # Default assumption
                 
                 self._calculate_bpm(est_fs)
                 self._ppg_buffer = self._ppg_buffer[-256:] # Overlap

            # Debug logs
            if not hasattr(self, '_ppg_log_timer'): self._ppg_log_timer = 0
            self._ppg_log_timer += 1
            if self._ppg_log_timer > 100:
                self._ppg_log_timer = 0
                logger.info(f"PPG Data | {channel_name}: {val:.0f} | BPM: {self.snapshot.bpm}")

    def _calculate_bpm(self, fs_est=256.0):
        """Derivative-based BPM estimation (Dynamic FS)."""
        try:
            # Gate: Don't calculate BPM unless headband is on a head
            # PPG sensor picks up IR noise from air/surfaces = fake BPM
            if not self.snapshot.headband_on:
                with self._lock:
                    self.snapshot.bpm = 0
                return
            # Determine mode based on estimated FS
            if fs_est > 150:
                fs = 256.0
                win_smooth = 12
                win_check = 10
                min_dist = 80  # ~190 BPM
                max_dist = 400 # ~38 BPM
            else:
                fs = 64.0
                win_smooth = 5
                win_check = 4
                min_dist = 20
                max_dist = 100
                
            raw = np.array(self._ppg_buffer)
            if len(raw) < (fs * 0.5): return
            
            # 1. Bandpass Filter (0.5Hz - 4Hz)
            # High-pass: Remove DC (already done by finding diff, but let's be cleaner)
            # Low-pass: strong smoothing to kill EMG noise
            win_smooth = int(fs / 5) # ~0.2s window
            smoothed = np.convolve(raw, np.ones(win_smooth)/win_smooth, mode='same')
            
            # 2. Derivative (Pulse Onset)
            diff = np.diff(smoothed)
            
            # 3. Peak Detection with Local Adaptive Threshold
            # Large artifacts (slope > 10k) usually ruin global thresholding.
            # We reject huge jumps and look for rhythmic smaller ones.
            
            valid_diff = diff[(diff > -5000) & (diff < 5000)]
            if len(valid_diff) < len(diff) * 0.5:
                 # Too much noise
                 if self._ppg_log_timer == 50: logger.info(f"BPM FAIL | Noise (High Amp)")
                 return
                 
            # Re-calc slope range on cleaner data
            max_slope = np.max(valid_diff) if len(valid_diff) > 0 else 0
            slope_range = max_slope - np.min(valid_diff) if len(valid_diff) > 0 else 0
            
            if slope_range < 5: return # Flatline
            
            threshold = max_slope * 0.3
            
            peaks = []
            for i in range(win_check, len(diff)-win_check):
                val = diff[i]
                # Check bounds to ignore massive artifacts
                if 5 < val < 5000: 
                    if val > threshold:
                        if val == np.max(diff[i-win_check : i+win_check]):
                            peaks.append(i)
                        
            bpm = 0
            # Method A: Peak Intervals
            if len(peaks) >= 2:
                intervals = np.diff(peaks)
                valid_intervals = [x for x in intervals if min_dist < x < max_dist]
                if valid_intervals:
                    avg_iv = np.mean(valid_intervals)
                    bpm = 60.0 * (fs / avg_iv)
            
            # Method B: Zero-Crossing (Backup)
            if bpm == 0:
                 # Standardize and zero-cross
                 norm = (diff - np.mean(diff))
                 zc = np.where(np.diff(np.sign(norm)))[0]
                 
                 time_sec = len(diff) / fs
                 if time_sec > 0.5:
                     est_beats = len(zc) / 2.0
                     bpm_zc = (est_beats / time_sec) * 60.0
                     if 45 < bpm_zc < 160: bpm = bpm_zc

            # Smooth update
            if 30 < bpm < 200:
                curr = self.snapshot.bpm
                alpha = 0.1 if curr > 0 else 1.0 # Slower smooth
                new_bpm = curr * (1-alpha) + bpm * alpha
                with self._lock:
                    self.snapshot.bpm = int(new_bpm)
            else:
                # Debug logging for rejection
                if self._ppg_log_timer == 50: # Log occasionally
                     logger.info(f"BPM FAIL | Slope:{slope_range:.1f} | Peaks:{len(peaks)} | FS:{fs:.0f}")

        except Exception as e:
             logger.error(f"BPM Error: {e}")

    def _on_ble_data(self, ch_idx, samples):
        """Callback from MuseBLEClient with new data."""
        try:
            names = ['TP9', 'AF7', 'AF8', 'TP10']
            if 0 <= ch_idx < 4:
                name = names[ch_idx]
                self._buffers[name].extend(samples)
                # Keeping it slightly larger than MAX_BUF for processing window
                if len(self._buffers[name]) > self.MAX_BUF * 1.5:
                    self._buffers[name] = self._buffers[name][-self.MAX_BUF:]
            
            if ch_idx == 3 and len(samples) > 0:
                self._process_data()
        except Exception as e:
            # Absorb errors (e.g. bleak _check_closed on BLE disconnect)
            logger.debug(f"BLE data callback error (safe to ignore): {e}")

    # ── SIGNAL PROCESSING HELPERS ──
    
    def _find_iaf(self, freqs, psd):
        """Find Individual Alpha Frequency (IAF) — peak in 7-14Hz range.
        IAF is the most stable EEG biomarker and varies per person (typically 9-11Hz).
        Used by clinical neurofeedback to personalize all band boundaries."""
        # Search only in the alpha-theta transition zone (7-14Hz)
        alpha_mask = np.logical_and(freqs >= 7.0, freqs <= 14.0)
        alpha_freqs = freqs[alpha_mask]
        alpha_psd = psd[alpha_mask]
        
        if len(alpha_psd) == 0:
            return 10.0  # Default
        
        # Find the peak
        peak_idx = np.argmax(alpha_psd)
        iaf = alpha_freqs[peak_idx]
        
        # Sanity check: IAF should be between 8-12Hz for healthy adults
        if iaf < 7.5 or iaf > 13.5:
            return 10.0  # Default fallback
        
        return float(iaf)
    
    def _get_iaf_bands(self, iaf):
        """Generate personalized band boundaries based on IAF.
        Clinical standard: Klimesch (1999) method."""
        return {
            'Delta': (0.5, iaf - 6.0),           # ~0.5 to ~4Hz
            'Theta': (max(2.0, iaf - 6.0), iaf - 2.0),  # ~4 to ~8Hz
            'Alpha': (iaf - 2.0, iaf + 2.0),     # ~8 to ~12Hz (centered on IAF)
            'Beta':  (iaf + 2.0, 30.0),           # ~12 to 30Hz
            'Gamma': (30.0, 50.0)                 # 30 to 50Hz (unchanged)
        }
    
    # ── ADVANCED DSP FILTERS ───────────────────────────────────
    def _notch_filter(self, data, freq_hz, fs=256.0, q=30.0):
        """Generic notch filter — use for 50Hz or 60Hz hum."""
        if signal is None: return data
        nyq = 0.5 * fs
        freq = freq_hz / nyq
        if freq >= 1.0: return data   # out of range, skip
        b, a = signal.iirnotch(freq, q)
        return signal.filtfilt(b, a, data)

    def _notch_filter_50hz(self, data, ch_name, fs=256.0):
        """Clean 50Hz + 60Hz electrical hum (dual-stage)."""
        d = self._notch_filter(data, 50.0, fs)
        d = self._notch_filter(d,    60.0, fs)
        return d

    def _bandpass_filter(self, data, lowcut=1.0, highcut=45.0, fs=256.0):
        """Clinical Butterworth filter to remove DC drift and high-freq noise."""
        if signal is None: return data
        nyq = 0.5 * fs
        low = lowcut / nyq
        high = highcut / nyq
        # 4th order Butterworth for flat passband and sharp roll-off
        b, a = signal.butter(4, [low, high], btype='band')
        return signal.filtfilt(b, a, data)

    # ── STAGE 3: IMU MOTION-AWARE FILTER ───────────────────────
    def _imu_motion_mask(self) -> np.ndarray:
        """Returns a boolean mask (len=512) of 'safe' EEG samples — ones where
        head motion was below the artifact threshold (0.15g change).
        Returns all-True if no IMU data available."""
        if len(self._imu_buffer) < 512:
            return np.ones(512, dtype=bool)
        imu = np.array(self._imu_buffer[-512:])
        # Compute per-sample movement magnitude
        mag = np.linalg.norm(imu, axis=1) if imu.ndim == 2 else np.abs(imu)
        # Rolling std: flag samples where magnitude exceeds 0.15g threshold
        threshold = np.median(mag) + 3.0 * np.std(mag)
        motion_mask = mag <= threshold
        return motion_mask

    # ── STAGE 4: LIGHTWEIGHT ASR ────────────────────────────────
    def _asr_clean(self, data: np.ndarray, z_thresh=5.0) -> np.ndarray:
        """Artifact Subspace Reconstruction (lightweight).
        Replaces samples > z_thresh sigma with the channel median.
        Preserves the rest of the window unlike full channel rejection."""
        ch_median = np.median(data)
        ch_std = np.std(data)
        if ch_std < 0.01: return data  # Flatline, skip
        z = np.abs((data - ch_median) / ch_std)
        cleaned = data.copy()
        cleaned[z > z_thresh] = ch_median
        return cleaned

    # ── STAGE 5: CROSS-FREQUENCY COUPLING (Deep Focus) ──────────
    def _cfc_score(self, data: np.ndarray, fs=256.0) -> float:
        """Alpha-Gamma phase-amplitude coupling via Hilbert transform.
        Returns Mean Vector Length (MVL) in [0, 1] — proxy for 'deep focus'.
        High MVL = sustained attention, low = relaxed or distracted."""
        try:
            if signal is None or len(data) < 256: return 0.0
            # Alpha phase (8-12 Hz)
            alpha_filt = self._bandpass_filter(data, 8.0, 12.0, fs)
            alpha_phase = np.angle(signal.hilbert(alpha_filt))
            # Gamma amplitude (30-50 Hz)
            gamma_filt = self._bandpass_filter(data, 30.0, 50.0, fs)
            gamma_amp = np.abs(signal.hilbert(gamma_filt))
            # Mean Vector Length (Canolty et al. 2006)
            mvl = np.abs(np.mean(gamma_amp * np.exp(1j * alpha_phase)))
            # Normalise to [0, 1] with empirical max of ~5.0
            return float(np.clip(mvl / 5.0, 0.0, 1.0))
        except Exception:
            return 0.0

    # ── STAGE 2: SAVITZKY-GOLAY SMOOTHING ───────────────────────
    def _savgol_smooth(self, history: list, new_val: float,
                       window=9, polyorder=3) -> float:
        """Append new_val to history, return Savitzky-Golay smoothed output.
        Window must be odd and > polyorder. History is modified in-place."""
        history.append(new_val)
        if len(history) > window:
            history.pop(0)
        if len(history) < polyorder + 2:
            return new_val  # Not enough data yet
        win = min(len(history), window)
        if win % 2 == 0: win -= 1  # Must be odd
        if win <= polyorder: return new_val
        if signal is None: return new_val
        smoothed = signal.savgol_filter(history, win, polyorder)
        return float(smoothed[-1])

    def _detect_emg(self, psd, freqs) -> bool:
        """Detect muscle tension (clenching) in 45-100Hz range."""
        idx = np.logical_and(freqs >= 45.0, freqs <= 100.0)
        if not np.any(idx): return False
        avg_high_freq = np.mean(psd[idx])
        # Empirical threshold for muscle noise
        return avg_high_freq > 1.5
    
    def _detect_blinks(self, af7_data, af8_data, threshold=100.0):
        """Detect eye blink artifacts on frontal channels.
        Blinks cause >100.0uV spikes on AF7/AF8.
        Returns: list of (start, end) sample indices to exclude."""
        blink_zones = []
        combined = (np.abs(af7_data) + np.abs(af8_data)) / 2.0
        in_blink = False
        start = 0
        
        for i in range(len(combined)):
            if combined[i] > threshold and not in_blink:
                start = max(0, i - 25)  # 100ms before
                in_blink = True
            elif combined[i] < threshold * 0.5 and in_blink:
                end = min(len(combined), i + 25)  # 100ms after
                blink_zones.append((start, end))
                in_blink = False
        
        if in_blink:
            blink_zones.append((start, len(combined)))
        
        return blink_zones
    
    def _welch_psd(self, data, fs=256.0, n_segments=4):
        """Welch's method: average PSD over overlapping segments.
        More stable than single-window periodogram."""
        n = len(data)
        seg_len = n // (n_segments // 2 + 1)  # 50% overlap
        if seg_len < 64:
            seg_len = n  # Fall back to single window
            n_segments = 1
        
        step = seg_len // 2  # 50% overlap
        psd_sum = None
        count = 0
        
        for start in range(0, n - seg_len + 1, step):
            segment = data[start:start + seg_len]
            # Detrend
            segment = segment - np.mean(segment)
            # Hanning Window
            window = np.hanning(seg_len)
            # FFT
            fft_vals = np.fft.rfft(segment * window)
            psd = np.abs(fft_vals)**2 / seg_len
            
            if psd_sum is None:
                psd_sum = psd
            else:
                psd_sum = psd_sum + psd
            count += 1
        
        if count == 0:
            return None, None
        
        psd_avg = psd_sum / count
        freqs = np.fft.rfftfreq(seg_len, 1/fs)
        return freqs, psd_avg

    def _process_data(self):
        """Clinical-grade EEG processing pipeline.
        Stage 1: Z-Score Brain-State Normalization
        Stage 2: Savitzky-Golay Stabilization
        Stage 3: IMU Motion-Aware Filtering
        Stage 4: Lightweight ASR (Artifact Subspace Reconstruction)
        Stage 5: Cross-Frequency Coupling (Deep Focus overlay)
        """
        try:
            # ── Step 0: Collect raw data (2s window = 512 samples) ──
            ch_names = ['TP9', 'AF7', 'AF8', 'TP10']
            raw_arrays = {}
            for ch in ch_names:
                if len(self._buffers[ch]) >= 512:
                    raw_arrays[ch] = np.array(self._buffers[ch][-512:], dtype=np.float64)
            
            if not raw_arrays: return
            
            available_ch = list(raw_arrays.keys())
            fs = 256.0
            
            # Use IAF-personalized bands if available
            bands = self._iaf_bands if self._iaf_bands else {
                'Delta': (0.5, 4), 'Theta': (4, 8), 'Alpha': (8, 13), 'Beta': (13, 30), 'Gamma': (30, 50)
            }
            
            # ── Stage 3+4: Filtering, motion mask, ASR ──
            motion_mask = self._imu_motion_mask()  # Stage 3: IMU motion mask
            filtered = {}
            for ch in available_ch:
                # 1. Bandpass (1-45Hz) + Dual notch (50+60Hz)
                d_bp    = self._bandpass_filter(raw_arrays[ch], fs=fs)
                d_notch = self._notch_filter_50hz(d_bp, ch, fs)

                # Stage 4: ASR — replace spike samples with channel median
                d_asr = self._asr_clean(d_notch, z_thresh=5.0)

                # Stage 3: zero out motion-contaminated samples
                if len(motion_mask) == len(d_asr):
                    d_asr[~motion_mask] = float(np.median(d_asr))

                filtered[ch] = d_asr
            
            # ── Step 1.2: CAR (Common Average Reference) ──
            # Software-based noise cancellation. Subtracting the average of all 
            # electrodes removes noise that is common to all sensors (environmental hum/vibration).
            if len(available_ch) >= 3:
                all_raw = np.array([filtered[ch] for ch in available_ch])
                common_noise = np.median(all_raw, axis=0) # Use median for robust noise profile
                for ch in available_ch:
                    filtered[ch] -= common_noise
            
            valid_ch = []
            for ch in available_ch:
                d = filtered[ch]
                p2p = np.max(d) - np.min(d)
                std = np.std(d)
                # Railing / flat / broken sensor
                if np.min(d) <= -999.0 or np.max(np.abs(d)) >= 800: continue
                if p2p < 5 or std < 1.0: continue
                # Real EEG std after bandpass is 5-350µV. Relaxed to handle varying skin contact.
                if std > 350: continue
                # P2P > 1000µV means severe artifact or no skin contact
                if p2p > 1000: continue
                valid_ch.append(ch)
            
            if not valid_ch: return
            
            # ── Step 2: Eye Blink Rejection ──
            blink_zones = []
            if 'AF7' in valid_ch and 'AF8' in valid_ch:
                blink_zones = self._detect_blinks(filtered['AF7'], filtered['AF8'])
            
            n_samples = len(filtered[valid_ch[0]])
            clean_mask = np.ones(n_samples, dtype=bool)
            for (s, e) in blink_zones:
                clean_mask[s:e] = False
            
            # Record blinks into history for rate calculation
            if blink_zones:
                now = time.time()
                # To prevent double-counting a single long blink spread across dual updates
                if not self._blink_history or (now - self._blink_history[-1] > 0.5):
                    for _ in range(len(blink_zones)):
                        self._blink_history.append(now)
            
            # Calculate blink rate over last 60 seconds
            now = time.time()
            self._blink_history = [t for t in self._blink_history if now - t < 60]
            blink_rate = len(self._blink_history)
            
            clean_ratio = np.sum(clean_mask) / n_samples
            ampl_ok = (clean_ratio >= 0.2)
            
            # ── Step 3: Spectral Power per Channel (Pure segments only) ──
            ch_band_powers = {k: [] for k in bands}
            emg_detected = False
            psd_sum_all = None
            
            for ch in valid_ch:
                d = filtered[ch]
                # Manual segmenting to ignore any window containing a blink
                # 512 samples @ 256Hz = 2s. We use 256 sample windows with 128 overlap.
                # Window 1: [0:256], Window 2: [128:384], Window 3: [256:512]
                valid_psds = []
                for start in [0, 128, 256]:
                    end = start + 256
                    if end > n_samples: break
                    # Only use if segment is 100% clean
                    if np.all(clean_mask[start:end]):
                        seg = d[start:end]
                        seg = seg - np.mean(seg) # Detrend
                        f, p = signal.welch(seg, fs, window='hann', nperseg=256, noverlap=128)
                        valid_psds.append(p)
                        freqs = f # Reference freqs
                
                if not valid_psds:
                    # Fallback: if no 100% clean segment, use largest available 
                    # but it's risky for clinical data. We'll skip this channel.
                    continue
                
                # Average PSD for this channel from pure segments only
                psd = np.mean(valid_psds, axis=0)
                
                if self._detect_emg(psd, freqs):
                    emg_detected = True
                
                if psd_sum_all is None: psd_sum_all = psd.copy()
                else: psd_sum_all += psd
                
                for band, (f_min, f_max) in bands.items():
                    idx = np.logical_and(freqs >= f_min, freqs <= f_max)
                    if np.any(idx):
                        ch_band_powers[band].append(np.mean(psd[idx]))

            # ── Step 4: Robust Statistics ──
            avg_powers = {}
            processed_ch_count = 0
            for band in bands:
                powers = ch_band_powers[band]
                if powers:
                    avg_powers[band] = np.median(powers)
                    processed_ch_count = max(processed_ch_count, len(powers))
                else:
                    avg_powers[band] = 0.0
            
            if processed_ch_count == 0: return
            
            total_p = sum(avg_powers.values())
            if total_p < 0.1: return
            
            snapshot_updates = {k.lower(): v/total_p for k, v in avg_powers.items()}
            denom = snapshot_updates['alpha'] + snapshot_updates['theta']
            raw_ratio = (snapshot_updates['beta'] / denom) if denom > 0.001 else 0.0
            
            # ── Stage 1: Z-Score Normalization & Focus ──────────
            # Headband-on detection: signal QUALITY based, not spectral content.
            # Spectral content (alpha vs beta) tells you what the person is THINKING,
            # not whether the headband is on. A focused person has high beta = still on head.
            alpha_theta = snapshot_updates['alpha'] + snapshot_updates['theta']
            raw_headband_on = (
                len(valid_ch) >= 2 and          # At least 2 good electrodes = skin contact
                clean_ratio >= 0.4 and          # Reasonable clean window
                alpha_theta > 0.15              # Above pure noise floor
            )

            # ── Temporal Debounce: require 3 consecutive same-state samples to flip ──
            DEBOUNCE_THRESHOLD = 3
            if raw_headband_on:
                self._headband_stability_counter = min(self._headband_stability_counter + 1, DEBOUNCE_THRESHOLD)
            else:
                self._headband_stability_counter = max(self._headband_stability_counter - 1, -DEBOUNCE_THRESHOLD)

            if self._headband_stability_counter >= DEBOUNCE_THRESHOLD:
                headband_on = True
                self._headband_confirmed = True
            elif self._headband_stability_counter <= -DEBOUNCE_THRESHOLD:
                headband_on = False
                self._headband_confirmed = False
            else:
                headband_on = self._headband_confirmed  # Hold last confirmed state during transition

            focus_metric = 0.0
            headband_off = False
            if not headband_on:
                headband_off = True
                if not hasattr(self, '_headband_warn_t') or time.time() - self._headband_warn_t > 10:
                    self._headband_warn_t = time.time()
                    logger.info("HEADBAND OFF: No valid EEG contact detected. Focus frozen.")

            if not self._baseline_done:
                if headband_off:
                    # Reset any partial baseline data (don't calibrate on noise)
                    self._baseline_start_time = None
                    self._baseline_samples.clear()
                    self._iaf_psd_accumulator.clear()
                    # Band powers still flow to chart, but focus stays at 0
                else:
                    if self._baseline_start_time is None:
                        self._baseline_start_time = time.time()
                        logger.info("═══ BASELINE CALIBRATION STARTED (15s) — Headband detected on head ═══")

                    self._baseline_samples.append(raw_ratio)
                    if psd_sum_all is not None:
                        self._iaf_psd_accumulator.append((freqs, psd_sum_all / len(valid_ch)))

                    elapsed = time.time() - self._baseline_start_time
                    if elapsed >= 15.0:
                        # Z-score baseline: mean and std of resting-state ratio
                        self._baseline_ratio = float(np.median(self._baseline_samples))
                        self._baseline_std   = float(np.std(self._baseline_samples))
                        if self._baseline_std < 0.02:
                            self._baseline_std = 0.02  # Floor to prevent extreme Z-score amplification
                        if self._iaf_psd_accumulator:
                            all_psds = np.array([p for _, p in self._iaf_psd_accumulator])
                            avg_psd  = np.mean(all_psds, axis=0)
                            self._iaf       = self._find_iaf(self._iaf_psd_accumulator[0][0], avg_psd)
                            self._iaf_bands = self._get_iaf_bands(self._iaf)
                        self._baseline_done = True
                        logger.info(f"═══ BASELINE COMPLETE | mean={self._baseline_ratio:.4f} std={self._baseline_std:.4f} IAF={self._iaf:.1f}Hz ═══")
                    focus_metric = 0.3  # During calibration, hold at neutral

            else:
                if headband_off:
                    # Post-baseline headband off: freeze focus at 0
                    focus_metric = 0.0
                else:
                    # Z-score: how many SD away from resting state?
                    z = (raw_ratio - self._baseline_ratio) / self._baseline_std
                    # Map Z ∈ [-2, +6] SD → Focus ∈ [0, 0.95]
                    # 100% is impossible (capped at 95%). Typical range: 30-75%
                    # Z=0 → 25% (baseline), Z=+2 → 50%, Z=+4 → 75%, Z=+6 → 95%
                    focus_metric = (z + 2.0) / 8.0
                    focus_metric = float(np.clip(focus_metric, 0.0, 0.95))

                    if not hasattr(self, '_focus_log_counter'): self._focus_log_counter = 0
                    self._focus_log_counter += 1
                    if self._focus_log_counter % 20 == 0:
                        logger.info(f"FOCUS | raw={raw_ratio:.4f} | z={z:+.2f}SD | focus={focus_metric*100:.0f}% | clean={clean_ratio*100:.0f}%")

            # ── Stage 5: CFC Deep Focus (secondary metric) ──────────
            deep_focus = 0.0
            if self._baseline_done and 'AF7' in filtered and not headband_off:
                deep_focus = self._cfc_score(filtered['AF7'], fs=fs)

            # ── Mind State Classification (Muse-style Active/Neutral/Calm) ──
            # Based on alpha vs beta relative power:
            #   Alpha dominant (relaxation) → Calm
            #   Beta dominant (engagement)  → Active
            #   Balanced                    → Neutral
            alpha_p = snapshot_updates.get('alpha', 0)
            beta_p  = snapshot_updates.get('beta', 0)
            theta_p = snapshot_updates.get('theta', 0)
            
            if headband_off:
                mind_state = 'unknown'
            elif not self._baseline_done:
                mind_state = 'calibrating'
            else:
                # Alpha+Theta vs Beta comparison (Muse uses similar approach)
                calm_power   = alpha_p + theta_p * 0.5   # Alpha + some theta = relaxation
                active_power = beta_p                      # Beta = mental activity
                
                if calm_power > active_power * 1.3:
                    mind_state = 'calm'
                elif active_power > calm_power * 1.3:
                    mind_state = 'active'
                else:
                    mind_state = 'neutral'

            # Always update focus (0 when off, real when on)
            snapshot_updates['focus'] = focus_metric
            snapshot_updates['mind_state'] = mind_state
            snapshot_updates['deep_focus'] = deep_focus

            with self._lock:
                self._last_update = time.time()
                self.snapshot.timestamp  = time.time()
                # Signal_ok = False when headband is off
                self.snapshot.signal_ok  = (ampl_ok and not emg_detected and not headband_off)
                self.snapshot.emg_noise  = emg_detected
                self.snapshot.connected  = True
                self.snapshot.headband_on = not headband_off

                # Mind state (Muse-style Active/Neutral/Calm)
                prev_state = self.snapshot.mind_state
                self.snapshot.mind_state = mind_state
                if mind_state == prev_state and mind_state in ('calm', 'neutral', 'active'):
                    self.snapshot.mind_state_time += 0.5  # ~2 updates/sec
                else:
                    self.snapshot.mind_state_time = 0.0

                if ampl_ok:
                    # Band powers: EMA (α=0.03 ≈ 1.6s time constant — smooth like Muse app)
                    ema_alpha = 0.03
                    for k in ['delta', 'theta', 'alpha', 'beta', 'gamma']:
                        curr = snapshot_updates[k]
                        prev = self._smooth_hist[k]
                        new_val = prev * (1 - ema_alpha) + curr * ema_alpha
                        self._smooth_hist[k] = new_val
                        setattr(self.snapshot, k, round(new_val, 3))

                    # Stage 2: Focus output EMA (α=0.01 ≈ 5s time constant — slow stable needle)
                    focus_ema_alpha = 0.01
                    prev_focus = self._smooth_hist['focus']
                    smooth_focus = prev_focus * (1 - focus_ema_alpha) + snapshot_updates['focus'] * focus_ema_alpha
                    self._smooth_hist['focus'] = smooth_focus
                    self.snapshot.focus = round(float(np.clip(smooth_focus, 0.0, 0.95)), 2)

                    # Deep focus (CFC)
                    self.snapshot.deep_focus = round(deep_focus, 3)

                    # Blink rate (Fatigue Index)
                    self.snapshot.blink_rate = blink_rate

        except Exception as e:
            logger.error(f"Error processing BLE data: {e}")

    # ── LSL FALLBACK ──
    def _try_lsl_connect(self, timeout=3.0) -> bool:
        if not LSL_AVAILABLE: return False
        try:
            streams = resolve_byprop('type', 'EEG', timeout=timeout)
            if not streams: return False
            inlet = StreamInlet(streams[0])
            self._state = 'connected'
            threading.Thread(target=self._read_lsl_loop, args=(inlet,), daemon=True).start()
            return True
        except Exception as e:
            logger.warning(f"LSL connect failed: {e}")
            return False

    def _read_lsl_loop(self, inlet):
        while self._state == 'connected':
            try:
                sample, ts = inlet.pull_sample(timeout=1.0)
                if sample:
                    data = np.array(sample)
                    with self._lock:
                        self.snapshot.connected = True
                        self.snapshot.timestamp = time.time()
            except Exception:
                break
        self._state = 'idle'
    
    # ── SIMULATION ───────────────────────────────────────────
    def _simulate_forever(self):
        """Generate synthetic EEG-like data for demo."""
        logger.info("🔵 SIMULATION mode active.")
        t = 0
        with self._lock:
            self.snapshot.connected = True
            self.snapshot.signal_ok = True

        while self._sim_running:
            t += 0.1
            alpha = 0.4 + 0.2 * np.sin(t * 0.3)
            beta  = 0.3 + 0.15 * np.sin(t * 0.5 + 1)
            theta = 0.1 + 0.05 * np.cos(t * 0.2)
            delta = 0.05 + 0.02 * np.sin(t * 0.1)
            gamma = 0.02 + 0.01 * np.cos(t * 0.8)
            
            focus = max(0, min(1, beta * 0.6 + alpha * 0.4 + np.random.normal(0, 0.02)))
            with self._lock:
                self.snapshot.focus = round(focus, 4)
                self.snapshot.alpha = round(alpha, 4)
                self.snapshot.beta  = round(beta, 4)
                self.snapshot.theta = round(theta, 4)
                self.snapshot.delta = round(delta, 4)
                self.snapshot.gamma = round(gamma, 4)
                self.snapshot.timestamp = time.time()
            time.sleep(0.1)
        self._state = 'idle'


# ═══════════════════════════════════════════════════════════════
#  GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════
conn_mgr = ConnectionManager()

# Helper: Sensor diagnostics for the Sensor Test feature
def get_sensor_diagnostics():
    """Analyze all Muse 2 sensors and return per-channel diagnostics."""
    diag = {
        'connected': conn_mgr._state == 'connected',
        'eeg': {},
        'ppg': {},
        'accelerometer': {},
        'gyroscope': {},
        'iaf': conn_mgr._iaf if conn_mgr._baseline_done else None,
        'baseline_done': conn_mgr._baseline_done,
    }
    
    # ── EEG Channels ──
    ch_names = ['TP9', 'AF7', 'AF8', 'TP10']
    ch_locations = {
        'TP9': 'Left Ear', 'AF7': 'Left Forehead',
        'AF8': 'Right Forehead', 'TP10': 'Right Ear'
    }
    
    for ch in ch_names:
        buf = conn_mgr._buffers.get(ch, [])
        n = len(buf)
        
        if n < 10:
            diag['eeg'][ch] = {
                'location': ch_locations[ch],
                'status': 'NO_DATA',
                'samples': n,
                'amplitude': 0, 'noise': 0, 'peak_to_peak': 0,
                'waveform': []
            }
            continue
        
        data = np.array(buf[-256:], dtype=np.float64)  # Last 1 second
        amp = float(np.mean(np.abs(data)))
        noise = float(np.std(data))
        p2p = float(np.max(data) - np.min(data))
        
        # Status logic — tuned for real EEG vs. off-head noise
        if np.min(data) <= -999.0:
            status = 'FAIL'  # Rail voltage = no contact
        elif p2p > 600:
            status = 'FAIL'  # Environmental noise / no skin contact
        elif amp > 500:
            status = 'FAIL'  # Too high amplitude = not on head (real EEG is 10-100µV)
        elif p2p < 5:
            status = 'FAIL'  # Flat line = no signal
        elif noise > 100:
            status = 'WARN'  # Noisy but receiving
        elif noise < 2:
            status = 'WARN'  # Suspiciously quiet
        else:
            status = 'PASS'
        
        # Downsample waveform for display (64 points)
        step = max(1, len(data) // 64)
        waveform = data[::step][:64].tolist()
        
        diag['eeg'][ch] = {
            'location': ch_locations[ch],
            'status': status,
            'samples': n,
            'amplitude': round(amp, 1),
            'noise': round(noise, 1),
            'peak_to_peak': round(p2p, 1),
            'waveform': [round(v, 1) for v in waveform]
        }
    
    # ── PPG (Heart Rate Sensor) ──
    with conn_mgr._lock:
        ppg_data = conn_mgr.snapshot.ppg
        bpm = conn_mgr.snapshot.bpm
    
    ppg_active = any(abs(v) > 0.01 for v in ppg_data.values())
    diag['ppg'] = {
        'status': 'PASS' if ppg_active else 'NO_DATA',
        'bpm': bpm,
        'values': ppg_data
    }
    
    # ── Accelerometer ──
    with conn_mgr._lock:
        accel = conn_mgr.snapshot.accel
    
    accel_active = any(abs(v) > 0.01 for v in accel.values())
    diag['accelerometer'] = {
        'status': 'PASS' if accel_active else 'NO_DATA',
        'x': round(accel['x'], 3),
        'y': round(accel['y'], 3),
        'z': round(accel['z'], 3)
    }
    
    # ── Gyroscope ──
    with conn_mgr._lock:
        gyro = conn_mgr.snapshot.gyro
    
    gyro_active = any(abs(v) > 0.01 for v in gyro.values())
    diag['gyroscope'] = {
        'status': 'PASS' if gyro_active else 'NO_DATA',
        'x': round(gyro['x'], 3),
        'y': round(gyro['y'], 3),
        'z': round(gyro['z'], 3)
    }
    
    return diag

# ═══════════════════════════════════════════════════════════════
#  HTTP HANDLERS
# ═══════════════════════════════════════════════════════════════

# -- Static files --
async def handle_index(request: web.Request) -> web.Response:
    path = resource_path('dashboard.html')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return web.Response(text=f.read(), content_type='text/html')
    return web.Response(text="<h1>FocusFlow</h1><p>dashboard.html not found</p>", content_type='text/html')

async def handle_static(request: web.Request) -> web.Response:
    filename = request.match_info['filename']
    file_path = resource_path(filename)
    if not os.path.exists(file_path):
        return web.Response(status=404, text='Not found')
    ext_map = {'.css': 'text/css', '.js': 'application/javascript', '.png': 'image/png',
               '.jpg': 'image/jpeg', '.ico': 'image/x-icon', '.svg': 'image/svg+xml'}
    ext = os.path.splitext(filename)[1].lower()
    ct = ext_map.get(ext, 'application/octet-stream')
    with open(file_path, 'rb') as f:
        return web.Response(body=f.read(), content_type=ct)

async def handle_assets(request: web.Request) -> web.Response:
    """Serve files from assets/ subdirectory."""
    filepath = request.match_info['path']
    full = resource_path(os.path.join('assets', filepath))
    if not os.path.exists(full):
        return web.Response(status=404, text='Not found')
    ext_map = {'.css': 'text/css', '.js': 'application/javascript', '.png': 'image/png',
               '.jpg': 'image/jpeg', '.ico': 'image/x-icon', '.svg': 'image/svg+xml',
               '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf'}
    ext = os.path.splitext(filepath)[1].lower()
    ct = ext_map.get(ext, 'application/octet-stream')
    with open(full, 'rb') as f:
        return web.Response(body=f.read(), content_type=ct)

# -- Data API --
async def handle_focus(request: web.Request) -> web.Response:
    return web.json_response(conn_mgr.get_snapshot())

async def handle_status(request: web.Request) -> web.Response:
    return web.json_response({
        'connection_state': conn_mgr.state,
        'lsl_available': LSL_AVAILABLE,
        'ble_available': BLE_AVAILABLE,
    })

# -- System Control API --
async def handle_connect(request: web.Request) -> web.Response:
    logger.info("API: /api/system/connect requested")
    result = conn_mgr.connect()
    return web.json_response(result)

async def handle_disconnect(request: web.Request) -> web.Response:
    result = conn_mgr.disconnect()
    return web.json_response(result)

async def handle_system_status(request: web.Request) -> web.Response:
    logger.info("API: /api/system/status requested")
    return web.json_response({
        'connection_state': conn_mgr.state,
        'snapshot': conn_mgr.get_snapshot(),
    })

# -- Settings --
async def handle_settings(request: web.Request) -> web.Response:
    data = await request.json()
    logger.info(f"Settings updated: {data}")
    return web.json_response({'status': 'ok'})

# -- Calibration --
async def handle_calibrate(request: web.Request) -> web.Response:
    logger.info("Calibration requested by client.")
    return web.json_response({'status': 'calibration_started'})

# -- Session Start (reset baseline for new student) --
async def handle_session_start(request: web.Request) -> web.Response:
    """Reset baseline/IAF so a fresh calibration runs for this student."""
    logger.info("API: /api/session/start — resetting baseline for new student")
    conn_mgr.reset_baseline()
    return web.json_response({'status': 'ok', 'message': 'Baseline reset. Calibration will begin.'})

# -- Demo/Simulation (explicit only) --
async def handle_simulate(request: web.Request) -> web.Response:
    result = conn_mgr.start_simulation()
    return web.json_response(result)

# -- Sensor Test --
async def handle_sensor_test(request: web.Request) -> web.Response:
    diag = get_sensor_diagnostics()
    return web.json_response(diag)

# ═══════════════════════════════════════════════════════════════
#  PHASE 2 API HANDLERS — Student Management & Database
# ═══════════════════════════════════════════════════════════════
import database as db_module
import json as _json

# ── College ──
async def handle_college_add(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        result = db_module.add_college(
            name=data.get('name', ''),
            city=data.get('city', ''),
            board=data.get('board', '')
        )
        return web.json_response({'status': 'ok', 'data': result})
    except Exception as e:
        return web.json_response({'status': 'error', 'message': str(e)}, status=500)

async def handle_colleges_get(request: web.Request) -> web.Response:
    try:
        return web.json_response(db_module.get_colleges())
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# ── Class ──
async def handle_class_add(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        result = db_module.add_class(
            college_id=data.get('college_id', ''),
            name=data.get('name', '')
        )
        return web.json_response({'status': 'ok', 'data': result})
    except Exception as e:
        return web.json_response({'status': 'error', 'message': str(e)}, status=500)

async def handle_classes_get(request: web.Request) -> web.Response:
    try:
        college_id = request.rel_url.query.get('college_id', '')
        return web.json_response(db_module.get_classes(college_id))
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# ── Student ──
async def handle_student_add(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        result = db_module.add_student(
            class_id=data.get('class_id', ''),
            name=data.get('name', ''),
            roll_no=data.get('roll_no', ''),
            age=int(data.get('age') or 0),
            notes=data.get('notes', '')
        )
        return web.json_response({'status': 'ok', 'data': result})
    except Exception as e:
        return web.json_response({'status': 'error', 'message': str(e)}, status=500)

async def handle_students_get(request: web.Request) -> web.Response:
    try:
        class_id = request.rel_url.query.get('class_id', '')
        return web.json_response(db_module.get_students(class_id))
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def handle_students_search(request: web.Request) -> web.Response:
    try:
        q = request.rel_url.query
        results = db_module.search_students(
            college_name=q.get('college', ''),
            class_name=q.get('class_name', ''),
            student_name=q.get('name', '')
        )
        return web.json_response(results)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# ── Session ──
async def handle_session_save(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        result = db_module.save_session(
            student_id=data.get('student_id', ''),
            duration=int(data.get('duration', 0)),
            avg_focus=float(data.get('avg_focus', 0)),
            peak_focus=float(data.get('peak_focus', 0)),
            graph_data=data.get('graph_data', [])
        )
        return web.json_response({'status': 'ok', 'data': result})
    except Exception as e:
        return web.json_response({'status': 'error', 'message': str(e)}, status=500)

async def handle_sessions_get(request: web.Request) -> web.Response:
    try:
        student_id = request.rel_url.query.get('student_id', '')
        return web.json_response(db_module.get_sessions(student_id))
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# ── PDF Report ──
async def handle_report_generate(request: web.Request) -> web.Response:
    try:
        student_id = request.match_info['student_id']
        sessions = db_module.get_sessions(student_id)
        # Get student info from sessions (we embed it)
        student_info = request.rel_url.query
        student = {
            'name': student_info.get('name', 'Student'),
            'roll_no': student_info.get('roll_no', ''),
            'age': student_info.get('age', ''),
            'class_name': student_info.get('class_name', ''),
            'college_name': student_info.get('college_name', ''),
        }
        from reporting import generate_pdf_report
        pdf_bytes = generate_pdf_report(student, sessions)
        return web.Response(
            body=pdf_bytes,
            content_type='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="{student["name"]}_report.pdf"'}
        )
    except Exception as e:
        logger.error(f'Report error: {e}')
        return web.json_response({'error': str(e)}, status=500)

async def handle_db_status(request: web.Request) -> web.Response:
    logger.info("API: /api/db/status requested")
    return web.json_response({'connected': db_module.is_connected()})

async def handle_recent_sessions(request: web.Request) -> web.Response:
    """Fetch global recent sessions for the Database tab auto-load."""
    try:
        limit = int(request.rel_url.query.get('limit', 20))
        sessions = db_module.get_recent_sessions(limit=limit)
        return web.json_response(sessions)
    except Exception as e:
        logger.error(f"Handle recent sessions error: {e}")
        return web.json_response({'error': str(e)}, status=500)

# ── Delete Handlers ──
async def handle_college_delete(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        ok = db_module.delete_college(data.get('id', ''))
        return web.json_response({'status': 'ok' if ok else 'error'})
    except Exception as e:
        return web.json_response({'status': 'error', 'message': str(e)}, status=500)

async def handle_class_delete(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        ok = db_module.delete_class(data.get('id', ''))
        return web.json_response({'status': 'ok' if ok else 'error'})
    except Exception as e:
        return web.json_response({'status': 'error', 'message': str(e)}, status=500)

async def handle_student_delete(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        ok = db_module.delete_student(data.get('id', ''))
        return web.json_response({'status': 'ok' if ok else 'error'})
    except Exception as e:
        return web.json_response({'status': 'error', 'message': str(e)}, status=500)

async def handle_session_delete(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        ok = db_module.delete_session(data.get('id', ''))
        return web.json_response({'status': 'ok' if ok else 'error'})
    except Exception as e:
        return web.json_response({'status': 'error', 'message': str(e)}, status=500)

# ═══════════════════════════════════════════════════════════════
#  CORS MIDDLEWARE
# ═══════════════════════════════════════════════════════════════
@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        resp = web.Response()
    else:
        try:
            resp = await handler(request)
        except web.HTTPException as ex:
            resp = ex
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return resp

# ═══════════════════════════════════════════════════════════════
#  APP LIFECYCLE
# ═══════════════════════════════════════════════════════════════
async def on_app_startup(app):
    """Called when aiohttp starts. We capture the loop here."""
    loop = asyncio.get_running_loop()
    logger.info(f"App startup: capturing main loop {id(loop)}")
    conn_mgr.set_loop(loop)

async def on_app_cleanup(app):
    """Called on shutdown."""
    logger.info("App cleanup: disconnecting BLE...")
    conn_mgr.disconnect()

def create_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.on_startup.append(on_app_startup)
    app.on_cleanup.append(on_app_cleanup)

    # Routes
    app.router.add_get('/', handle_index)
    app.router.add_get('/assets/{path:.+}', handle_assets)
    app.router.add_get('/api/focus', handle_focus)
    app.router.add_get('/api/status', handle_status)
    app.router.add_get('/api/system/status', handle_system_status)
    app.router.add_post('/api/system/connect', handle_connect)
    app.router.add_post('/api/system/disconnect', handle_disconnect)
    app.router.add_post('/api/system/simulate', handle_simulate)
    app.router.add_post('/api/settings', handle_settings)
    app.router.add_post('/api/calibrate', handle_calibrate)
    app.router.add_get('/api/sensor_test', handle_sensor_test)
    # ── Phase 2: Student Management ──
    app.router.add_post('/api/college/add', handle_college_add)
    app.router.add_get('/api/colleges', handle_colleges_get)
    app.router.add_post('/api/class/add', handle_class_add)
    app.router.add_get('/api/classes', handle_classes_get)
    app.router.add_post('/api/student/add', handle_student_add)
    app.router.add_get('/api/students', handle_students_get)
    app.router.add_get('/api/students/search', handle_students_search)
    app.router.add_post('/api/session/save', handle_session_save)
    app.router.add_post('/api/session/start', handle_session_start)
    app.router.add_get('/api/sessions', handle_sessions_get)
    app.router.add_get('/api/report/{student_id}', handle_report_generate)
    app.router.add_get('/api/db/status', handle_db_status)
    app.router.add_get('/api/db/recent', handle_recent_sessions)
    # ── Delete routes ──
    app.router.add_post('/api/college/delete', handle_college_delete)
    app.router.add_post('/api/class/delete', handle_class_delete)
    app.router.add_post('/api/student/delete', handle_student_delete)
    app.router.add_post('/api/session/delete', handle_session_delete)
    
    # Static fallback
    app.router.add_get('/{filename}', handle_static)

    return app

# ═══════════════════════════════════════════════════════════════
#  NATIVE WINDOW LAUNCHER  (Edge/Chrome --app mode)
# ═══════════════════════════════════════════════════════════════
import subprocess
import shutil

def find_browser():
    """Find Edge or Chrome executable for --app mode (frameless native window)."""
    candidates = [
        # Microsoft Edge (guaranteed on Windows 10/11)
        os.path.expandvars(r'%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe'),
        os.path.expandvars(r'%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe'),
        # Google Chrome
        os.path.expandvars(r'%PROGRAMFILES%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    # Last resort: try shutil
    for name in ['msedge', 'chrome', 'google-chrome']:
        found = shutil.which(name)
        if found:
            return found
    return None

def launch_app_window(url: str):
    """Launch browser in --app mode (frameless, no address bar, looks native)."""
    browser = find_browser()
    if not browser:
        logger.warning("No Edge/Chrome found — opening default browser")
        import webbrowser
        webbrowser.open(url)
        return None

    browser_name = 'Edge' if 'edge' in browser.lower() else 'Chrome'
    logger.info(f"Launching native window via {browser_name} --app mode")

    # --app gives a clean frameless window — no tabs, no address bar
    proc = subprocess.Popen([
        browser,
        f'--app={url}',
        '--window-size=1400,900',
        '--disable-extensions',
        '--disable-sync',
        '--no-first-run',
        '--no-default-browser-check',
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc

# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print()
    print("=" * 60)
    print("  FocusFlow — Precision Neurofeedback")
    print("=" * 60)
    print(f"  BLE (Direct) : {'OK (muse_ble)' if BLE_AVAILABLE else 'OFF'}")
    print(f"  LSL Fallback : {'OK (pylsl)' if LSL_AVAILABLE else 'OFF'}")
    print("=" * 60)
    print()

    # Launch native window after server starts
    url = f'http://localhost:{config.PORT}/'

    def _open_window():
        time.sleep(1.5)  # Let server start
        launch_app_window(url)
    threading.Thread(target=_open_window, daemon=True).start()

    # Run server (blocks until Ctrl+C)
    app = create_app()
    web.run_app(app, host=config.HOST, port=config.PORT, print=None, access_log=logger)
