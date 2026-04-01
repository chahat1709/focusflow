"""
muse_ble.py — Direct BLE connector for Muse 2 headband.
Uses only `bleak` (no muselsl, no pylsl).
Handles scan → connect → subscribe → parse EEG data.
"""

import asyncio
import struct
import logging
import time
import os
import numpy as np
from typing import Optional, Callable, List

logger = logging.getLogger('FocusFlow.BLE')

# ═══════════════════════════════════════════════════════════════
#  MUSE 2 BLE PROTOCOL CONSTANTS
# ═══════════════════════════════════════════════════════════════

# GATT Service
MUSE_SERVICE_UUID = "0000fe8d-0000-1000-8000-00805f9b34fb"

# Control characteristic (write commands here)
CONTROL_UUID = "273e0001-4c4d-454d-96be-f03bac821358"

# EEG channel characteristics (subscribe for notifications)
EEG_UUIDS = {
    'TP9':  "273e0003-4c4d-454d-96be-f03bac821358",
    'AF7':  "273e0004-4c4d-454d-96be-f03bac821358",
    'AF8':  "273e0005-4c4d-454d-96be-f03bac821358",
    'TP10': "273e0006-4c4d-454d-96be-f03bac821358",
}

# Accelerometer / Gyro
ACCEL_UUID = "273e000a-4c4d-454d-96be-f03bac821358"
GYRO_UUID  = "273e0009-4c4d-454d-96be-f03bac821358"

# PPG (Heart Rate - Optical)
PPG_UUIDS = {
    'PPG1': "273e000f-4c4d-454d-96be-f03bac821358",
    'PPG2': "273e0010-4c4d-454d-96be-f03bac821358",
    'PPG3': "273e0011-4c4d-454d-96be-f03bac821358",
}

# Control commands
CMD_START    = bytearray([0x02, 0x73, 0x0a])          # 's' Start streaming
CMD_STOP     = bytearray([0x02, 0x68, 0x0a])          # 'h' Stop streaming
CMD_HALT     = bytearray([0x02, 0x68, 0x0a])          # 'h' Halt
CMD_KEEP     = bytearray([0x02, 0x6b, 0x0a])          # 'k' Keep-alive
CMD_RESUME   = bytearray([0x02, 0x64, 0x0a])          # 'd' Resume
CMD_PRESET_P21 = bytearray([0x04, 0x70, 0x32, 0x31, 0x0a])  # 'p21'
CMD_PRESET_P50 = bytearray([0x04, 0x70, 0x35, 0x30, 0x0a])  # 'p50'
CMD_DEV_INFO = bytearray([0x02, 0x76, 0x0a])          # 'v' Version

# ═══════════════════════════════════════════════════════════════
#  PACKET PARSERS
# ═══════════════════════════════════════════════════════════════

def parse_eeg_packet(raw: bytes) -> List[float]:
    """
    Parse a 20-byte Muse EEG notification into 12 samples.
    Format: 2-byte counter + 12 × 12-bit unsigned values (packed big-endian).
    Each sample represents microvolts (µV).
    """
    if len(raw) < 20:
        return []

    # Skip first 2 bytes (packet counter)
    # Remaining 18 bytes = 12 × 12-bit values (144 bits = 18 bytes)
    samples = []
    bit_buffer = 0
    bits_in_buffer = 0

    for byte_val in raw[2:]:
        bit_buffer = (bit_buffer << 8) | byte_val
        bits_in_buffer += 8

        while bits_in_buffer >= 12:
            bits_in_buffer -= 12
            sample_raw = (bit_buffer >> bits_in_buffer) & 0xFFF
            # Convert 12-bit unsigned to microvolts
            # Muse 2 reference: 1.0 µV per LSB approximately
            uv = (sample_raw - 2048) * 0.48828125  # Center and scale
            samples.append(uv)

    return samples[:12]  # Exactly 12 samples per packet

