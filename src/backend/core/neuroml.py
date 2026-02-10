
import numpy as np

class NeuroML:
    def __init__(self):
        self.profile_file = 'user_profile.json'
        self.means = {'Alpha': 0.8, 'Beta': 0.6, 'Theta': 0.7, 'Delta': 0.5, 'Gamma': 0.4}
        self.stds = {'Alpha': 0.4, 'Beta': 0.3, 'Theta': 0.3, 'Delta': 0.3, 'Gamma': 0.2}
        self.history = []
        self.calibrated = False
        self.load_profile()

    def load_profile(self):
        import json
        import os
        if os.path.exists(self.profile_file):
            try:
                with open(self.profile_file, 'r') as f:
                    data = json.load(f)
                    self.means = data.get('means', self.means)
                    self.stds = data.get('stds', self.stds)
                    self.calibrated = data.get('calibrated', False)
                    print(f"🧠 LOADED PROFILE: {self.means}")
            except Exception as e: print(f"⚠️ Profile Load Error: {e}")

    def save_profile(self):
        import json
        try:
            with open(self.profile_file, 'w') as f:
                json.dump({
                    'means': self.means,
                    'stds': self.stds,
                    'calibrated': self.calibrated
                }, f)
            print("💾 PROFILE SAVED")
        except Exception as e: print(f"⚠️ Profile Save Error: {e}")

    def set_baseline(self, calibration_buffer):
        """Calculates personalized Mean and StdDev from 30s calibration data."""
        if not calibration_buffer: return
        
        # Calculate stats for each band
        bands = ['Alpha', 'Beta', 'Theta', 'Delta', 'Gamma']
        for band in bands:
            # Handle new buffer format (dict with 'bands' key) or old format (direct dict)
            values = []
            for sample in calibration_buffer:
                if 'bands' in sample:
                    values.append(sample['bands'].get(band, 0.1))
                else:
                    values.append(sample.get(band, 0.1))
            
            self.means[band] = np.mean(values)
            self.stds[band] = np.std(values) + 0.001 # Prevent div/0
            
        self.calibrated = True
        self.save_profile()
        print(f"🧠 BASELINE SET: {self.means}")

    def get_z_scores(self, bands):
        """Converts raw power to Z-Scores (Standard Deviations from Mean)."""
        z_scores = {}
        for band, val in bands.items():
            if band in self.means:
                # Z = (Current - Mean) / StdDev
                z = (val - self.means[band]) / self.stds[band]
                z_scores[band] = np.clip(z, -3.0, 3.0) # Clamp to +/- 3 Sigma
        return z_scores

    def extract_features(self, bands):
        """Calculates adaptive biomarkers using Z-Scores."""
        # 1. Normalize
        z = self.get_z_scores(bands)
        
        # 2. Adaptive Ratios (Difference of Z-Scores = Log Ratio)
        # Z_Beta - Z_Theta is equivalent to log(Beta/Theta) normalized
        focus_index = z.get('Beta', 0) - z.get('Theta', 0)
        relax_index = z.get('Alpha', 0) - z.get('Theta', 0)
        stress_index = z.get('Beta', 0) - z.get('Alpha', 0)
        
        # FATIGUE: (Theta + Alpha) / Beta
        # In Z-Space: (Z_Theta + Z_Alpha) - Z_Beta
        fatigue_index = (z.get('Theta', 0) + z.get('Alpha', 0)) - z.get('Beta', 0)

        return {
            'focus_ratio': focus_index, # > 0 means "More Focused than Normal"
            'relax_ratio': relax_index,
            'stress_ratio': stress_index,
            'fatigue_ratio': fatigue_index,
            'raw': bands,
            'z_scores': z
        }

    def predict_state(self, features):
        """Classifies mental state based on relative deviations."""
        f = features['focus_ratio']
        s = features['stress_ratio']
        r = features['relax_ratio']
        
        # Thresholds are now in StdDev units (e.g., +1 Sigma)
        if f > 1.0: return "FLOW_STATE"      # 1 Sigma above normal focus
        elif s > 1.5: return "HIGH_STRESS"   # 1.5 Sigma above normal stress
        elif r > 1.0: return "DEEP_RELAXATION" # 1 Sigma above normal relaxation
        elif f < -1.5: return "DISTRACTED"   # 1.5 Sigma below normal focus
        else: return "BALANCED"

    def push(self, bands):
        """Add new band power data to history buffer"""
        self.history.append(bands)
        if len(self.history) > 10: 
            self.history.pop(0)

    def predict(self):
        """Predict state based on buffered history"""
        if not self.history: return None
        
        # Average recent bands for stability
        avg_bands = {}
        keys = self.history[0].keys()
        for k in keys:
            avg_bands[k] = np.mean([h.get(k, 0) for h in self.history])
            
        features = self.extract_features(avg_bands)
        state_label = self.predict_state(features)
        
        return {
            'state': state_label,
            'features': features,
            # Normalize display scores to 0-1 range for UI (Sigmoidish)
            'load': 1 / (1 + np.exp(-features['stress_ratio'])), 
            'flow': 1 / (1 + np.exp(-features['focus_ratio'])),
            'fatigue': 1 / (1 + np.exp(-features['fatigue_ratio']))
        }

# Singleton Instance
ml_pipeline = NeuroML()
