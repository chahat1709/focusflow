# -*- coding: utf-8 -*-
import threading
import time
import webbrowser
import os
import sys

# Ensure current directory is in path for imports
sys.path.append(os.getcwd())

from src.backend.main import start_server
from muse_connect import MuseStreamer
import asyncio

# Global streamer instance for API access
_streamer_instance = None

# FIX FOR FROZEN NO-CONSOLE APPS
# PyInstaller noconsole mode crashes web servers that try to print to stdout
if getattr(sys, 'frozen', False):
    # Redirect stdout/stderr to null or log file
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

def run_streamer_thread():
    """Run the MuseStreamer in its own thread with asyncio loop"""
    global _streamer_instance
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    _streamer_instance = MuseStreamer()
    loop.run_until_complete(_streamer_instance.run())

def get_streamer():
    """Get the global streamer instance"""
    return _streamer_instance

def main():
    print("FOCUS FLOW LAUNCHER: Professional Mode")
    print("-----------------------------------")
    
    # 1. Start Muse Streamer (Silent - no auto-scan)
    print(">> Starting Muse Service (Idle)...")
    stream_thread = threading.Thread(target=run_streamer_thread, daemon=True)
    stream_thread.start()
    
    # Wait for streamer to initialize
    time.sleep(2)
    
    # 2. Start Backend Server (Port 5001) - Pass streamer reference
    print(">> Starting Backend Server...")
    from src.backend import main as backend_main
    backend_main._streamer_instance = _streamer_instance  # Inject streamer
    
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # 3. Wait for initialization
    print(">> Waiting for services to warm up...")
    time.sleep(5)  # Increased wait time
    
    # 4. Launch Dashboard
    dashboard_path = os.path.abspath("dashboard.html")
    print(f">> Opening Dashboard: {dashboard_path}")
    webbrowser.open(f"file:///{dashboard_path}")
    
    print("\n>> SYSTEM ONLINE (PROFESSIONAL MODE)")
    print(">> Use the dashboard to connect to your Muse.")
    
    # 5. Keep Alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(">> Shutting down...")
        sys.exit(0)

if __name__ == "__main__":
    main()