def parse_imu_packet(raw: bytes, scale: float = 1.0) -> List[dict]:
    """
    Parse a 20-byte Muse IMU (Accel/Gyro) notification.
    Format: 2-byte sequence + 3 samples × (X, Y, Z) 16-bit signed big-endian.
    Returns list of 3 dicts: [{'x':..., 'y':..., 'z':...}, ...]
    """
    if len(raw) < 20: 
        return []
    
    data = raw[2:] # Skip sequence
    # 18 bytes / 2 = 9 int16 values (3 samples * 3 axes)
    values = []
    for i in range(0, 18, 2):
        val = int.from_bytes(data[i:i+2], byteorder='big', signed=True)
        values.append(val * scale)
        
    samples = []
    for i in range(0, 9, 3):
        samples.append({'x': values[i], 'y': values[i+1], 'z': values[i+2]})
        
    return samples

def parse_ppg_packet(raw: bytes) -> List[float]:
    """
    Parse a 20-byte Muse PPG notification.
    Format: 2-byte sequence + 6 × 24-bit unsigned values (packed big-endian).
    Returns list of 6 samples (raw intensity).
    """
    if len(raw) < 20:
        return []
        
    # Skip sequence (2 bytes)
    data = raw[2:]
    # 18 bytes = 6 samples * 3 bytes (24-bit)
    samples = []
    for i in range(0, 18, 3):
        # 24-bit big-endian
        val = (data[i] << 16) | (data[i+1] << 8) | data[i+2]
        samples.append(val)
        
    return samples

# ═══════════════════════════════════════════════════════════════
#  MUSE BLE CLIENT
# ═══════════════════════════════════════════════════════════════

