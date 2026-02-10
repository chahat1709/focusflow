
import threading
import time
import datetime
import numpy as np
from pylsl import StreamInlet, resolve_byprop
from src.backend.config import state, buffers, indices, calib, rec, BUFF_SIZE, state_lock
from src.backend.core.processor import processor

class BeastStreamer(threading.Thread):
    def __init__(self):
        super().__init__()
        self.running = True
        self.inlets = {} # Dictionary of Multi-Sensor Inlets
        self.connected = False
        self.silence_counter = 0  # Watchdog counter
        self.last_scan_time = 0
        print("🦍 BEAST STREAMER: Initialized (Multi-Sensor Mode).")

    def run(self):
        self.log("🦍 BEAST STREAMER: Thread Started.")
        
        while self.running:
            # ---------------------------------------------------------
            # PHASE 1: MULTI-SENSOR DISCOVERY (Anchor & Expand)
            # ---------------------------------------------------------
            if not self.inlets.get('EEG'):
                try:
                    # 1. Anchor: Find the EEG stream first (The Master Clock)
                    print("🔎 BEAST: Scanning for EEG Stream...", flush=True)
                    streams = resolve_byprop('type', 'EEG', timeout=2.0)
                    
                    if streams:
                        # Find the NEWEST session
                        last_stream = streams[-1]
                        target_session_id = last_stream.source_id()
                        print(f"🎯 BEAST: TARGET LOCKED -> Session: {target_session_id} ({len(streams)} candidates)", flush=True)
                        
                        # 2. Expand: Find all sensors for this Session
                        # We use the session ID to find siblings (PPG, ACC, GYRO)
                        sibling_streams = resolve_byprop('source_id', target_session_id, timeout=1.0)
                        
                        for s in sibling_streams:
                             s_type = s.type()
                             if s_type not in self.inlets:
                                 self.inlets[s_type] = StreamInlet(s, max_buflen=360)
                                 self.log(f"   + Linked {s_type} Stream (Anchor Strategy)")

                        if 'EEG' in self.inlets:
                            self.connected = True
                            self.silence_counter = 0 
                            with state_lock: state['connected'] = True
                            self.log("✅ BEAST: MAIN PIPELINE CONNECTED.")
                    else:
                        print("... No EEG streams found yet. Retrying.", flush=True)
                        time.sleep(0.5) 
                        
                except Exception as e:
                    self.log(f"❌ Discovery Error: {e}")
                    time.sleep(1)
            
            # ---------------------------------------------------------
            # PHASE 2: PARALLEL INGESTION & INCREMENTAL DISCOVERY
            # ---------------------------------------------------------
            else:
                # INCREMENTAL DISCOVERY (Fix for Race Condition)
                # If we have EEG but missing others, try to find them
                required = ['PPG', 'ACC', 'GYRO']
                missing = [t for t in required if t not in self.inlets]
                
                # Check every 3 seconds, NOT every frame
                import time # Ensure we have time module
                if missing and (time.time() - self.last_scan_time > 3.0):
                    self.last_scan_time = time.time()
                    try:
                         # BRUTE FORCE STRATEGY: Find missing types individually
                         # This bypasses any 'source_id' filtering issues
                         if 'PPG' not in self.inlets:
                             s = resolve_byprop('type', 'PPG', timeout=0.5)
                             if s: 
                                 self.inlets['PPG'] = StreamInlet(s[-1], max_buflen=360)
                                 self.log("   + BRUTE LINK: PPG Stream Connected")

                         if 'ACC' not in self.inlets:
                             s = resolve_byprop('type', 'ACC', timeout=0.5)
                             if s: 
                                 self.inlets['ACC'] = StreamInlet(s[-1], max_buflen=360)
                                 self.log("   + BRUTE LINK: ACC Stream Connected")
                                 
                         if 'GYRO' not in self.inlets:
                             s = resolve_byprop('type', 'GYRO', timeout=0.5)
                             if s: 
                                 self.inlets['GYRO'] = StreamInlet(s[-1], max_buflen=360)
                                 self.log("   + BRUTE LINK: GYRO Stream Connected")
                                 
                    except Exception as e:
                        print(f"Brute Scan Error: {e}")

                try:
                    active_data = False
                    
                    # 1. EEG (Master Clock)
                    if 'EEG' in self.inlets:
                        sample, ts = self.inlets['EEG'].pull_sample(timeout=0.0)
                        if sample:
                            active_data = True
                            # Slice 4 channels
                            processor.process_sample(np.array(sample[:4]), timestamp=ts)

                    # 2. PPG (Heart)
                    if 'PPG' in self.inlets:
                        sample, ts = self.inlets['PPG'].pull_sample(timeout=0.0)
                        if sample: 
                            if sample[1] != 0: print(f"RX_PPG: {sample}", flush=True)
                            processor.process_ppg(np.array(sample))

                    # 3. ACC (Motion)
                    if 'ACC' in self.inlets:
                        sample, ts = self.inlets['ACC'].pull_sample(timeout=0.0)
                        if sample: processor.process_imu(np.array(sample), 'acc')

                    # 4. GYRO (Rotation)
                    if 'GYRO' in self.inlets:
                        sample, ts = self.inlets['GYRO'].pull_sample(timeout=0.0)
                        if sample: processor.process_imu(np.array(sample), 'gyro')


                    # WATCHDOG LOGIC
                    if active_data:
                        self.silence_counter = 0
                        with state_lock: state['connected'] = True
                    else:
                        self.silence_counter += 1
                        time.sleep(0.01) # Prevent CPU burn
                        
                        # If silent for ~2.5 seconds (250 loops * 0.01s)
                        if self.silence_counter > 250:
                            self.log("⚠️ GHOST STREAM DETECTED! (Silence > 2s). Resetting...")
                            self.inlets = {} # Destroy all objects
                            self.connected = False
                            with state_lock: state['connected'] = False
                        
                except Exception as e:
                    self.log(f"❌ Pull Error: {e}")
                    self.inlets = {}
                    self.connected = False

    def log(self, msg):
        print(msg)

    def stop(self):
        self.running = False
