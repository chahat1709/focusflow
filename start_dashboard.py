#!/usr/bin/env python3
"""
Simple web server for FocusFlow Dashboard
Run this script and open http://localhost:8000 in your browser
"""

import http.server
import socketserver
import os
import webbrowser
from pathlib import Path

# Set the port
PORT = 8000

# Get current directory
DIRECTORY = Path(__file__).parent

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def end_headers(self):
        # Add CORS headers to allow all requests
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        # Set proper MIME types
        if self.path.endswith('.css'):
            self.send_header('Content-Type', 'text/css')
        elif self.path.endswith('.js'):
            self.send_header('Content-Type', 'application/javascript')
        super().end_headers()

def start_server():
    """Start the web server and open browser"""
    
    # Change to the correct directory
    os.chdir(DIRECTORY)
    
    # Create server
    with socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
        print(f"🚀 FocusFlow Dashboard Server Started!")
        print(f"📍 Directory: {DIRECTORY}")
        print(f"🌐 Open: http://localhost:{PORT}")
        print(f"🎯 Your dashboard is ready!")
        print(f"⏹️  Press Ctrl+C to stop server")
        print("-" * 50)
        
        # Open browser automatically
        try:
            webbrowser.open(f'http://localhost:{PORT}')
            print("🌐 Browser opened automatically!")
        except:
            print("📝 Could not open browser automatically")
            print(f"🌐 Please open: http://localhost:{PORT}")
        
        try:
            # Start serving
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n⏹️  Server stopped by user")
            httpd.shutdown()

if __name__ == "__main__":
    start_server()
