#!/usr/bin/env python3
"""
Nova TON Monitor & API Server - Production Entry Point
Main entry point for the TON blockchain monitoring system with API server
"""

import sys
import os
import threading
import time
from pathlib import Path

# Add monitor root and src to path for imports
monitor_root = Path(__file__).parent
sys.path.insert(0, str(monitor_root))
sys.path.insert(0, str(monitor_root / 'src'))

def start_api_server():
    """Start the API server in a separate thread."""
    try:
        print("🌐 Starting API server...")
        from config.server_config import server_config
        from api.marketplace_api_complete import app
        
        # Use centralized configuration
        host = '0.0.0.0'  # Bind to all interfaces
        port = server_config.PORT
        
        print(f"🌐 Server will be accessible at: {server_config.get_server_url()}")
        app.run(host=host, port=port, debug=False, threaded=True)
    except Exception as e:
        print(f"❌ API server error: {e}")

def start_monitor():
    """Start the blockchain monitor."""
    try:
        print("⛓️ Starting blockchain monitor...")
        # Import and run the working monitor
        from core.monitor import main as monitor_main
        monitor_main()
    except ImportError as e:
        print(f"❌ Failed to import monitor: {e}")
        print("💡 Please check your Python environment and dependencies")
    except Exception as e:
        print(f"❌ Monitor error: {e}")

def main():
    """Main entry point for Nova TON Monitor with API server."""
    print("=" * 60)
    print(" NOVA TON MONITOR & API SERVER - PRODUCTION")
    print("=" * 60)
    print("Starting integrated system...")
    
    try:
        # Start API server in background thread
        api_thread = threading.Thread(target=start_api_server, daemon=True)
        api_thread.start()
        
        # Give API server time to start
        time.sleep(2)
        print("✅ API server started successfully")
        
        # Start monitor in main thread
        start_monitor()
        
    except KeyboardInterrupt:
        print("\n🛑 System stopped by user")
    except Exception as e:
        print(f"❌ System error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()