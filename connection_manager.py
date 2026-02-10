import subprocess
import threading
import time
import re
import sys
import shutil
import json
import os
from pylsl import resolve_byprop

CACHE_FILE = "muse_device_cache.json"

class MuseAutopilot:
    def __init__(self):
        self.process = None
        self.status = "disconnected"  # disconnected, scanning, connecting, streaming, error
        self.last_error = ""
        self.mac_address = self._load_cache()
        self.device_name = "Muse Device"
        self.battery_level = 0
        self.stop_event = threading.Event()
        self.monitor_thread = None
        
        # Check if muselsl is installed
        if not shutil.which("muselsl") and not shutil.which("muse-lsl"):
            self.status = "error"
            self.last_error = "muselsl not found. pip install muselsl"

    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    data = json.load(f)
                    print(f"[Autopilot] Loaded cached MAC: {data.get('mac_address')}")
                    return data.get('mac_address')
            except: pass
        return None

    def _save_cache(self, mac):
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump({'mac_address': mac}, f)
        except: pass

    def scan_for_muse(self):
        """Scans for available Muse devices using native BleakScanner (NO CLI)"""
        self.status = "scanning"
        self.last_error = ""
        print("[Autopilot] Scanning for Muse devices (Native Bleak)...")
        
        try:
            import asyncio
            from bleak import BleakScanner

            async def run_scan():
                devices = await BleakScanner.discover(timeout=15.0)
                for d in devices:
                    name = d.name or "Unknown"
                    if "Muse" in name:
                        return d.name, d.address
                return None, None

            # Run in new event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            name, mac = loop.run_until_complete(run_scan())
            
            if name and mac:
                self.device_name = name
                self.mac_address = mac
                self._save_cache(self.mac_address)
                print(f"[Autopilot] Found {self.device_name}: {self.mac_address}")
                return self.mac_address
            else:
                self.last_error = "No Muse found via Native Scan."
                print(f"[Autopilot] Scan failed: {self.last_error}")
                self.status = "disconnected"
                return None

        except Exception as e:
            self.last_error = f"Scan error: {str(e)}"
            self.status = "error"
            print(f"[Autopilot] {self.last_error}")
            return None

    async def _read_battery_async(self, address):
        from bleak import BleakClient
        BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"
        try:
            async with BleakClient(address) as client:
                val = await client.read_gatt_char(BATTERY_UUID)
                return int(val[0])
        except Exception as e:
            print(f"[Autopilot] Battery read failed: {e}")
            return -1

    def start_stream(self, mac_address=None):
        """Starts the muselsl stream process"""
        if self.process:
            self.stop()
            
        # 1. OPTIMIZATION: Try Cached MAC first (Instant Connect)
        target_mac = mac_address or self.mac_address
        
        if not target_mac:
            # No cache? Then we must scan.
            target_mac = self.scan_for_muse()
            if not target_mac:
                return False
        
        # 2. BATTERY CHECK (Pre-Flight)
        print(f"[Autopilot] Checking Battery for {target_mac}...")
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            batt = loop.run_until_complete(self._read_battery_async(target_mac))
            loop.close()
            if batt > 0:
                self.battery_level = batt
                print(f"[Autopilot] 🔋 Battery Level: {batt}%")
            else:
                print("[Autopilot] 🔋 Battery Status Unknown")
        except Exception as e:
            print(f"[Autopilot] Battery check skipped: {e}")

        self.status = "connecting"
        print(f"[Autopilot] Connecting to {target_mac}...")
        
        try:
            # Start background process
            # muselsl stream --address MAC --ppg --acc --gyro
            # muselsl stream --address MAC --ppg --acc --gyro --backend bleak
            cmd = ['muselsl', 'stream', '--address', target_mac, '--ppg', '--acc', '--gyro', '--backend', 'bleak']
            # Pipe output to log file
            self.log_file = open('muselsl.log', 'w')
            
            # Windows: Don't hide completely, or capture to file
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            self.process = subprocess.Popen(
                cmd,
                stdout=self.log_file,
                stderr=subprocess.STDOUT,
                startupinfo=startupinfo
            )
            
            # Start monitoring thread
            self.stop_event.clear()
            self.monitor_thread = threading.Thread(target=self._monitor_stream, daemon=True)
            self.monitor_thread.start()
            
            return True
            
        except Exception as e:
            self.last_error = f"Connection error: {str(e)}"
            self.status = "error"
            return False

    def _monitor_stream(self):
        """Watchdog to ensure stream is alive"""
        start_time = time.time()
        
        while not self.stop_event.is_set():
            # 1. Check if process is alive
            if self.process.poll() is not None:
                # Process died
                error_msg = "Unknown error"
                try:
                    with open('muselsl.log', 'r') as f:
                        lines = f.readlines()
                        if lines: error_msg = lines[-1].strip()
                except: pass
                
                self.last_error = f"Process died: {error_msg}"
                
                # CRITICAL FIX: If we used cache and failed, DELETE CACHE and Retry effectively
                # We can't auto-retry easily in this thread, but we MUST clear the bad cache
                # so the next user click works.
                if self.status == "connecting":
                    print("[Autopilot] Connection failed. Clearing cache...")
                    self.mac_address = None
                    if os.path.exists(CACHE_FILE):
                        try: os.remove(CACHE_FILE)
                        except: pass
                    self.last_error = "Connection failed. Please retry (Scanning...)"
                
                self.status = "error"
                print(f"[Autopilot] Stream died: {self.last_error}")
                break
            
            # 2. Check for LSL stream availability (every 2s)
            # Give it more time (10s) to establish LSL before declaring success
            if time.time() - start_time > 3: 
                streams = resolve_byprop('type', 'EEG', timeout=0.1)
                if streams:
                    self.status = "streaming"
                    # If we are successfully streaming, confirm the MAC is good (already saved)
                else:
                    # Still connecting...
                    pass
            
            time.sleep(2)

    def stop(self):
        """Stop the stream"""
        self.stop_event.set()
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
        self.status = "disconnected"
