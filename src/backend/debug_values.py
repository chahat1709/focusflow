import requests
import time

API_URL = "http://localhost:5001/api/status"

print("--- DATA LIVENESS TEST ---")
prev_alpha = -1

for i in range(10):
    try:
        res = requests.get(API_URL, timeout=1).json()
        alpha = res.get('bands', {}).get('alpha', 0)
        
        diff = alpha - prev_alpha
        status = "CHANGED (ALIVE)" if diff != 0 and prev_alpha != -1 else "STATIC (FROZEN)"
        
        print(f"[{i}] Alpha: {alpha:.4f} | {status}")
        
        prev_alpha = alpha
    except Exception as e:
        print(f"[{i}] FAIL: {e}")
        
    time.sleep(1.0)
