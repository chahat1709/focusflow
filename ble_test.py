import asyncio
from bleak import BleakScanner

async def run():
    print("BLE Scanning for 5 seconds...")
    devices = await BleakScanner.discover(timeout=5.0)
    for d in devices:
        print(f"Found: {d.name} ({d.address})")
    if not devices:
        print("No devices found.")

if __name__ == '__main__':
    asyncio.run(run())
