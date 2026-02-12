# -*- coding: utf-8 -*-
import threading
import time
import os
import sys
import socket

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
    try:
        # Use TEMP directory (always exists and writable)
        log_file = os.path.join(os.environ.get('TEMP', '.'), 'FocusFlow_debug.log')
        
        # Redirect stdout/stderr to log file
        sys.stdout = open(log_file, 'w', buffering=1)
        sys.stderr = open(log_file, 'w', buffering=1)
        print(f"=== FocusFlow Debug Log ===")
        print(f"Started at {time.ctime()}")
        print(f"Log file: {log_file}")
    except Exception as e:
        # If logging fails, continue without it (better than crashing)
        pass

def find_free_port():
    """Find an available port dynamically"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def check_server_ready(port, timeout=10):
    """Wait for Flask server to be responsive"""
    import urllib.request
    url = f"http://localhost:{port}/api/status"
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except:
            time.sleep(0.3)
    return False

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

def show_error_dialog(title, message):
    """Display error message to user"""
    try:
        import webview
        # Create a simple error window
        webview.create_window(title, html=f"""
            <html>
            <head><style>
                body {{ font-family: Arial; padding: 40px; background: #f44336; color: white; }}
                h1 {{ font-size: 24px; }}
                pre {{ background: rgba(0,0,0,0.3); padding: 20px; border-radius: 5px; }}
            </style></head>
            <body>
                <h1>⚠️ {title}</h1>
                <pre>{message}</pre>
                <p>Please contact support with this error message.</p>
            </body>
            </html>
        """, width=600, height=400)
        webview.start()
    except:
        # Fallback to console if webview fails
        print(f"\n{'='*60}\nERROR: {title}\n{message}\n{'='*60}\n")
        input("Press Enter to exit...")

def main():
    try:
        print("FOCUS FLOW LAUNCHER: Professional Mode")
        print("-----------------------------------")
        
        # 1. Find available port dynamically
        port = find_free_port()
        print(f">> Allocated Port: {port}")
        
        # 2. Start Muse Streamer (Silent - no auto-scan)
        print(">> Starting Muse Service (Idle)...")
        stream_thread = threading.Thread(target=run_streamer_thread, daemon=True)
        stream_thread.start()
        
        # Wait for streamer to initialize
        time.sleep(2)
        
        # 3. Start Backend Server on dynamic port
        print(f">> Starting Backend Server on port {port}...")
        server_thread = threading.Thread(
            target=lambda: start_server(get_streamer, port=port),
            daemon=True
        )
        server_thread.start()
        
        # 4. Wait for server health check
        print(">> Waiting for backend to be ready...")
        if not check_server_ready(port, timeout=15):
            raise Exception(f"Backend server failed to start on port {port}.\nPossible causes:\n- Port blocked by firewall\n- Missing dependencies\n- Python runtime error")
        
        print(">> Backend is READY!")
        
        # 5. Launch Dashboard (Native Window Mode)
        url = f"http://localhost:{port}"
        print(f">> Opening App Window: {url}")
        
        import webview
        
        # Create a professional app window
        window = webview.create_window(
            title='Focus Flow - Professional', 
            url=url, 
            width=1280, 
            height=850, 
            resizable=True,
            confirm_close=True,
            text_select=False,  # Disable text selection (app feel)
            zoomable=False      # Disable zooming
        )
        
        # Start the GUI loop
        webview.start(debug=False, http_server=True)
        
        print("\n>> SYSTEM ONLINE (PROFESSIONAL MODE)")
        
        # When window closes, we exit
        print(">> App closed. Shutting down...")
        sys.exit(0)
        
    except Exception as e:
        # Global error handler - show user-friendly error
        error_msg = f"{type(e).__name__}: {str(e)}"
        show_error_dialog("Focus Flow Startup Error", error_msg)
        sys.exit(1)

if __name__ == "__main__":
    main()
