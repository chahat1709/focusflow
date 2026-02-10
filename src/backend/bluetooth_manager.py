import asyncio
from bleak import BleakScanner, BleakClient
import subprocess
import time

class BluetoothManager:
    """Manages Bluetooth scanning and connection to Muse headband"""
    
    # Muse GATT UUIDs
    BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
    BATTERY_LEVEL_CHAR_UUID = "00002a19-0000-1000-8000-00805f9b34fb"
    
    def __init__(self):
        self.muse_device = None
        self.client = None
        self.battery_level = None
        
    async def scan_devices(self, timeout=10):
        """Scan for nearby Muse devices"""
        devices = await BleakScanner.discover(timeout=timeout)
        muse_devices = []
        
        for device in devices:
            if device.name and 'Muse' in device.name:
                muse_devices.append({
                    'name': device.name,
                    'address': device.address,
                    'rssi': device.rssi if hasattr(device, 'rssi') else -100
                })
        
        return muse_devices
    
    async def connect_device(self, address):
        """Connect to a specific Muse device"""
        try:
            self.client = BleakClient(address)
            await self.client.connect()
            self.muse_device = address
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    async def get_battery_level(self):
        """Read battery level from connected Muse"""
        if not self.client or not self.client.is_connected:
            return None
        
        try:
            # Read battery characteristic
            battery_bytes = await self.client.read_gatt_char(self.BATTERY_LEVEL_CHAR_UUID)
            self.battery_level = int.from_bytes(battery_bytes, byteorder='little')
            return self.battery_level
        except Exception as e:
            print(f"Battery read failed: {e}")
            return None
    
    def start_muselsl_stream(self, device_address):
        """Launch muselsl stream for selected device"""
        try:
            # Kill any existing muselsl process
            subprocess.run(['taskkill', '/F', '/IM', 'muselsl.exe'], 
                         stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            time.sleep(1)
            
            # Start new stream with specific device
            subprocess.Popen(['muselsl', 'stream', '--address', device_address],
                           creationflags=subprocess.CREATE_NEW_CONSOLE)
            return True
        except Exception as e:
            print(f"Failed to start muselsl: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Muse"""
        if self.client:
            await self.client.disconnect()
            self.client = None
            self.muse_device = None

# Global instance
bt_manager = BluetoothManager()

# Sync wrappers for Flask routes
def scan_for_muse():
    """Synchronous wrapper for scanning"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    devices = loop.run_until_complete(bt_manager.scan_devices())
    loop.close()
    return devices

def connect_to_muse(address):
    """Synchronous wrapper for connection"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success = loop.run_until_complete(bt_manager.connect_device(address))
    loop.close()
    
    if success:
        # Start muselsl stream
        bt_manager.start_muselsl_stream(address)
    
    return success

def get_battery():
    """Synchronous wrapper for battery reading"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    battery = loop.run_until_complete(bt_manager.get_battery_level())
    loop.close()
    return battery
