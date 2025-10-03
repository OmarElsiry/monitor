#!/usr/bin/env python3
"""
Nova TON Monitor - Production Entry Point
Main entry point for the TON blockchain monitoring system
"""

import sys
import os
from pathlib import Path

# Add monitor root and src to path for imports
monitor_root = Path(__file__).parent
sys.path.insert(0, str(monitor_root))
sys.path.insert(0, str(monitor_root / 'src'))

def main():
    """Main entry point for Nova TON Monitor."""
    print("=" * 60)
    print(" NOVA TON MONITOR - PRODUCTION")
    print("=" * 60)
    print("Starting blockchain monitoring system...")
    try:
        # Import and run the production monitor
        from core.production_monitor import main as production_main
        production_main()
    except ImportError as e:
        print(f"❌ Failed to import production monitor: {e}")
        print("🔄 Falling back to working monitor...")
        try:
            from core.monitor import main as monitor_main
            monitor_main()
        except ImportError as e2:
            print(f"❌ Failed to import working monitor: {e2}")
            print("💡 Please check your Python environment and dependencies")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Monitor stopped by user")
    except Exception as e:
        print(f"❌ Monitor error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()