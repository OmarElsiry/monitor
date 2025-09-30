#!/usr/bin/env python3
"""
🧹 Production Cleanup Script
Remove all non-production files and organize for production deployment
"""

import os
import shutil
from pathlib import Path

def cleanup_monitor_directory():
    """Clean up monitor directory for production."""
    
    # Files to remove (debug, test, development files)
    files_to_remove = [
        # Debug files
        "api_request_logger.py",
        "comprehensive_debug.py", 
        "frontend_debug_test.py",
        "realtime_user_monitor.py",
        "simple_debug_test.py",
        "wallet_connection_debug.py",
        
        # Test files
        "test_cors_fix.py",
        "test_instant_creation.py", 
        "test_marketplace_system.py",
        "test_user_creation.py",
        "test_user_creation_debug.py",
        
        # Quick/manual tools
        "quick_user_test.py",
        "manual_user_test.py",
        
        # Fix/setup scripts (move to tools)
        "fix_database.py",
        "fix_missing_deposits.py", 
        "reset_database.py",
        "reset_logical_time.py",
        "setup_marketplace.py",
        "check_database_users.py",
        "cleanup_production.py",
        
        # Development monitors
        "ultra_simple_monitor.py",
        
        # Old README files
        "README.md",
        "TELEGRAM_MARKETPLACE_README.md"
    ]
    
    # Create tools directory for utilities
    tools_dir = Path("tools")
    tools_dir.mkdir(exist_ok=True)
    
    # Move utility files to tools
    utility_files = [
        "fix_database.py",
        "fix_missing_deposits.py", 
        "reset_database.py",
        "reset_logical_time.py",
        "check_database_users.py"
    ]
    
    for file in utility_files:
        if os.path.exists(file):
            try:
                shutil.move(file, tools_dir / file)
                print(f"✅ Moved {file} to tools/")
            except:
                pass
    
    # Remove debug/test files
    removed_count = 0
    for file in files_to_remove:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"🗑️ Removed {file}")
                removed_count += 1
            except Exception as e:
                print(f"❌ Failed to remove {file}: {e}")
    
    print(f"\n✅ Cleanup complete! Removed {removed_count} non-production files")
    
    # Show remaining production files
    print("\n📁 Production files remaining:")
    production_files = [
        "production_monitor.py",
        "working_monitor.py", 
        "api/production_server.py",
        "config/production.py",
        "database/production_db.py",
        "utils/production_logger.py",
        "utils/address_normalizer.py",
        "Dockerfile",
        "docker-compose.yml",
        "requirements.txt",
        ".env.production.template",
        "PRODUCTION_README.md"
    ]
    
    for file in production_files:
        if os.path.exists(file):
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} (missing)")

if __name__ == "__main__":
    print("🧹 Starting Production Cleanup...")
    cleanup_monitor_directory()
    print("\n🎉 Production cleanup complete!")
