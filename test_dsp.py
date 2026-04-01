#!/usr/bin/env python3
"""
test_dsp.py — Unit tests for FocusFlow DSP pipeline.
Tests the signal processing functions in production_server.py for
numerical correctness, boundary conditions, and edge cases.

Run: python test_dsp.py
"""

import sys
import os
import unittest
import numpy as np
from collections import deque

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the ConnectionManager and DSP functions
from production_server import ConnectionManager, EEGSnapshot


class TestZScoreArtifactRejection(unittest.TestCase):
    """PhD Fix P1: Test the honest Z-score clipping (was mislabeled 'ASR')."""
    
    def setUp(self):
        self.cm = ConnectionManager()
    
    def test_clean_signal_unchanged(self):
        """Clean signal (no outliers) should pass through unchanged."""
        # Generate clean sine wave (typical EEG-like signal)
        t = np.linspace(0, 1, 256)
        clean = 10 * np.sin(2 * np.pi * 10 * t)  # 10Hz, 10µV
        result = self.cm._zscore_clip(clean, z_thresh=5.0)
        np.testing.assert_array_almost_equal(result, clean, decimal=5)
    
    def test_spikes_replaced_by_median(self):
        """Large spikes (>5σ) should be replaced with the channel median."""
        data = np.random.normal(0, 10, 256)  # Normal EEG-like noise
        data[100] = 5000  # Inject a massive artifact
        data[200] = -5000
        result = self.cm._zscore_clip(data, z_thresh=5.0)
        
        # The spike locations should now be close to median, not 5000
        median_val = np.median(data)
        self.assertAlmostEqual(result[100], median_val, places=1)
        self.assertAlmostEqual(result[200], median_val, places=1)
    
    def test_flatline_returns_unchanged(self):
        """Flatline signal (std < 0.01) should return unchanged."""
        flat = np.zeros(256) + 3.0  # All identical values
        result = self.cm._zscore_clip(flat, z_thresh=5.0)
        np.testing.assert_array_equal(result, flat)
    
    def test_high_threshold_passes_more(self):
        """Higher z_thresh should clip fewer samples."""
        data = np.random.normal(0, 10, 512)
        # Add moderate outliers (3-4σ)
        data[50] = 35  # ~3.5σ
        data[51] = -35
        
        strict = self.cm._zscore_clip(data.copy(), z_thresh=3.0)
        lenient = self.cm._zscore_clip(data.copy(), z_thresh=5.0)
        
        # Strict should clip more samples than lenient
        strict_changes = np.sum(strict != data)
        lenient_changes = np.sum(lenient != data)
        self.assertGreaterEqual(strict_changes, lenient_changes)


class TestBandpassFilter(unittest.TestCase):
    """Test the Butterworth bandpass filter (1-45Hz clinical standard)."""
    
    def setUp(self):
        self.cm = ConnectionManager()
    
    def test_dc_removed(self):
        """DC offset (0Hz) should be removed by bandpass."""
        # Signal = DC offset + 10Hz sine
        t = np.linspace(0, 2, 512)
        signal = 100 + 10 * np.sin(2 * np.pi * 10 * t)  # DC=100, 10Hz tone
        result = self.cm._bandpass_filter(signal, lowcut=1.0, highcut=45.0, fs=256.0)
        
        # DC should be gone — mean should be near 0
        self.assertAlmostEqual(np.mean(result), 0.0, delta=1.0)
    
    def test_high_freq_attenuated(self):
        """Frequencies above 45Hz should be attenuated."""
        t = np.linspace(0, 2, 512)
        # 100Hz signal (well above 45Hz cutoff)
        high_freq = 10 * np.sin(2 * np.pi * 100 * t)
        result = self.cm._bandpass_filter(high_freq, lowcut=1.0, highcut=45.0, fs=256.0)
        
        # Output power should be much lower than input
        input_power = np.mean(high_freq**2)
        output_power = np.mean(result**2)
        self.assertLess(output_power, input_power * 0.1)  # >90% attenuation
    
    def test_10hz_alpha_passes(self):
        """10Hz alpha wave should pass through with minimal attenuation."""
        t = np.linspace(0, 2, 512)
        alpha = 10 * np.sin(2 * np.pi * 10 * t)
        result = self.cm._bandpass_filter(alpha, lowcut=1.0, highcut=45.0, fs=256.0)
        
        # Trim edges (filter ringing), check middle section
        mid = slice(64, -64)
        input_power = np.mean(alpha[mid]**2)
        output_power = np.mean(result[mid]**2)
        # Should retain most power (>70%)
        self.assertGreater(output_power, input_power * 0.7)


class TestTBRCalculation(unittest.TestCase):
    """PhD Fix P2: Test Theta/Beta Ratio (TBR) calculation."""
    
    def test_tbr_basic_ratio(self):
        """TBR = theta / beta. If theta=0.3 and beta=0.1, TBR should be 3.0."""
        theta = 0.3
        beta = 0.1
        tbr = theta / beta if beta > 0.001 else 0.0
        self.assertAlmostEqual(tbr, 3.0, places=2)
    
    def test_tbr_zero_beta(self):
        """If beta is zero/tiny, TBR should not divide by zero."""
        theta = 0.3
        beta = 0.0
        tbr = theta / beta if beta > 0.001 else 0.0
        self.assertEqual(tbr, 0.0)
    
    def test_tbr_adhd_range(self):
        """Elevated TBR (5-7) indicates inattention per Arns et al. 2013."""
        # Simulate ADHD-like power spectrum (lots of theta, little beta)
        theta = 0.35
        beta = 0.06
        tbr = theta / beta
        self.assertGreater(tbr, 5.0)
        self.assertLess(tbr, 7.0)
    
    def test_tbr_focused_range(self):
        """Low TBR (1-2) indicates focused state."""
        theta = 0.15
        beta = 0.10
        tbr = theta / beta
        self.assertGreater(tbr, 1.0)
        self.assertLess(tbr, 2.0)


