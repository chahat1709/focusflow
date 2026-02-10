import asyncio
from bleak import BleakScanner

async def scan():
    print("search...")
    devices = await BleakScanner.discover(timeout=5.0)
    found = False
    for d in devices:
        if "Muse" in (d.name or "") or d.address.startswith("00:55:DA"):
            print(f"✅ FOUND MUSE: {d.name} [{d.address}]")
            found = True
        else:
            # print(f"  - {d.name} [{d.address}]")
            pass
            
    if not found:
        print("❌ NO MUSE DEVICE FOUND.")

if __name__ == "__main__":
    asyncio.run(scan())
