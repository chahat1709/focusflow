"""Test: Does BLE scan work from a background thread?
Simulates exactly what production_server.py does.
"""
import threading
import asyncio
from bleak import BleakScanner

def scan_in_thread():
    """This is what the server does: asyncio.run() in a daemon thread."""
    print("[THREAD] Starting BLE scan from background thread...")
    
    async def do_scan():
        print("[ASYNC] Running BleakScanner.discover (10s timeout)...")
        devices = await BleakScanner.discover(timeout=10.0)
        print(f"[ASYNC] Found {len(devices)} devices:")
        muse_found = False
        for d in devices:
            name = d.name or '(no name)'
            print(f"  {name} -> {d.address}")
            if 'muse' in name.lower():
                muse_found = True
                print(f"  *** MUSE MATCH! ***")
        if not muse_found:
            print("[ASYNC] NO MUSE FOUND by name!")
        return devices
    
    devices = asyncio.run(do_scan())
    print(f"[THREAD] Done. {len(devices)} devices total.")

print("Starting threaded scan test...")
t = threading.Thread(target=scan_in_thread, daemon=True)
t.start()
t.join(timeout=30)
print("Test complete.")
