#!/usr/bin/env python3
"""
Nova API Server - Production Entry Point
Main entry point for the Nova API server
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def main():
    """Main entry point for Nova API Server."""
    print("=" * 60)
    print("🌐 NOVA API SERVER - PRODUCTION")
    print("=" * 60)
    print("Starting API server...")
    
    try:
        # Import and run the API server
        from api.marketplace_api_complete import app
        print("✅ API server loaded successfully")
        print("🌐 Server running on http://0.0.0.0:5001")
        app.run(host='0.0.0.0', port=5001, debug=False)
    except ImportError as e:
        print(f"❌ Failed to import API server: {e}")
        print("💡 Please check your Python environment and dependencies")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 API server stopped by user")
    except Exception as e:
        print(f"❌ API server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
