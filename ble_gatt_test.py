"""Step-by-step test with CORRECT command order: Preset BEFORE subscribe."""
import asyncio
import sys
import io
import traceback

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

LOG_FILE = "ble_test_result.txt"

class Logger:
    def __init__(self, path):
        self.f = open(path, 'w', encoding='utf-8')
    def log(self, msg):
        line = str(msg)
        self.f.write(line + '\n')
        self.f.flush()
        print(line)
    def close(self):
        self.f.close()

CONTROL_UUID = "273e0001-4c4d-454d-96be-f03bac821358"
EEG_UUIDS = {
    'TP9':  "273e0003-4c4d-454d-96be-f03bac821358",
    'AF7':  "273e0004-4c4d-454d-96be-f03bac821358",
    'AF8':  "273e0005-4c4d-454d-96be-f03bac821358",
    'TP10': "273e0006-4c4d-454d-96be-f03bac821358",
}
ACCEL_UUID = "273e000a-4c4d-454d-96be-f03bac821358"
GYRO_UUID  = "273e0009-4c4d-454d-96be-f03bac821358"
PPG_UUIDS = {
    'PPG1': "273e000f-4c4d-454d-96be-f03bac821358",
    'PPG2': "273e0010-4c4d-454d-96be-f03bac821358",
    'PPG3': "273e0011-4c4d-454d-96be-f03bac821358",
}
CMD_HALT       = bytearray([0x02, 0x68, 0x0a])
CMD_DEV_INFO   = bytearray([0x02, 0x76, 0x0a])
CMD_RESUME     = bytearray([0x02, 0x64, 0x0a])
CMD_START      = bytearray([0x02, 0x73, 0x0a])
CMD_KEEP       = bytearray([0x02, 0x6b, 0x0a])
CMD_PRESET_P50 = bytearray([0x04, 0x70, 0x35, 0x30, 0x0a])

data_count = 0

def on_notify(sender, data):
    global data_count
    data_count += 1

async def main():
    L = Logger(LOG_FILE)
    try:
        from bleak import BleakScanner, BleakClient
        
        L.log("=== STEP 1: Scan (10s) ===")
        devices = await BleakScanner.discover(timeout=10.0)
        muse = None
        for d in devices:
            if d.name and 'muse' in d.name.lower():
                muse = d
        if not muse:
            L.log("FAIL: No Muse found")
            L.close()
            return
        L.log(f"OK: Found {muse.name} ({muse.address})")
        
        L.log("=== STEP 2: GATT Connect ===")
        client = BleakClient(muse.address, timeout=20.0)
        await client.connect()
        L.log(f"OK: Connected = {client.is_connected}")
        
        L.log("=== STEP 3: HALT ===")
        await client.write_gatt_char(CONTROL_UUID, CMD_HALT, response=False)
        await asyncio.sleep(0.3)
        L.log("OK: HALT sent")
        
        L.log("=== STEP 4: DEV_INFO ===")
        await client.write_gatt_char(CONTROL_UUID, CMD_DEV_INFO, response=False)
        await asyncio.sleep(0.3)
        L.log("OK: DEV_INFO sent")
        
        L.log("=== STEP 5: PRESET P50 (BEFORE subscribe!) ===")
        await client.write_gatt_char(CONTROL_UUID, CMD_PRESET_P50, response=False)
        await asyncio.sleep(1.0)
        L.log("OK: PRESET P50 sent")
        
        L.log("=== STEP 6: Subscribe EEG ===")
        for ch_name, uuid in EEG_UUIDS.items():
            await client.start_notify(uuid, on_notify)
            L.log(f"OK: Subscribed to {ch_name}")
        
        L.log("=== STEP 7: Subscribe IMU ===")
        for name, uuid in [('ACCEL', ACCEL_UUID), ('GYRO', GYRO_UUID)]:
            await client.start_notify(uuid, on_notify)
            L.log(f"OK: Subscribed to {name}")
        
        L.log("=== STEP 8: Subscribe PPG ===")
        for name, uuid in PPG_UUIDS.items():
            await client.start_notify(uuid, on_notify)
            L.log(f"OK: Subscribed to {name}")
        
        L.log("=== STEP 9: RESUME ===")
        await client.write_gatt_char(CONTROL_UUID, CMD_RESUME, response=False)
        await asyncio.sleep(0.3)
        L.log("OK: RESUME sent")
        
        L.log("=== STEP 10: START + KEEP ===")
        await client.write_gatt_char(CONTROL_UUID, CMD_START, response=False)
        await asyncio.sleep(0.3)
        await client.write_gatt_char(CONTROL_UUID, CMD_KEEP, response=False)
        L.log("OK: START + KEEP sent")
        
        L.log("=== STEP 11: Listen 15s ===")
        for i in range(15):
            await asyncio.sleep(1)
            L.log(f"  {i+1}s: {data_count} notifications so far")
        
        L.log(f"Total notifications: {data_count}")
        
        L.log("=== Disconnect ===")
        await client.disconnect()
        L.log("OK: Disconnected")
        
        if data_count > 0:
            L.log("RESULT: *** SUCCESS *** Data is flowing!")
        else:
            L.log("RESULT: Connected but NO DATA received")
    
    except Exception as e:
        L.log(f"ERROR: {e}")
        L.log(traceback.format_exc())
    finally:
        L.close()

if __name__ == '__main__':
    asyncio.run(main())
