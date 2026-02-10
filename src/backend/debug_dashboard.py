import requests
import time
import sys

API_URL = "http://127.0.0.1:5001/api/status"
CONNECT_URL = "http://127.0.0.1:5001/api/connect"

def debug_dashboard():
    print("=== HEADLESS DASHBOARD DEBUGGER ===")
    
    # 1. Trigger Connect
    print("[Action] Clicking 'Connect' Button (via API)...")
    try:
        requests.get(CONNECT_URL)
        print("[Success] Connection Initiated.")
    except:
        print("[Error] Server down?")
        return

    # 2. Poll Data
    print("[Action] Polling /api/status for 30 seconds...")
    for i in range(30):
        try:
            res = requests.get(API_URL).json()
            
            # Extract Critical Metrics
            connected = res.get('connected')
            signal = res.get('signal_ok')
            bpm = res.get('bpm')
            focus = res.get('focus')
            device = res.get('device_name')
            raw_eeg = res.get('bands', {}).get('alpha')
            
            status_icon = "🟢" if connected else "🔴"
            data_icon = "🌊" if raw_eeg else "❌"
            
            print(f"[{i}s] {status_icon} Conn: {connected} | {data_icon} EEG: {raw_eeg} | ❤️ BPM: {bpm} | 🧠 Focus: {focus} | 📱 {device}")
            
            if connected and raw_eeg:
                print("\n>>> CONCLUSION: BACKEND IS ALIVE AND STREAMING DATA! <<<")
                print("The issue is NOT the Python code. It is the Browser/JS.")
                break
                
        except Exception as e:
            print(f"[{i}s] Request Failed: {e}")
        
        time.sleep(1)

if __name__ == "__main__":
    debug_dashboard()
