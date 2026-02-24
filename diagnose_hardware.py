import asyncio
import logging
import sys
import traceback

# Setup logging to console — FORCE UTF-8 on Windows
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-7s | %(name)s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('FocusFlow.Test')

# Import our BLE client
try:
    from muse_ble import MuseBLEClient
    print("[OK] MuseBLEClient imported successfully.")
except ImportError as e:
    print(f"[FAIL] Failed to import MuseBLEClient: {e}")
    sys.exit(1)

def dummy_eeg(ch_idx, samples):
    if dummy_eeg.count < 5:
        print(f"  [DATA] EEG ch{ch_idx}: {len(samples)} samples, first={samples[0]:.2f}")
    dummy_eeg.count += 1
dummy_eeg.count = 0

def dummy_imu(sensor_type, samples):
    if dummy_imu.count < 3:
        print(f"  [DATA] IMU {sensor_type}: {len(samples)} samples")
    dummy_imu.count += 1
dummy_imu.count = 0

def dummy_ppg(channel_name, samples):
    if dummy_ppg.count < 3:
        print(f"  [DATA] PPG {channel_name}: {len(samples)} samples")
    dummy_ppg.count += 1
dummy_ppg.count = 0

async def main():
    print("")
    print("=" * 50)
    print("   FOCUSFLOW HARDWARE DIAGNOSTIC TOOL")
    print("=" * 50)
    print("")

    client = MuseBLEClient(
        on_eeg_sample=dummy_eeg,
        on_imu_sample=dummy_imu,
        on_ppg_sample=dummy_ppg,
    )

    print("[STEP 1] Scanning for Muse (timeout=10s, retries=3)...")
    try:
        success = await client.auto_connect(max_retries=3, scan_timeout=10.0)
    except Exception as e:
        print(f"[ERROR] auto_connect raised: {e}")
        traceback.print_exc()
        success = False

    if success:
        print("")
        print("*" * 50)
        print(f"   [OK] Muse CONNECTED: {client.device_name} ({client.device_address})")
        print("*" * 50)
        print("")
        print("[STEP 2] Listening for data for 10 seconds...")
        await asyncio.sleep(10)
        print(f"   EEG packets received: {dummy_eeg.count}")
        print(f"   IMU packets received: {dummy_imu.count}")
        print(f"   PPG packets received: {dummy_ppg.count}")
        print("")
        print("[STEP 3] Disconnecting...")
        await client.disconnect()
        print("[DONE] Test complete - Muse is fully operational!")
    else:
        print("")
        print("!" * 50)
        print("   [FAIL] Could not connect to Muse headband.")
        print("   Checklist:")
        print("   1. Is the headband ON? (should have flashing light)")
        print("   2. Is Bluetooth ON on this PC?")
        print("   3. Is another app connected to it? (BlueMuse, Mind Monitor)")
        print("   4. Try turning the Muse OFF and ON again.")
        print("!" * 50)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest cancelled by user.")
    except Exception as e:
        print(f"\n[FATAL] Unhandled error: {e}")
        traceback.print_exc()
