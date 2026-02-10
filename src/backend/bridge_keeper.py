import subprocess
import time
import sys
import datetime
import os
import requests

# Configuration
MUSE_ADDRESS = "00:55:DA:B8:15:5E"
CMD_STR = f"muselsl stream --address {MUSE_ADDRESS} --ppg --acc --gyro --backend bleak"

def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] 🌉 BRIDGE KEEPER: {msg}")

def main():
    log(f"Guardian Active. Target: {MUSE_ADDRESS}")
    log("Disconnecting any existing streams first...")
    try:
        subprocess.run("taskkill /F /IM muselsl.exe /T", shell=True, capture_output=True)
    except: pass
    
    crash_count = 0
    zombie_timer = 0
    
    while True:
        try:
            log("🚀 Launching Muse Stream...")
            start_time = time.time()
            
            # NON-BLOCKING LAUNCH
            process = subprocess.Popen(CMD_STR, shell=True)
            
            while process.poll() is None:
                # 1. Check for Zombie State (Every 2s)
                try:
                    r = requests.get('http://localhost:5001/api/status', timeout=1)
                    data = r.json()
                    
                    if data.get('connected'):
                        # Check for flatline
                        alpha = data.get('bands', {}).get('alpha', 0)
                        if alpha == 0.0:
                            zombie_timer += 2
                            if zombie_timer % 10 == 0:
                                log(f"⚠️ Zombie Stream Detected ({zombie_timer}s flatline)...")
                        else:
                            zombie_timer = 0 # Reset if signal is good
                            
                    # KILL IF ZOMBIE MODE > 20s
                    if zombie_timer > 6000: # DISABLED FOR DEBUGGING (Was 20)
                        log("💀 ZOMBIE CONFIRMED. KILLING DRIVER!")
                        subprocess.run("taskkill /F /IM muselsl.exe /T", shell=True, capture_output=True)
                        process.terminate()
                        break 
                        
                except Exception as e:
                    # Ignore connection errors if server is down
                    pass
                
                time.sleep(2)
            
            # --- PROCESS EXITED ---
            duration = time.time() - start_time
            exit_code = process.poll()
            
            log(f"⚠️ Stream exited (Code: {exit_code}) after {duration:.1f}s")
            
            # Anti-Spam protection
            if duration < 5:
                crash_count += 1
                log(f"warning: Rapid crash detected ({crash_count}/5)")
                if crash_count >= 5:
                    log("🚨 Too many rapid crashes. Waiting 10s to cool down...")
                    time.sleep(10)
                    crash_count = 0
            else:
                crash_count = 0 # Reset if it ran for a while
                zombie_timer = 0
            
            log("♻️ Restarting stream in 2 seconds...")
            time.sleep(2)
            
        except KeyboardInterrupt:
            log("🛑 Stopping BridgeKeeper.")
            try:
                subprocess.run("taskkill /F /IM muselsl.exe /T", shell=True, capture_output=True)
            except: pass
            break
        except Exception as e:
            log(f"❌ CRITICAL BRIDGE ERROR: {e}")
            time.sleep(5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
