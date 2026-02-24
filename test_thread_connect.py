"""Full test: scan + connect + subscribe from a THREAD (simulating production_server.py).
This is the exact flow the server uses.
"""
import threading
import asyncio
import time
from muse_ble import MuseBLEClient

notification_count = 0

def on_eeg(ch_idx, samples):
    global notification_count
    notification_count += len(samples)

def connect_in_thread():
    """This mimics what the server does."""
    print("[THREAD] Starting full BLE connection from background thread...")
    
    async def do_connect():
        client = MuseBLEClient(on_eeg_sample=on_eeg)
        success = await client.auto_connect(max_retries=4, scan_timeout=8.0)
        if success:
            print(f"[OK] Connected to {client.device_name} ({client.device_address})")
            print("[OK] Waiting 10s for data...")
            await asyncio.sleep(10)
            print(f"[OK] Received {notification_count} data points!")
            await client.disconnect()
        else:
            print("[FAIL] Could not connect!")
        return success
    
    result = asyncio.run(do_connect())
    print(f"[THREAD] Done. Success={result}")

print("Starting full threaded connect test...")
t = threading.Thread(target=connect_in_thread, daemon=True)
t.start()
t.join(timeout=60)
print(f"Test complete. Total notifications: {notification_count}")