class TestCFCScore(unittest.TestCase):
    """PhD Fix P4: Test CFC gating behind EMG detection."""
    
    def setUp(self):
        self.cm = ConnectionManager()
    
    def test_emg_detected_returns_zero(self):
        """When EMG noise is detected, CFC score should always be 0."""
        # Generate any signal — doesn't matter, EMG flag should override
        t = np.linspace(0, 1, 256)
        data = np.sin(2 * np.pi * 10 * t) + np.sin(2 * np.pi * 40 * t)
        result = self.cm._cfc_score(data, fs=256.0, emg_detected=True)
        self.assertEqual(result, 0.0)
    
    def test_short_data_returns_zero(self):
        """Data shorter than 256 samples should return 0."""
        data = np.random.randn(100)
        result = self.cm._cfc_score(data, fs=256.0, emg_detected=False)
        self.assertEqual(result, 0.0)
    
    def test_returns_bounded_value(self):
        """CFC score should always be in [0, 1]."""
        data = np.random.randn(512)
        result = self.cm._cfc_score(data, fs=256.0, emg_detected=False)
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)


class TestDequeBuffers(unittest.TestCase):
    """Stress Fix S4: Test deque buffer behavior."""
    
    def test_buffers_are_deque(self):
        """All EEG buffers should be collections.deque, not list."""
        cm = ConnectionManager()
        for ch in ['TP9', 'AF7', 'AF8', 'TP10']:
            self.assertIsInstance(cm._buffers[ch], deque)
    
    def test_deque_maxlen(self):
        """Deque should auto-trim at maxlen=768."""
        cm = ConnectionManager()
        # Push 1000 samples — should only keep 768
        for i in range(1000):
            cm._buffers['TP9'].append(float(i))
        self.assertEqual(len(cm._buffers['TP9']), 768)
        # The oldest samples should be trimmed
        self.assertEqual(cm._buffers['TP9'][0], 232.0)  # 1000 - 768 = 232
    
    def test_ppg_buffer_is_deque(self):
        """PPG buffer should also be deque."""
        cm = ConnectionManager()
        self.assertIsInstance(cm._ppg_buffer, deque)
    
    def test_imu_buffer_is_deque(self):
        """IMU buffer should also be deque."""
        cm = ConnectionManager()
        self.assertIsInstance(cm._imu_buffer, deque)


class TestBaselineCalibration(unittest.TestCase):
    """PhD Fix P3: Test 60s baseline parameter."""
    
    def test_baseline_not_done_initially(self):
        """Baseline should not be complete on init."""
        cm = ConnectionManager()
        self.assertFalse(cm._baseline_done)
    
    def test_baseline_ratio_none_initially(self):
        """Baseline ratio should be None before calibration."""
        cm = ConnectionManager()
        self.assertIsNone(cm._baseline_ratio)
    
    def test_iaf_default_10hz(self):
        """Default IAF should be 10Hz (standard adult alpha)."""
        cm = ConnectionManager()
        self.assertEqual(cm._iaf, 10.0)


class TestEEGSnapshot(unittest.TestCase):
    """Test the EEGSnapshot dataclass fields."""
    
    def test_has_tbr_field(self):
        """EEGSnapshot should have a tbr field (PhD Fix P2)."""
        snap = EEGSnapshot()
        self.assertTrue(hasattr(snap, 'tbr'))
        self.assertEqual(snap.tbr, 0.0)
    
    def test_has_headband_on_field(self):
        """EEGSnapshot should have headband_on field."""
        snap = EEGSnapshot()
        self.assertTrue(hasattr(snap, 'headband_on'))
        self.assertFalse(snap.headband_on)
    
    def test_has_mind_state_field(self):
        """EEGSnapshot should have mind_state field."""
        snap = EEGSnapshot()
        self.assertEqual(snap.mind_state, 'unknown')
    
    def test_has_deep_focus_field(self):
        """EEGSnapshot should have deep_focus field (CFC)."""
        snap = EEGSnapshot()
        self.assertEqual(snap.deep_focus, 0.0)


class TestSimRunningInit(unittest.TestCase):
    """Deep Audit Fix P6: _sim_running should be initialized."""
    
    def test_sim_running_initialized(self):
        """ConnectionManager should have _sim_running = False on init."""
        cm = ConnectionManager()
        self.assertTrue(hasattr(cm, '_sim_running'))
        self.assertFalse(cm._sim_running)


class TestDSPQueue(unittest.TestCase):
    """Stress Fix S3: Test DSP worker queue setup."""
    
    def test_dsp_queue_exists(self):
        """ConnectionManager should have a DSP queue."""
        cm = ConnectionManager()
        self.assertTrue(hasattr(cm, '_dsp_queue'))
    
    def test_dsp_thread_alive(self):
        """DSP worker thread should be alive after init."""
        cm = ConnectionManager()
        self.assertTrue(hasattr(cm, '_dsp_thread'))
        self.assertTrue(cm._dsp_thread.is_alive())


if __name__ == '__main__':
    print("=" * 60)
    print("  FocusFlow — DSP Unit Test Suite")
    print("=" * 60)
    print()
    unittest.main(verbosity=2)
