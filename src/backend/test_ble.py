import asyncio
from bleak import BleakScanner

async def scan():
    print("------- DIRECT BLE SCAN INITIATED -------")
    print("Scanning for 10 seconds...")
    devices = await BleakScanner.discover(timeout=10.0)
    
    found_muse = False
    for d in devices:
        name = d.name or "Unknown"
        # RSSI is usually d.rssi but let's be safe
        rssi = getattr(d, 'rssi', 'N/A')
        print(f"FOUND: {name} [{d.address}] - RSSI: {rssi}")
        if "Muse" in name:
            found_muse = True
            print(">>> MUSE DEVICE DETECTED! <<<")
            
    if not found_muse:
        print("------- RESULT: MARKER NOT FOUND -------")
        with open("final_scan.txt", "w") as f: f.write("NONE")
    else:
        print("------- RESULT: SUCCESS -------")
        with open("final_scan.txt", "w") as f:
            for d in devices:
                if "Muse" in (d.name or ""):
                    f.write(f"{d.name}|{d.address}\n")

if __name__ == "__main__":
    asyncio.run(scan())
