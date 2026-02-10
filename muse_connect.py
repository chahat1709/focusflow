import asyncio
import time
import uuid
import struct
import numpy as np
from bleak import BleakScanner, BleakClient
from pylsl import StreamInfo, StreamOutlet

# --- CONFIGURATION ---
MUSE_NAME_FILTER = "Muse" 

# UUIDs
EEG_CHARS = [
    "273e0003-4c4d-454d-96be-f03bac821358",  # TP9
    "273e0004-4c4d-454d-96be-f03bac821358",  # AF7
    "273e0005-4c4d-454d-96be-f03bac821358",  # AF8
    "273e0006-4c4d-454d-96be-f03bac821358",  # TP10
]
PPG_CHARS = [
    "273e000f-4c4d-454d-96be-f03bac821358",  # Ambient
    "273e0010-4c4d-454d-96be-f03bac821358",  # IR
    "273e0011-4c4d-454d-96be-f03bac821358",  # Red
]
ACC_CHAR = "273e000a-4c4d-454d-96be-f03bac821358"
GYRO_CHAR = "273e0009-4c4d-454d-96be-f03bac821358"
CTRL_CHAR = "273e0001-4c4d-454d-96be-f03bac821358"

class MuseStreamer:
    def __init__(self):
        # 1. UNIQUE SESSION ID (The Ghost Buster)
        self.session_id = f"Muse_Session_{uuid.uuid4().hex[:8]}"
        print(f"🆔 GENERATING NEW SESSION ID: {self.session_id}")
        
        # PHASE 6: Connection State Management
        self.connection_state = "idle"  # idle, scanning, connected, error
        self.should_scan = False  # Control flag for manual connection
        self.client = None  # BleakClient instance
        self.connection_lock = threading.Lock()  # v1.1: Thread safety
        
        # 2. CREATE OUTLETS
        # EEG
        self.info_eeg = StreamInfo('Muse', 'EEG', 4, 256, 'float32', self.session_id)
        self.outlet_eeg = StreamOutlet(self.info_eeg)
        time.sleep(0.2) # Flood protection
        
        # PPG (3 Channels: Ambient, IR, Red)
        self.info_ppg = StreamInfo('Muse', 'PPG', 3, 64, 'float32', self.session_id)
        self.outlet_ppg = StreamOutlet(self.info_ppg)
        time.sleep(0.2)
        
        # ACC (3 Channels: X, Y, Z)
        self.info_acc = StreamInfo('Muse', 'ACC', 3, 52, 'float32', self.session_id)
        self.outlet_acc = StreamOutlet(self.info_acc)
        time.sleep(0.2)
        
        # GYRO (3 Channels: X, Y, Z)
        self.info_gyro = StreamInfo('Muse', 'GYRO', 3, 52, 'float32', self.session_id)
        self.outlet_gyro = StreamOutlet(self.info_gyro)
        
        print("🔌 LSL Streams Created (EEG, PPG, ACC, GYRO).")
        
        # Buffer to hold latest values for [TP9, AF7, AF8, TP10]
        self.eeg_buffer = [0.0] * 4 

    def decode_12bit(self, data_bytes):
        samples = []
        payload = data_bytes[2:] 
        for i in range(0, len(payload), 3):
            if i + 2 < len(payload):
                b1, b2, b3 = payload[i], payload[i+1], payload[i+2]
                s1 = (b1 << 4) | (b2 >> 4)
                s2 = ((b2 & 0x0f) << 8) | b3
                samples.extend([s1 - 0x800, s2 - 0x800])
        return samples

    def decode_imu(self, data_bytes, scale=1.0):
        # IMU data is 16-bit signed
        if len(data_bytes) >= 8: # 2 seq + 6 data
             return struct.unpack('>hhh', data_bytes[2:8])
        return None

    # --- HANDLERS ---
    async def eeg_handler(self, sender, data):
        # Decode packet (usually contains 12 samples)
        decoded = self.decode_12bit(data)
        
        # Identify Channel Index by UUID
        # EEG_CHARS order: TP9, AF7, AF8, TP10
        uuid_str = str(sender.uuid).lower()
        if uuid_str in EEG_CHARS:
            idx = EEG_CHARS.index(uuid_str)
            
            if decoded:
                # Muse sends relative packets. For LSL we need absolute consistency.
                # Update the buffer with the LATEST sample from this packet.
                # Ideally we would push 12 separate updates, but for 'Live UI' 
                # a 'Sample & Hold' 60Hz update is sufficient responsiveness.
                # Since Muse sends ~20 packets/sec per channel (256Hz / 12 samples),
                # updating the buffer and pushing is fine.
                
                latest_val = decoded[-1]
                self.eeg_buffer[idx] = latest_val
                
                # Push the TRUE state of all 4 sensors
                # This way, if AF7 updates, we send [TP9_old, AF7_new, AF8_old, TP10_old]
                # Receiver will see the change in AF7 specifically.
                # Receiver will see the change in AF7 specifically.
                self.outlet_eeg.push_sample(self.eeg_buffer)

    async def ppg_handler(self, sender, data):
        # PPG is 24-bit? Or similar to 12-bit?
        # Use decode_12bit logic for now as approximation or pass raw
        decoded = self.decode_12bit(data)
        if decoded and len(decoded) >= 3:
             # Just push first 3
             self.outlet_ppg.push_sample(decoded[:3])
             print(f"P{decoded[:3]}", end=" ", flush=True) # DEBUG PPG VALS

    async def acc_handler(self, sender, data):
        val = self.decode_imu(data)
        if val:
            # Scale to g (approx / 16384 for 2g range)
            vec = [v / 16384.0 for v in val]
            self.outlet_acc.push_sample(vec)
            print("A", end="", flush=True) # DEBUG ACC

    async def gyro_handler(self, sender, data):
        val = self.decode_imu(data)
        if val:
            # Scale to deg/s
            vec = [v * 0.0074768 for v in val] # standard muse scale
            self.outlet_gyro.push_sample(vec)
            # print("G", end="", flush=True) # DEBUG GYRO

    async def run(self):
        """PHASE 6: On-Demand Connection Loop"""
        print("✅ Muse Service Ready (Idle). Waiting for connection request...")
        
        while True:
            # Wait for manual trigger
            if not self.should_scan:
                await asyncio.sleep(0.5)
                continue
            
            # Begin scanning
            self.connection_state = "scanning"
            print("🔎 Scanning for Muse...")
            device = None
            
            try:
                device = await BleakScanner.find_device_by_filter(
                    lambda d, ad: d.name and (MUSE_NAME_FILTER in d.name),
                    timeout=10.0  # 10 second timeout
                )
                
                if not device:
                    print("❌ Muse not found.")
                    self.connection_state = "error"
                    self.should_scan = False  # Stop scanning
                    continue
                
                print(f"✅ Found {device.name}. Connecting...")
                async with BleakClient(device) as client:
                    self.client = client
                    self.connection_state = "connected"
                    print("🔗 Connected! Subscribing to Sensors...")
                    
                    # EEG
                    for char_uuid in EEG_CHARS:
                        await client.start_notify(char_uuid, self.eeg_handler)
                        await asyncio.sleep(0.1)

                    # PPG
                    for char_uuid in PPG_CHARS:
                        await client.start_notify(char_uuid, self.ppg_handler)
                        await asyncio.sleep(0.1)
                        
                    # IMU
                    await client.start_notify(ACC_CHAR, self.acc_handler)
                    await client.start_notify(GYRO_CHAR, self.gyro_handler)
                    
                    print("▶️ Control: Resuming Transmission...")
                    await client.write_gatt_char(CTRL_CHAR, b'\x02d\x0a')
                    
                    print("🚀 MULTI-SENSOR STREAMING LIVE!")
                    print("   Outputting: EEG (4ch), PPG (3ch), ACC (3ch), GYRO (3ch)")
                    
                    # Keep alive loop (until disconnection or manual stop)
                    while self.should_scan:
                        await asyncio.sleep(1)
                    
                    print("🛑 Disconnecting...")
                    self.connection_state = "idle"
                    
            except Exception as e:
                print(f"❌ Connection Error: {e}")
                self.connection_state = "error"
                self.should_scan = False

    def start_connection(self):
        """Trigger connection scan"""
        with self.connection_lock:  # v1.1: Thread-safe
            if self.connection_state == "scanning":  # Prevent double-scan
                return
            self.should_scan = True
            self.connection_state = "scanning"
    
    def stop_connection(self):
        """Stop connection"""
        with self.connection_lock:  # v1.1: Thread-safe
            self.should_scan = False
            self.connection_state = "idle"

def start_stream():
    """Entry point for the monolithic launcher"""
    try:
        asyncio.run(MuseStreamer().run())
    except KeyboardInterrupt:
        print("Stopped.")

if __name__ == "__main__":
    start_stream()
