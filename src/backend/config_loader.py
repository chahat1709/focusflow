import json
import os

DEFAULT_CONFIG = {
    "version": "1.1",
    "build_date": "2026-02-08",
    
    "backend": {
        "port": 5001,
        "host": "localhost"
    },
    
    "features": {
        "ai_coach": False,
        "calibration": True,
        "recording": True
    },
    
    "theme": {
        "primary_color": "#2DD4BF",
        "secondary_color": "#7DD3FC",
        "app_name": "Focus Flow"
    },
    
    "recording": {
        "output_folder": "./recordings",
        "auto_flush_interval": 1.0
    }
}

def load_config():
    """Load configuration from config.json or create default"""
    if os.path.exists('config.json'):
        try:
            with open('config.json', 'r') as f:
                user_config = json.load(f)
                # Merge with defaults (user config overrides)
                return {**DEFAULT_CONFIG, **user_config}
        except Exception as e:
            print(f"⚠️ Config load error: {e}. Using defaults.")
            return DEFAULT_CONFIG
    else:
        # Create default config file
        try:
            with open('config.json', 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            print("✅ Created default config.json")
        except:
            pass
        return DEFAULT_CONFIG

CONFIG = load_config()