class MuseBLEClient:
    """
    Direct BLE connection to Muse 2.
    Scans → Connects → Subscribes to EEG channels → Parses data.
    """

    def __init__(self, on_eeg_sample: Optional[Callable] = None, on_imu_sample: Optional[Callable] = None, on_ppg_sample: Optional[Callable] = None):
        """
        Args:
            on_eeg_sample: Callback(channel_index: int, samples: List[float])
            on_imu_sample: Callback(sensor_type: str, samples: List[dict])
            on_ppg_sample: Callback(channel_name: str, samples: List[float])
        """
        self.on_eeg_sample = on_eeg_sample
        self.on_imu_sample = on_imu_sample
        self.on_ppg_sample = on_ppg_sample
        self._client = None
        self._connected = False
        self._address = None
        self._name = None
        self._keep_alive_task = None
        self._channel_names = list(EEG_UUIDS.keys())

        # Latest sample per channel (for snapshot)
        self.latest = {
            'TP9': 0.0, 'AF7': 0.0, 'AF8': 0.0, 'TP10': 0.0,
            'timestamp': 0.0,
            'sample_count': 0,
        }
        self._log_counter = 0 
        self._last_packet_times = {ch: 0.0 for ch in EEG_UUIDS.keys()}
        self._packet_counts = {ch: 0 for ch in EEG_UUIDS.keys()}
        self._reconnect_attempts = 0
        self._watchdog_task = None


    @property
    def connected(self):
        return self._connected

    @property
    def device_name(self):
        return self._name or 'Unknown'

    @property
    def device_address(self):
        return self._address or 'Unknown'

    # ── SCAN ─────────────────────────────────────────────────
    ADDR_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.muse_address')

    async def scan(self, timeout: float = 10.0) -> Optional[dict]:
        """Scan for a Muse device via BLE. Returns {name, address} or None.
        
        On Windows, BLE device names sometimes come back as None/Unknown 
        on subsequent scans from threads. We work around this by:
        1. Checking a cache file with the last known Muse address
        2. Scanning with multiple name resolution strategies
        """
        try:
            from bleak import BleakScanner

            # 1. Try cached address first (from previous successful connection)
            if os.path.isfile(self.ADDR_CACHE_FILE):
                with open(self.ADDR_CACHE_FILE, 'r') as f:
                    cached = f.read().strip()
                if cached:
                    logger.info(f"Trying cached Muse address: {cached}")
                    return {'name': 'Muse (cached)', 'address': cached}

            # 2. Full BLE scan
            logger.info(f"BLE scanning for Muse device (timeout={timeout}s)...")
            devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
            logger.info(f"Scan found {len(devices)} total devices nearby.")

            for d, adv in devices.values():
                # Try multiple name sources (Windows caching workaround)
                name = d.name or adv.local_name or 'Unknown'
                addr = d.address or 'NoAddr'
                logger.info(f"  Device: {name} ({addr})")
                if 'muse' in name.lower():
                    logger.info(f"*** Found Muse MATCH: {name} ({addr}) ***")
                    # Cache this address for future use
                    try:
                        with open(self.ADDR_CACHE_FILE, 'w') as f:
                            f.write(addr)
                    except Exception:
                        pass
                    return {'name': name, 'address': addr}

            logger.info("  Scan complete - No 'muse' string found in any device name.")
            return None

        except Exception as e:
            logger.error(f"BLE scan error: {e}")
            return None

    # ── CONNECT ──────────────────────────────────────────────
    async def connect(self, address: str) -> bool:
        """Connect to Muse at given BLE address."""
        try:
            from bleak import BleakClient

            logger.info(f"Connecting to Muse at {address}...")
            # Pass disconnect callback in constructor (bleak >= 0.21 API)
            self._client = BleakClient(address, timeout=20.0, disconnected_callback=self._on_disconnect)
            await self._client.connect()

            if not self._client.is_connected:
                logger.error(f"Connection to {address} FAILED - Bleak reports not connected.")
                return False

            self._connected = True
            self._address = address
            self._reconnect_attempts = 0
            logger.info(f"[OK] BLE connected to {address}")

            # 1. Halt (reset any previous state)
            await self._client.write_gatt_char(CONTROL_UUID, CMD_HALT, response=False)
            await asyncio.sleep(0.3)

            # 2. Privacy/Version Handshake
            await self._client.write_gatt_char(CONTROL_UUID, CMD_DEV_INFO, response=False)
            await asyncio.sleep(0.3)

            # 3. Preset (p50) FIRST - tells firmware which channels to activate
            #    Must be sent BEFORE subscribing to notifications
            await self._client.write_gatt_char(CONTROL_UUID, CMD_PRESET_P50, response=False)
            await asyncio.sleep(1.0)  # Give firmware time to reconfigure
            logger.info("  [OK] Preset P50 sent (EEG+PPG+Accel+Gyro)")

            # 4. Subscribe to EEG channels (AFTER preset)
            for i, (ch_name, uuid) in enumerate(EEG_UUIDS.items()):
                ch_idx = i
                def make_handler(idx, name):
                    def handler(sender, data):
                        self._on_eeg_notification(idx, name, data)
                    return handler
                await self._client.start_notify(uuid, make_handler(ch_idx, ch_name))
                logger.info(f"  [OK] Subscribed to {ch_name}")

            # 4b. Subscribe to IMU (Accel/Gyro)
            for s_type, uuid in [('accel', ACCEL_UUID), ('gyro', GYRO_UUID)]:
                def make_imu_handler(st):
                    def handler(sender, data):
                        self._on_imu_notification(st, data)
                    return handler
                await self._client.start_notify(uuid, make_imu_handler(s_type))
                logger.info(f"  [OK] Subscribed to {s_type.upper()}")

            # 4c. Subscribe to PPG (Heart)
            for p_name, uuid in PPG_UUIDS.items():
                def make_ppg_handler(pn):
                    def handler(sender, data):
                        self._on_ppg_notification(pn, data)
                    return handler
                await self._client.start_notify(uuid, make_ppg_handler(p_name))
                logger.info(f"  [OK] Subscribed to {p_name}")

            # 5. Resume (d) — wake from halt
            await self._client.write_gatt_char(CONTROL_UUID, CMD_RESUME, response=False)
            await asyncio.sleep(0.3)

            # 6. Start Streaming (s)
            await self._client.write_gatt_char(CONTROL_UUID, CMD_START, response=False)
            await asyncio.sleep(0.3)

            # 7. Keep-alive (k) — first ping
            await self._client.write_gatt_char(CONTROL_UUID, CMD_KEEP, response=False)
            
            # 8. Start background health watchdog
            if self._watchdog_task: self._watchdog_task.cancel()
            self._watchdog_task = asyncio.create_task(self._stability_watchdog())
            
            # 9. Start keep-alive loop
            self._keep_alive_task = asyncio.ensure_future(self._keep_alive_loop())

            logger.info("[OK] EEG+IMU+PPG commands sent and watchdog active")
            return True

        except Exception as e:
            import traceback as _tb
            logger.error(f"BLE connect error: {e}")
            logger.error(_tb.format_exc())
            self._connected = False
            return False

    # ── DISCONNECT ───────────────────────────────────────────
    async def disconnect(self):
        """Cleanly disconnect."""
        self._connected = False
        if self._watchdog_task:
            self._watchdog_task.cancel()
        if self._client and self._client.is_connected:
            try:
                await self._client.write_gatt_char(CONTROL_UUID, CMD_STOP, response=False)
                await self._client.disconnect()
            except Exception as e:
                logger.warning(f"BLE disconnect cleanup error: {e}")
        self._client = None
        logger.info("BLE disconnected")

    def _on_disconnect(self, client):
        """Called by Bleak when device drops."""
        if self._connected:
            logger.warning("!!! BLE Hardware Disconnect detected !!!")
            # We don't set self._connected = False here yet to trigger the watchdog

    async def _stability_watchdog(self):
        """Self-healing loop: monitors data flow and reconnects if stalled."""
        while self._connected:
            await asyncio.sleep(2.0)
            now = time.time()
            stalled = False
            for ch, last_t in self._last_packet_times.items():
                if now - last_t > 3.0: # 3 seconds of no data
                    stalled = True
                    break
            
            if stalled or (self._client and not self._client.is_connected):
                logger.warning("Data stream STALLED. Attempting full reconnect handshake...")
                try:
                    # Attempt reconnect
                    await self._client.connect(timeout=5.0)
                    # Full handshake: Halt → DevInfo → Preset P50 → Resume → Start
                    await self._client.write_gatt_char(CONTROL_UUID, CMD_HALT, response=False)
                    await asyncio.sleep(0.3)
                    await self._client.write_gatt_char(CONTROL_UUID, CMD_DEV_INFO, response=False)
                    await asyncio.sleep(0.3)
                    await self._client.write_gatt_char(CONTROL_UUID, CMD_PRESET_P50, response=False)
                    await asyncio.sleep(1.0)
                    await self._client.write_gatt_char(CONTROL_UUID, CMD_RESUME, response=False)
                    await asyncio.sleep(0.3)
                    await self._client.write_gatt_char(CONTROL_UUID, CMD_START, response=False)
                    await asyncio.sleep(0.3)
                    await self._client.write_gatt_char(CONTROL_UUID, CMD_KEEP, response=False)
                    logger.info("[OK] Full reconnect handshake completed")
                    
                    # Reset stall timers to prevent immediate re-trigger
                    now = time.time()
                    for ch in self._last_packet_times:
                        self._last_packet_times[ch] = now
                        
                except Exception as e:
                    logger.error(f"Reconnect failed: {e}")
                    # Give up and let the main loop do a full robust re-scan
                    self._connected = False

    def get_sqi(self) -> float:
        """Calculate Signal Quality Index (0.0 to 1.0)."""
        if not self._connected: return 0.0
        now = time.time()
        gaps = [now - t for t in self._last_packet_times.values()]
        avg_gap = sum(gaps) / len(gaps)
        # Ideal gap should be < 0.1s. If > 2s, SQI drops to 0.
        score = max(0.0, 1.0 - (avg_gap / 2.0))
        return score

    # ── NOTIFICATION HANDLERS ────────────────────────────────
    def _on_eeg_notification(self, ch_idx: int, ch_name: str, data: bytes):
        """Called when a BLE notification arrives for an EEG channel."""
        self._last_packet_times[ch_name] = time.time()
        self._packet_counts[ch_name] += 1
        
        if self._log_counter < 10:
            logger.info(f"BLE Notification: {ch_name} ({len(data)} bytes)")
        
        samples = parse_eeg_packet(bytes(data))
        if not samples:
            if self._log_counter < 10:
                logger.warning(f"  Empty samples parsed from {ch_name}")
            return

        if self._log_counter < 10:
            logger.info(f"  Parsed {len(samples)} samples: {samples[:3]}...")
            self._log_counter += 1

        # Store latest RMS value for this channel
        rms = np.sqrt(np.mean(np.array(samples) ** 2))
        self.latest[ch_name] = rms
        self.latest['timestamp'] = time.time()
        self.latest['sample_count'] += 1

        # Forward to callback
        if self.on_eeg_sample:
            try:
                self.on_eeg_sample(ch_idx, samples)
            except Exception as e:
                logger.error(f"EEG callback error: {e}")

    def _on_imu_notification(self, sensor_type: str, data: bytes):
        """Called when a BLE notification arrives for Accel/Gyro."""
        # Calibrated scale factors for Muse 2 hardware:
        # Accelerometer: 16384 LSB/g → multiply by 1/16384 to get g-force
        # Gyroscope: 131 LSB/(deg/s) → multiply by 1/131 to get deg/s
        scale = 1.0 / 16384.0 if sensor_type == 'accel' else 1.0 / 131.0
        samples = parse_imu_packet(bytes(data), scale=scale)
        if not samples:
            return
            
        if self.on_imu_sample:
            try:
                self.on_imu_sample(sensor_type, samples)
            except Exception as e:
                logger.error(f"IMU callback error: {e}")

    def _on_ppg_notification(self, channel_name: str, data: bytes):
        """Called when a BLE notification arrives for PPG."""
        samples = parse_ppg_packet(bytes(data))
        if not samples:
            return
            
        if self.on_ppg_sample:
            try:
                self.on_ppg_sample(channel_name, samples)
            except Exception as e:
                logger.error(f"PPG callback error: {e}")

    # ── KEEP ALIVE ───────────────────────────────────────────
    async def _keep_alive_loop(self):
        """Send keep-alive every 8 seconds to prevent Muse from disconnecting.
        Muse 2 firmware timeout is ~10-12s; 8s gives safe margin for BLE jitter."""
        while self._connected:
            try:
                await asyncio.sleep(8)
                if self._client and self._client.is_connected:
                    await self._client.write_gatt_char(CONTROL_UUID, CMD_KEEP)
                else:
                    logger.warning("Muse disconnected unexpectedly")
                    self._connected = False
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Keep-alive error: {e}")
                self._connected = False
                break

    # ── HIGH-LEVEL: SCAN + CONNECT ───────────────────────────
    async def auto_connect(self, max_retries: int = 6, scan_timeout: float = 5.0) -> bool:
        """Scan for a Muse and connect automatically."""
        for attempt in range(1, max_retries + 1):
            logger.info(f"BLE scan attempt {attempt}/{max_retries}...")
            result = await self.scan(timeout=scan_timeout)
            if result:
                self._name = result['name']
                success = await self.connect(result['address'])
                if success:
                    return True
            await asyncio.sleep(2)

        logger.error("[FAIL] No Muse found after all scan attempts.")
        return False
