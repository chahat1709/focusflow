
import numpy as np
import datetime
from scipy.signal import butter, lfilter, iirnotch, find_peaks
from src.backend.config import FS, PPG_FS

class SmartProcessor:
    def __init__(self, notch_freq=50):
        # Dual Notch (50Hz EU + 60Hz US) for Global Medical Compliance
        self.notch50_b, self.notch50_a = iirnotch(50.0, 30.0, FS)
        self.notch60_b, self.notch60_a = iirnotch(60.0, 30.0, FS)
        self.bp_b, self.bp_a = butter(4, [0.5, 50.0], btype='band', fs=FS)
        self.filters = {} # State preservation
        self.iaf = 10.0 # Default
        self.active_notch = notch_freq # 50, 60, or 'dual'
        
        # PHASE 1: Timestamp Synchronization
        self.sample_count = 0  # Running counter
        self.session_start_time = None  # First timestamp received
        self.corrected_timestamps = []  # For verification

    def process_sample(self, sample, timestamp=None):
        """
        Main Entry Point for EEG Data from BeastStreamer.
        sample: [TP9, AF7, AF8, TP10] (floats)
        timestamp: LSL timestamp (float)
        """
        from src.backend.config import state, brackets, buffers, indices, BUFF_SIZE, state_lock, calib
        
        # PHASE 1: Monotonic Timestamp Correction
        if timestamp:
            if self.session_start_time is None:
                self.session_start_time = timestamp
                self.sample_count = 0
            
            # Calculate mathematically perfect timestamp
            corrected_ts = self.session_start_time + (self.sample_count / FS)
            self.sample_count += 1
        else:
            corrected_ts = None
        
        # 1. Update Ring Buffer
        idx = indices['eeg']
        buffers['eeg'][idx] = sample # Write to shared buffer
        
        # --- RECORDING HOOK ---
        # Write every sample? 256Hz is fast, but CSV can handle it.
        # Format: [Time, 'EEG', TP9, AF7, AF8, TP10, Focus]
        from src.backend.config import rec
        # SAFE: Read state with lock
        with state_lock:
            is_recording = state.get('recording', False)
            current_focus = state.get('focus', 0)
            
        if is_recording and rec.get('writer'):
            try:
                if corrected_ts:  # Use CORRECTED timestamp (Phase 1 fix)
                    ts_str = f"{corrected_ts:.6f}"
                else:
                    ts_str = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    
                rec['writer'].writerow([ts_str, 'EEG', sample[0], sample[1], sample[2], sample[3], current_focus])
                
                # PHASE 4: Periodic flush (every 1 second = every 256 samples)
                if self.sample_count % 256 == 0:
                    rec.get('file', None) and rec['file'].flush()
            except Exception as e:
                print(f"CSV WRITE ERROR: {e}")  # DEBUG
        
        # 2. Increment & Wrap
        next_idx = (idx + 1) % BUFF_SIZE
        indices['eeg'] = next_idx
        
        # 3. Process Window (Every ~4 samples or approx 60Hz update rate to save CPU?)
        # Muse is 256Hz. Processing every sample is expensive and unnecessary for UI.
        # Let's process every 8th sample (32Hz update)
        if idx % 8 == 0:
            results = self.process_window(buffers['eeg'], idx)
            
            if results:
                with state_lock:
                    # state['bands'] = results['bands'] # Smooth update?
                    # Exponential Moving Average for smoother UI
                    for band in state['bands']:
                        state['bands'][band] = state['bands'][band] * 0.7 + results['bands'][band] * 0.3
                        
                    state['focus'] = state['focus'] * 0.9 + results['focus_score'] * 0.1
                    state['focus'] = max(0.0, min(1.0, state['focus'])) # Clamp
                    
                    # Update FFT for Visualizer
                    state['raw_trace'] = sample # Just send current sample for "Scope"
                    # Store RAW EEG for export (NOW INSIDE LOCK)
                    state['raw_eeg'] = list(sample[:4]) if len(sample) >= 4 else [0,0,0,0]
                    
                    # PHASE 2: Signal Quality Engine
                    # Calculate contact quality (variance of last 256 samples = 1 second window)
                    quality_status = self.calculate_signal_quality(buffers['eeg'], idx)
                    state['signal_quality'] = quality_status
                    
                    # --- CALIBRATION HOOK ---
                    is_calibrating = state.get('calibrating', False)
                    
                # CALIBRATION LOGIC (Outside lock to avoid blocking)
                if is_calibrating and 'fft_val' in results:
                    # Append safely
                    calib['data'].append(list(results['fft_val'][:60]))
                    # Cap at 1800 frames (60 seconds @ 30Hz)
                    if len(calib['data']) > 1800:
                        calib['data'].pop(0)
                    # Update progress (0 to 100 based on target 600 frames ~20s)
                    calib['progress'] = min(100, int((len(calib['data']) / 600) * 100))
                    
                    # AUTO-FINISH Calibration after ~20 seconds (ONLY ONCE)
                    if len(calib['data']) == 600:  # CHANGED: Only trigger exactly at 600
                        print("🎯 Calibration threshold reached, triggering IAF calculation...")
                        self.calibrate_iaf(calib['data'])

                with state_lock:
                    # MULTI-MODAL FOCUS CALCULATION
                    # Get current sensor states
                    hrv_rmssd = state.get('rmssd', 50)
                    gyro_motion = state.get('motion_level', 0)
                    
                    # Calculate enhanced focus
                    mm_focus, components = self.calculate_multimodal_focus(
                        results['bands'],
                        hrv_rmssd,
                        gyro_motion,
                        results['valence']
                    )
                    
                    # Update with multi-modal score
                    state['focus'] = state['focus'] * 0.9 + mm_focus * 0.1
                    state['focus'] = max(0.0, min(1.0, state['focus']))
                    state['focus_components'] = components
    
    def process_ppg(self, sample):
        """Buffer PPG and calculate heart rate + HRV"""
        from src.backend.config import buffers, indices, PPG_FS, state, state_lock
        
        # sample is usually [Ambient, IR, Red] for Muse 2
        # We focus on IR/Red for HR.
        
        idx = indices['ppg']
        buffers['ppg'][idx] = sample
        indices['ppg'] = (idx + 1) % (PPG_FS * 10) # 10s buffer
        
        with state_lock:
            # Store raw PPG
            state['raw_ppg'] = list(sample[:3]) if len(sample) >= 3 else [0,0,0]
            
        # RECORDING HOOK
        from src.backend.config import rec
        with state_lock:
            is_recording = state.get('recording', False)
            current_bpm = state.get('bpm', 0)
            
        if is_recording and rec.get('writer'):
            try:
                ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                rec['writer'].writerow([ts, 'PPG', sample[0], sample[1], sample[2], 0, current_bpm])
            except Exception as e:
                print(f"PPG CSV WRITE ERROR: {e}")
        
        # Calculate BPM every 1 second (approx 64 samples)
        if idx % 64 == 0:
            bpm = self.calculate_bpm(buffers['ppg'])
            if bpm > 30 and bpm < 180:
                with state_lock:
                    state['bpm'] = int(state['bpm'] * 0.8 + bpm * 0.2) # Smooth it
            
            # Calculate HRV every 30 seconds (1920 samples)
            if idx % (PPG_FS * 30) == 0:
                rmssd, ready = self.calculate_hrv_rmssd(buffers['ppg'], idx)
                with state_lock:
                    state['rmssd'] = rmssd
                    state['hrv_ready'] = ready
                    if ready:
                        print(f"💓 HRV: {rmssd}ms RMSSD")
                    
    def process_imu(self, sample, sensor_type='acc'):
        """Handle Accelerometer and Gyroscope"""
        from src.backend.config import state, state_lock
        
        with state_lock:
            if sensor_type == 'acc':
                # Store raw for export
                state['raw_acc'] = list(sample[:3]) if len(sample) >= 3 else [0,0,0]
                
                # sample = [x, y, z]
                # Calculate Pitch/Roll
                x, y, z = sample
                pitch = np.arctan2(y, np.sqrt(x*x + z*z)) * 180 / np.pi
                roll = np.arctan2(-x, z) * 180 / np.pi
                state['posture_values'] = {'pitch': pitch, 'roll': roll}
                
                # Simple posture check
                if pitch > 30: state['posture'] = 'Slouching'
                elif pitch < -30: state['posture'] = 'Looking Up'
                else: state['posture'] = 'Good'
                
            elif sensor_type == 'gyro':
                 state['gyro'] = {'x': sample[0], 'y': sample[1], 'z': sample[2]}
                 # Detect head motion intensity
                 motion = np.sqrt(sample[0]**2 + sample[1]**2 + sample[2]**2)
                 state['motion_level'] = motion
                 # Store raw for multi-modal focus
                 state['raw_gyro'] = list(sample[:3]) if len(sample) >= 3 else [0,0,0]
                 # print(f"DEBUG GYRO: {state['raw_gyro']}")
        
    def calculate_hrv_rmssd(self, ppg_buffer, current_idx):
        """
        Calculate Heart Rate Variability using RMSSD method.
        RMSSD = Root Mean Square of Successive Differences between R-R intervals.
        
        Returns: (rmssd_ms, ready)
        """
        try:
            # We need at least 30 seconds of data for reliable HRV
            required_samples = PPG_FS * 30  # 30 seconds
            
            if current_idx < required_samples:
                return 0, False
            
            # Extract recent window
            if current_idx >= required_samples:
                window = ppg_buffer[current_idx-required_samples:current_idx, 1].copy()  # Use IR channel
            else:
                window = np.concatenate((ppg_buffer[current_idx-required_samples:, 1], ppg_buffer[:current_idx, 1]))
            
            # Simple peak detection for R-R intervals
            # PPG peaks correspond to heartbeats
            from scipy.signal import find_peaks
            peaks, _ = find_peaks(window, distance=PPG_FS*0.4, height=np.mean(window))  # Min 0.4s between beats (150 BPM max)
            
            if len(peaks) < 5:
                return 0, False
            
            # Calculate intervals (in samples)
            intervals_samples = np.diff(peaks)
            
            # Convert to milliseconds
            intervals_ms = (intervals_samples / PPG_FS) * 1000
            
            # Calculate RMSSD
            successive_diffs = np.diff(intervals_ms)
            rmssd = np.sqrt(np.mean(successive_diffs ** 2))
            
            return int(rmssd), True
            
        except Exception as e:
            print(f"HRV Calculation Error: {e}")
            return 0, False
    
    def calculate_multimodal_focus(self, eeg_bands, hrv_rmssd, gyro_motion, valence):
        """
        Calculate Multi-Modal Focus Score combining:
        - EEG (Cognitive Load): Beta/Gamma vs Theta/Alpha
        - HRV (Arousal): Optimal zone detection
        - Gyro (Stillness): Movement disrupts focus
        - Valence (Mood): Positive emotion enhances focus
        
        Returns: (focus_score, components_dict)
        """
        try:
            # 1. EEG FACTOR (0-1)
            # High Beta/Gamma with low Theta/Alpha = High Focus
            beta_gamma = eeg_bands['beta'] + eeg_bands['gamma']
            theta_alpha = eeg_bands['theta'] + eeg_bands['alpha']
            
            if theta_alpha < 1e-6:
                eeg_raw = 0.5
            else:
                eeg_raw = beta_gamma / theta_alpha
            
            # Normalize using tanh (sigmoid-like, 0-1 range)
            eeg_factor = np.tanh(eeg_raw / 2)
            
            # 2. HRV FACTOR (0-1)
            # Optimal HRV zone: 40-60ms RMSSD
            # Too low = stressed, too high = under-aroused
            optimal_hrv = 50
            hrv_deviation = abs(hrv_rmssd - optimal_hrv)
            hrv_factor = max(0, 1.0 - (hrv_deviation / 50))  # Normalize deviation
            
            # 3. STILLNESS FACTOR (0-1)
            # Gyro magnitude in deg/s
            # Low motion = high stillness = better focus
            stillness_factor = np.exp(-gyro_motion / 20)  # Exponential decay
            
            # 4. MOOD FACTOR (0-1)
            # Valence ranges from -1 (negative) to +1 (positive)
            # Map to 0-1 range
            mood_factor = (valence + 1) / 2
            
            # WEIGHTED COMBINATION
            # EEG is most important (0.5), others modulate (0.2, 0.15, 0.15)
            weights = {'eeg': 0.5, 'hrv': 0.2, 'stillness': 0.15, 'mood': 0.15}
            
            focus_score = (
                weights['eeg'] * eeg_factor +
                weights['hrv'] * hrv_factor +
                weights['stillness'] * stillness_factor +
                weights['mood'] * mood_factor
            )
            
            # Clamp to 0-1 range
            focus_score = max(0.0, min(1.0, focus_score))
            
            components = {
                'eeg_factor': float(eeg_factor),
                'hrv_factor': float(hrv_factor),
                'stillness_factor': float(stillness_factor),
                'mood_factor': float(mood_factor)
            }
            
            return focus_score, components
            
        except Exception as e:
            print(f"Multi-Modal Focus Error: {e}")
            return 0.5, {'eeg_factor': 0.5, 'hrv_factor': 0.5, 'stillness_factor': 0.5, 'mood_factor': 0.5}


    def process_window(self, buffer, current_idx):
        try:
            # DEBUG
            # print(f"⚙️ PROCESSOR: Called with idx {current_idx}")
            
            # Extract last 1 second (256 samples) from Ring Buffer
            rows = len(buffer)
            if current_idx >= 256:
                window = buffer[current_idx-256:current_idx].copy()
            else:
                # Wrap around
                window = np.concatenate((buffer[current_idx-256:], buffer[:current_idx])).copy()
            
            if window.ndim != 2 or window.shape[1] < 4:
                print(f"⚠️ Invalid Window Shape: {window.shape}")
                return None
            
            # 1. Artifact Check (Fast Fail)
            is_clean, reason = self.check_artifact(window)
            if not is_clean:
                # pass # ALWAYS PROCESS (For Debugging/Visuals)
                # return None # Skip noisy windows
                # print(f"⚠️ Artifact: {reason}")
                pass # BYPASS: We want to see the dirty data instead of nothing
            
            # 1.1 EVENT TRIGGER DETECTION (Blink/Jaw)
            self.detect_artifacts_event(window)
            
            # 2. NOISE GATING (The "Surgical" Clean)
            # Removes jaw clench high-freq noise without losing Alpha
            window = self.gate_noise(window)
            
            # 3. Filter (Notch + Bandpass)
            # process_eeg handles the per-channel filtering with state preservation
            filtered = self.process_eeg(window)
            
            # 4. Compute Powers (FFT)
            bands, fft_vals, fft_freq = self.compute_powers(filtered)
            
            # 3.1 Advanced Metrics (Valence/Coherence)
            valence, coherence = self.calculate_metrics(filtered)

            # 4. Focus Score (Beta/Theta ratio or complex metric)
            # Simple Beta/Theta + Alpha
            focus_score = (bands['beta'] + bands['gamma']) / (bands['theta'] + bands['alpha'] + 1e-6)
            # Log transform for stability
            focus_score = np.log10(focus_score + 1)
            
            return {
                'bands': bands,
                'fft': list(fft_vals[:60]), # Send first 60 bins (approx 0-60Hz) to save bandwidth
                'fft_val': fft_vals,
                'fft_freq': fft_freq,
                'focus_score': focus_score,
                'valence': valence,
                'coherence': coherence
            }
        except Exception as e:
            print(f"ProcessWindow Error: {e}")
            return None

    def process_eeg(self, sample_chunk):
        # Sanitize NaNs
        sample_chunk = np.nan_to_num(sample_chunk)
        
        # 4 Channel Loop
        filtered = np.zeros_like(sample_chunk)
        for i in range(4):
            # Initialize filter states with correct dimensions if not exists
            if i not in self.filters:
                notch_order = max(len(self.notch50_a), len(self.notch50_b)) - 1
                bp_order = max(len(self.bp_a), len(self.bp_b)) - 1
                self.filters[i] = {
                    'n50': np.zeros((notch_order,)),
                    'n60': np.zeros((notch_order,)),
                    'b': np.zeros((bp_order,))
                }
            
            # Dual Notch (Configurable)
            out = sample_chunk[:, i]
            
            # Apply 50Hz if requested or dual
            if self.active_notch in [50, 'dual', 50.0]:
                out, self.filters[i]['n50'] = lfilter(self.notch50_b, self.notch50_a, out, zi=self.filters[i]['n50'])
                
            # Apply 60Hz if requested or dual
            if self.active_notch in [60, 'dual', 60.0]:
                out, self.filters[i]['n60'] = lfilter(self.notch60_b, self.notch60_a, out, zi=self.filters[i]['n60'])
            
            # Bandpass filter
            out, self.filters[i]['b'] = lfilter(self.bp_b, self.bp_a, out, zi=self.filters[i]['b'])
            filtered[:, i] = out
        return filtered

    def gate_noise(self, window):
        """
        Spectral Noise Gating.
        If broad spectrum noise (muscle) is detected, clamp high frequencies.
        Simple Time-Domain Heuristic:
        If variance of 1st derivative (high freq content) is too high > dampen it.
        """
        try:
            # Calculate "Roughness" (High Freq Energy)
            # Diff = adjacent sample difference. High for Gamma/Muscle. Low for Alpha.
            diff = np.diff(window, axis=0) 
            roughness = np.std(diff, axis=0)
            
            # Threshold (Empirical for EEG ~ 15-20uV jump per sample is huge)
            # If roughness > 20, we likely have muscle noise.
            # NEW: ACTIVE GYRO GATING (Physics-Based Rejection)
            # Use real gyroscope data to detect head movement
            from src.backend.config import state
            motion = state.get('motion_level', 0)
            
            # 40 deg/s = Moderate head shake
            if motion > 40.0:
                 # Aggressive damping for Beta/Gamma during movement
                 # print(f"🌊 MOTION GATE: {motion:.1f} deg/s - dampening EEG")
                 for i in range(4):
                      w = window[:, i]
                      # Heavy smoothing (Moving Average of 5)
                      smoothed = np.convolve(w, np.ones(5)/5, mode='same')
                      window[:, i] = smoothed
            else:
                 # Standard Impulse Noise Gating (Jaw Clench)
                for i in range(4):
                    if roughness[i] > 15.0:
                        w = window[:, i]
                        smoothed = np.convolve(w, np.ones(3)/3, mode='same')
                        window[:, i] = smoothed
                        # print(f"🛡️ GATED Ch {i}: Roughness {roughness[i]:.1f}")
            
            return window
        except:
            return window

    def calibrate_iaf(self, calibration_data):
        """
        Finds the Individual Alpha Frequency (IAF) Peak from accumulated FFT data.
        Search Range: 7Hz - 13Hz.
        """
        try:
            # Check if we have enough data (calibration_data is list of FFT frames)
            if not calibration_data or len(calibration_data) < 10:
                print("⚠️ Not enough data for calibration")
                return

            print(f"🧠 Running IAF Calibration on {len(calibration_data)} frames...")
            
            # Convert list to array: [frames, freq_bins]
            fft_history = np.array(calibration_data)
            
            # Reconstruct Frequency Axis (assuming 60 bins = 0-60Hz approx)
            # We need exact freq matches.
            # In process_window we passed: list(fft_vals[:60])
            # Freq resolution = FS / N_FFT. N_FFT = 256 (window size)
            # Bin width = 256 / 256 = 1 Hz per bin.
            # Wait, rfft returns N/2 + 1 bins. 256 samples -> 129 bins.
            # 256Hz / 2 = 128Hz Nyquist.
            # So 129 bins cover 0-128Hz. 
            # Bin size = 1 Hz per bin? Correct. 
            # freq[k] = k * FS / N
            # freq[10] = 10 * 1 = 10Hz.
            
            freq_axis = np.fft.rfftfreq(256, 1.0/FS)[:60] # First 60 bins matching saved data
            
            peak_freq = self.find_peak_alpha(fft_history, freq_axis)
            
            from src.backend.config import state, state_lock
            with state_lock:
                state['iaf'] = peak_freq
                state['calibrating'] = False
                
        except Exception as e: 
            print(f"Calibration Error: {e}")

    def find_peak_alpha(self, fft_history, freq_axis):
        """
        Actual Math for IAF.
        averaged_fft: mean of all FFT frames.
        """
        try:
            # Average all frames
            avg_spectrum = np.mean(fft_history, axis=0)
            
            # Filter for Alpha Range (7-13Hz)
            # Note: with 1Hz bins, this is just indices 7 to 13.
            idx = np.where((freq_axis >= 7.0) & (freq_axis <= 13.0))[0]
            
            if len(idx) == 0:
                 print("⚠️ No Alpha bins found.")
                 return 10.0

            alpha_region = avg_spectrum[idx]
            alpha_freqs = freq_axis[idx]
            
            # Find Peak (Index within the region)
            local_peak_idx = np.argmax(alpha_region)
            peak_freq = alpha_freqs[local_peak_idx]
            
            # Sanity Check (if flat or edge)
            # Gravity Center method might be better if noisy, but Peak is standard IAF.
            
            print(f"🎯 NEW IAF CALCULATED: {float(peak_freq):.2f} Hz (Standard: 10Hz)")
            return float(peak_freq)
            
        except Exception as e:
            print(f"IAF Math Error: {e}")
            return 10.0

    def calculate_metrics(self, filtered_data):
        """
        Calculates Valence (Asymmetry) and Coherence.
        Channels: 0=TP9 (Left), 1=AF7 (Left Front), 2=AF8 (Right Front), 3=TP10 (Right)
        """
        # AF7 vs AF8 for Frontal Asymmetry
        left_front = filtered_data[:, 1]
        right_front = filtered_data[:, 2]

        # 1. Powers (using simplified Periodogram)
        l_fft = np.absolute(np.fft.rfft(left_front * np.hanning(len(left_front))))
        r_fft = np.absolute(np.fft.rfft(right_front * np.hanning(len(right_front))))
        freqs = np.fft.rfftfreq(len(left_front), 1.0/FS)
        
        # Alpha Indices (Dynamic IAF)
        alpha_low = max(4, self.iaf - 2)
        alpha_high = min(15, self.iaf + 2)
        idx = np.where((freqs >= alpha_low) & (freqs <= alpha_high))[0]
        
        l_alpha = np.mean(l_fft[idx])
        r_alpha = np.mean(r_fft[idx])
        
        # VALENCE: ln(Right) - ln(Left)
        # Higher Result = Relative Left Activation (Positive Mood)
        valence = np.log(r_alpha + 1e-6) - np.log(l_alpha + 1e-6)
        
        # COHERENCE (Simple Pearson Correlation of Envelopes for speed)
        # Real spectral coherence is heavy. Pearson of filtered alpha is decent proxy for synchrony.
        coherence = np.corrcoef(left_front, right_front)[0, 1]
        
        return valence, coherence

    def compute_powers(self, data):
        """
        Spatially Aware Power Calculation.
        Frontal (AF7, AF8) -> Focus (Beta/Gamma)
        Posterior (TP9, TP10) -> Relax (Alpha/Theta)
        """
        # Separate Channels
        # TP9 (0), AF7 (1), AF8 (2), TP10 (3)
        try:
            posterior = data[:, [0, 3]]
            frontal = data[:, [1, 2]]
            
            # FFT for Visualization (Global Average)
            avg = np.mean(data, axis=1)
            fft_vals = np.absolute(np.fft.rfft(avg * np.hanning(len(avg))))
            fft_freq = np.fft.rfftfreq(len(avg), 1.0/FS)
            
            # Helper for band power
            def get_band_power(chunk, f_low, f_high):
                # Average channels roughly
                sig = np.mean(chunk, axis=1)
                f_vals = np.absolute(np.fft.rfft(sig * np.hanning(len(sig))))
                freqs = np.fft.rfftfreq(len(sig), 1.0/FS)
                idx = np.where((freqs >= f_low) & (freqs <= f_high))[0]
                return np.mean(f_vals[idx]) if len(idx) > 0 else 0.0

            # SMART BANDS (Based on IAF)
            # Using spatially relevant sensors for each band
            bands = {
                'delta': get_band_power(data, 0.5, 4), # Global
                'theta': get_band_power(data, max(1, self.iaf - 6), max(4, self.iaf - 2)), # Global (Memory)
                
                # Alpha is dominant in Posterior (Visual Cortex)
                'alpha': get_band_power(posterior, max(4, self.iaf - 2), min(15, self.iaf + 2)), 
                
                # Beta is dominant in Frontal (Prefrontal Cortex - Executive Function)
                'beta':  get_band_power(frontal, min(15, self.iaf + 2), 30),
                
                'gamma': get_band_power(frontal, 30, 45) # Frontal Gamma (Cognitive Binding)
            }
                
            return bands, fft_vals, fft_freq
        except Exception as e:
            print(f"ComputePowers Error: {e}")
            return {}, [], []

    def calculate_bpm(self, ppg_buffer):
        """
        Robust BPM Calculation with Auto-Channel Selection.
        """
        try:
            # 1. Channel Selection (Best Cardiac Signal)
            # We look for the channel with highest variance in 1-3Hz (Heart Rate Band)
            best_channel = 1
            max_var = 0
            
            # Filter constants
            sos = butter(4, [0.8, 3.5], btype='band', fs=PPG_FS, output='sos')
            from scipy.signal import sosfilt
            
            # Check all 3 channels (Ambient, IR, Red)
            for i in range(ppg_buffer.shape[1]):
                raw = ppg_buffer[:, i]
                clean = sosfilt(sos, raw - np.mean(raw))
                var = np.var(clean)
                if var > max_var:
                    max_var = var
                    best_channel = i
            
            # 2. Process Best Channel
            signal = ppg_buffer[:, best_channel]
            
            # Robust Normalization (Percentiles to ignore artifacts)
            # Clip outliers
            p5, p95 = np.percentile(signal, [5, 95])
            signal = np.clip(signal, p5, p95)
            # Z-Score
            signal = (signal - np.mean(signal)) / (np.std(signal) + 1e-6)
            
            # 3. Filtering
            filtered_signal = sosfilt(sos, signal)
            
            # 4. Dynamic Peak Detection
            # Find peaks that are locally prominent
            # distance=PPG_FS*0.35 (limit to ~170 BPM max)
            peaks, properties = find_peaks(filtered_signal, distance=int(PPG_FS*0.35), prominence=0.3)
            
            # DEBUG: Trace BPM logic
            if len(peaks) > 0:
                 pass # print(f"DEBUG BPM: Found {len(peaks)} peaks in buffer")
            else:
                 pass # print("DEBUG BPM: No peaks found")

            if len(peaks) > 1:
                diffs = np.diff(peaks) # Samples between peaks
                
                # Use MEDIAN to ignore missed beats or double-counts
                median_dist = np.median(diffs)
                
                # Convert to BPM
                bpm = 60.0 / (median_dist / PPG_FS)
                
                # Sanity Check (40-180 BPM)
                if 40 <= bpm <= 180:
                     # --- HRV / RMSSD ---
                    rr_intervals_ms = (diffs / PPG_FS) * 1000.0
                    sdiff = np.diff(rr_intervals_ms)
                    rmssd = np.sqrt(np.mean(sdiff**2)) if len(sdiff) > 0 else 0
                    
                    print(f"💓 BPM CALC: {bpm:.1f} | RMSSD: {rmssd:.1f}")
                    return bpm, rmssd
                else:
                    print(f"⚠️ BPM Out of Range: {bpm:.1f}")
                
        except Exception as e: 
            print(f"BPM Error: {e}") 
            pass
            
        return 0, 0

    def check_artifact(self, signal_chunk):
        """
        ADVANCED ARTIFACT KILL-SWITCH
        Returns: (is_clean, reason)
        """
        # 1. FLATLINE / NaN DETECTOR
        if np.any(np.isnan(signal_chunk)):
            return False, "nan"
            
        var = np.var(signal_chunk)
        if var == 0:
            return False, "flatline"

        # 2. VARIANCE GATE (Head Movement)
        # If signal is jumping around too much (High variance)
        if var > 800: 
            return False, "noise"
            
        # 3. AMPLITUDE GATE (Blink / Jaw)
        # CRITICAL FIX: Remove DC Offset before checking amplitude!
        # Raw EEG often has huge offsets (-400uV, etc).
        centered = signal_chunk - np.mean(signal_chunk, axis=0)
        
        # 800uV is a generous ceiling (Blinks are ~500uV)
        if np.max(np.abs(centered)) > 800: 
             return False, "amplitude"

    def detect_artifacts_event(self, window):
        """
        Detects specific biological events:
        1. BLINK: Low frequency, high amplitude spike (>800uV) usually in frontal ch.
        2. JAW CLENCH: High frequency, broadband noise across all channels.
        """
        from src.backend.config import state, state_lock
        
        # --- BLINK DETECTION ---
        # Blinks are huge spikes, mostly in AF7/AF8
        frontal_avg = np.mean(window[:, 1:3], axis=1) # AF7, AF8
        centered = frontal_avg - np.mean(frontal_avg)
        peak = np.max(np.abs(centered))
        
        is_blink = False
        if peak > 600: # Slightly lower threshold for detection than rejection
            is_blink = True
            
        # --- JAW CLENCH DETECTION ---
        # Jaw clench introduces high power in >20Hz range
        # Use simple roughness (diff) check
        diff = np.diff(window, axis=0) 
        roughness = np.std(diff, axis=0)
        avg_roughness = np.mean(roughness)
        
        is_clench = False
        if avg_roughness > 30.0: # Normal is < 10
            is_clench = True
            
        # Update State (Transient flags)
        with state_lock:
            state['blink'] = is_blink
            state['jaw_clench'] = is_clench
            
            if is_blink: 
                state['blink_count'] += 1
                # print("👁️ BLINK DETECTED")
            
            if is_clench:
                state['posture'] = "Jaw Clench"
                # print("😬 JAW CLENCH DETECTED")

        return is_blink, is_clench

        return True, "clean"

    def calculate_signal_quality(self, buffer, current_idx):
        """
        PHASE 2: Signal Quality Engine
        Calculate contact quality for each EEG channel
        """
        from src.backend.config import BUFF_SIZE
        
        window_size = min(256, BUFF_SIZE)
        start_idx = (current_idx - window_size + 1) % BUFF_SIZE
        
        if start_idx < current_idx:
            window = buffer[start_idx:current_idx + 1]
        else:
            window = np.concatenate([buffer[start_idx:], buffer[:current_idx + 1]])
        
        quality_status = {}
        for ch in range(4):
            if len(window) < 10:
                quality_status[f'ch{ch+1}'] = {'status': 'unknown', 'variance': 0}
                continue
                
            variance = np.var(window[:, ch])
            
            if variance < 50:
                status = 'good'
            elif variance < 200:
                status = 'adjust'
            else:
                status = 'poor'
            
            quality_status[f'ch{ch+1}'] = {'status': status, 'variance': float(variance)}
        
        return quality_status


processor = SmartProcessor()
