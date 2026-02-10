import requests
import time
import sys

API_URL = "http://localhost:5001/api/status"

def debug_metrics():
    print("=== METRIC DEBUGGER ===")
    print("Polling API for [Focus, BPM, Blinks]...")
    
    for i in range(10):
        try:
            res = requests.get(API_URL).json()
            
            connected = res.get('connected')
            focus = res.get('focus')
            bpm = res.get('bpm')
            blinks = res.get('blinks')
            bands = res.get('bands')
            
            # Formatting
            band_str = "YES" if bands else "NO"
            
            print(f"[{i}] CONN:{connected} | BANDS:{band_str} | FOCUS:{focus:.2f} | BPM:{bpm} | BLINKS:{blinks}")
            
            if bpm > 0 or blinks > 0:
                print(">>> SUCCESS: Metrics are changing! Backend is OK.")
            
        except Exception as e:
            print(f"[{i}] FAIL: {e}")
        
        time.sleep(1.0)

if __name__ == "__main__":
    debug_metrics()
