"""
Comprehensive Data Quality Report Generator
Captures and analyzes data at every stage of the pipeline
"""
import numpy as np
from pylsl import StreamInlet, resolve_byprop
import requests
import time
import json

def main():
    report = []
    report.append("=" * 70)
    report.append("MUSE DATA QUALITY REPORT")
    report.append("Timestamp: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    report.append("=" * 70)
    
    # TEST 1: Raw LSL Streams
    report.append("\n[1] RAW LSL STREAM ANALYSIS")
    report.append("-" * 70)
    
    try:
        streams = resolve_byprop('type', 'EEG', timeout=3)
        if not streams:
            report.append("CRITICAL: No EEG stream detected!")
            print("\n".join(report))
            return
        
        inlet = StreamInlet(streams[0])
        info = streams[0]
        
        report.append(f"Device Name: {info.name()}")
        report.append(f"Sample Rate: {info.nominal_srate()} Hz")
        report.append(f"Channel Count: {info.channel_count()}")
        report.append(f"Data Type: {info.channel_format()}")
        
        # Collect 20 samples for statistical analysis
        report.append("\nCollecting 20 samples...")
        samples = []
        timestamps = []
        
        for i in range(20):
            sample, ts = inlet.pull_sample(timeout=0.5)
            if sample and ts:
                samples.append(sample[:4])  # First 4 EEG channels
                timestamps.append(ts)
        
        if len(samples) < 10:
            report.append(f"WARNING: Only got {len(samples)}/20 samples - data loss!")
        else:
            report.append(f"Captured: {len(samples)} samples")
            
            # Statistical Analysis
            arr = np.array(samples)
            report.append("\nStatistical Analysis (microvolts):")
            report.append("Channel    Mean      Std Dev   Min       Max       Variance")
            report.append("-" * 70)
            
            for ch in range(4):
                data = arr[:, ch]
                report.append(f"Ch{ch+1}     {np.mean(data):>8.2f}  {np.std(data):>8.2f}  "
                             f"{np.min(data):>8.2f}  {np.max(data):>8.2f}  {np.var(data):>10.2f}")
            
            # Check for suspicious patterns
            report.append("\nQuality Checks:")
            for ch in range(4):
                data = arr[:, ch]
                variance = np.var(data)
                
                if variance < 0.1:
                    report.append(f"  Ch{ch+1}: FLAT SIGNAL (variance={variance:.4f}) - FAKE DATA?")
                elif variance > 10000:
                    report.append(f"  Ch{ch+1}: EXCESSIVE NOISE (variance={variance:.1f}) - Bad contact?")
                else:
                    report.append(f"  Ch{ch+1}: NORMAL (variance={variance:.1f})")
            
            # Timestamp precision
            if len(timestamps) >= 2:
                intervals = np.diff(timestamps) * 1000  # ms
                report.append("\nTimestamp Precision:")
                report.append(f"  Expected interval: 3.91 ms (256 Hz)")
                report.append(f"  Measured average: {np.mean(intervals):.2f} ms")
                report.append(f"  Jitter (std dev): {np.std(intervals):.2f} ms")
                report.append(f"  Min interval: {np.min(intervals):.2f} ms")
                report.append(f"  Max interval: {np.max(intervals):.2f} ms")
                
                if np.std(intervals) > 1.0:
                    report.append(f"  WARNING: High jitter - unstable connection")
                else:
                    report.append(f"  GOOD: Low jitter - stable hardware clock")
    
    except Exception as e:
        report.append(f"ERROR in LSL analysis: {e}")
    
    # TEST 2: Backend API
    report.append("\n[2] BACKEND API ANALYSIS")
    report.append("-" * 70)
    
    try:
        r = requests.get('http://localhost:5001/api/raw_data', timeout=2)
        data = r.json()
        
        report.append(f"Connection Status: {data['connected']}")
        report.append(f"Focus Score: {data['focus_score']:.6f}")
        report.append(f"Heart Rate: {data['heart_rate']} BPM")
        
        report.append("\nEEG Channels (current):")
        for i, val in enumerate(data['eeg']):
            report.append(f"  Ch{i+1}: {val:>10.2f} uV")
        
        report.append("\nBand Powers:")
        for band, power in data['bands'].items():
            report.append(f"  {band.capitalize():8s}: {power:.6f}")
        
        # Check if focus score is static
        scores = []
        for _ in range(5):
            time.sleep(0.2)
            r = requests.get('http://localhost:5001/api/raw_data', timeout=1)
            scores.append(r.json()['focus_score'])
        
        score_variance = np.var(scores)
        report.append(f"\nFocus Score Variance (5 samples): {score_variance:.8f}")
        if score_variance < 0.0001:
            report.append("  WARNING: Focus score is STATIC - possible fake data")
        else:
            report.append("  GOOD: Focus score is changing")
            
    except Exception as e:
        report.append(f"ERROR in API analysis: {e}")
    
    # FINAL VERDICT
    report.append("\n" + "=" * 70)
    report.append("FINAL ASSESSMENT")
    report.append("=" * 70)
    
    # Determine if data is real
    if len(samples) >= 10:
        total_variance = np.mean([np.var(arr[:, ch]) for ch in range(4)])
        
        if total_variance < 1:
            report.append("VERDICT: DATA APPEARS FAKE OR SIMULATED")
            report.append("Reason: Signal variance is too low (flat line)")
        elif total_variance > 50000:
            report.append("VERDICT: POOR SIGNAL QUALITY")
            report.append("Reason: Excessive noise (check electrode contact)")
        else:
            report.append("VERDICT: DATA APPEARS GENUINE")
            report.append(f"Reason: Signal variance is within normal range ({total_variance:.1f})")
    
    report_text = "\n".join(report)
    
    # Save to file
    with open('DATA_QUALITY_REPORT.txt', 'w') as f:
        f.write(report_text)
    
    print(report_text)
    print(f"\nReport saved to: DATA_QUALITY_REPORT.txt")

if __name__ == "__main__":
    main()
