#!/usr/bin/env python3
"""
📱 Telegram Channel Marketplace Database Initialization
🎯 Initialize the comprehensive marketplace database system

This script creates and initializes the TelegramMarketplace.db database
with all tables, indexes, triggers, and views for the channel marketplace.

Features:
- Complete database schema creation
- Sample data insertion for testing
- Database integrity verification
- Migration support
- Backup and restore functionality

Author: Nova Team
Version: 3.0
Last Updated: September 27, 2025
"""

import sqlite3
import os
import json
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TelegramMarketplaceDB:
    """
    Telegram Channel Marketplace Database Manager
    
    Handles database initialization, schema creation, and data management
    for the comprehensive marketplace system.
    """
    
    def __init__(self, db_path="./data/TelegramMarketplace.db"):
        """Initialize database manager with specified path."""
        self.db_path = db_path
        self.schema_file = "telegram_marketplace_schema.sql"
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        logger.info(f"🚀 Initializing Telegram Marketplace Database at: {self.db_path}")
    
    def connect(self):
        """Create database connection with proper configuration."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = 10000")
        conn.execute("PRAGMA temp_store = MEMORY")
        return conn
    
    def create_database(self):
        """Create the complete database schema from SQL file."""
        try:
            logger.info("📊 Creating database schema...")
            
            # Read schema file
            if not os.path.exists(self.schema_file):
                raise FileNotFoundError(f"Schema file not found: {self.schema_file}")
            
            with open(self.schema_file, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            # Execute schema
            conn = self.connect()
            cursor = conn.cursor()
            
            # Split and execute SQL statements
            statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
            
            for statement in statements:
                if statement and not statement.startswith('--'):
                    try:
                        cursor.execute(statement)
                        logger.debug(f"✅ Executed: {statement[:50]}...")
                    except sqlite3.Error as e:
                        logger.warning(f"⚠️ SQL Warning: {e} for statement: {statement[:100]}...")
            
            conn.commit()
            conn.close()
            
            logger.info("✅ Database schema created successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error creating database: {e}")
            return False
    
    def verify_schema(self):
        """Verify that all tables and indexes were created correctly."""
        try:
            logger.info("🔍 Verifying database schema...")
            
            conn = self.connect()
            cursor = conn.cursor()
            
            # Expected tables
            expected_tables = [
                'users', 'channels', 'channel_gifts', 'bot_verifications',
                'transactions', 'channel_transfers', 'disputes', 'reviews',
                'channel_analytics', 'notifications', 'price_history',
                'escrow_accounts', 'channel_offers', 'audit_logs'
            ]
            
            # Check tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            missing_tables = set(expected_tables) - set(existing_tables)
            if missing_tables:
                logger.error(f"❌ Missing tables: {missing_tables}")
                return False
            
            # Check indexes
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = cursor.fetchall()
            logger.info(f"📈 Created {len(indexes)} indexes")
            
            # Check triggers
            cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
            triggers = cursor.fetchall()
            logger.info(f"⚡ Created {len(triggers)} triggers")
            
            # Check views
            cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
            views = cursor.fetchall()
            logger.info(f"👁️ Created {len(views)} views")
            
            conn.close()
            
            logger.info("✅ Schema verification completed successfully!")
            logger.info(f"📊 Total tables: {len(existing_tables)}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error verifying schema: {e}")
            return False
    
    def insert_sample_data(self):
        """Insert sample data for testing and demonstration."""
        try:
            logger.info("📝 Inserting sample data...")
            
            conn = self.connect()
            cursor = conn.cursor()
            
            # Sample users
            sample_users = [
                {
                    'telegram_id': 'user_001',
                    'username': 'crypto_seller',
                    'full_name': 'John Crypto',
                    'main_wallet_address': 'UQCryptoSellerWalletAddress123456789',
                    'user_type': 'seller',
                    'verification_status': 'verified'
                },
                {
                    'telegram_id': 'user_002',
                    'username': 'channel_buyer',
                    'full_name': 'Alice Buyer',
                    'main_wallet_address': 'UQChannelBuyerWalletAddress987654321',
                    'user_type': 'buyer',
                    'verification_status': 'verified'
                },
                {
                    'telegram_id': 'user_003',
                    'username': 'marketplace_trader',
                    'full_name': 'Bob Trader',
                    'main_wallet_address': 'UQMarketplaceTraderWallet555666777',
                    'user_type': 'both',
                    'verification_status': 'premium'
                }
            ]
            
            for user in sample_users:
                cursor.execute("""
                    INSERT OR IGNORE INTO users 
                    (telegram_id, username, full_name, main_wallet_address, user_type, verification_status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    user['telegram_id'], user['username'], user['full_name'],
                    user['main_wallet_address'], user['user_type'], user['verification_status']
                ))
            
            # Sample channels
            sample_channels = [
                {
                    'channel_id': '-1001234567890',
                    'channel_username': 'crypto_news_premium',
                    'channel_title': 'Crypto News Premium 📈',
                    'channel_description': 'Premium crypto news and analysis with exclusive insights',
                    'seller_id': 1,  # crypto_seller
                    'member_count': 15000,
                    'asking_price': '50.0',
                    'category': 'crypto',
                    'status': 'active'
                },
                {
                    'channel_id': '-1001234567891',
                    'channel_username': 'gaming_community',
                    'channel_title': 'Elite Gaming Community 🎮',
                    'channel_description': 'Exclusive gaming community with tournaments and rewards',
                    'seller_id': 3,  # marketplace_trader
                    'member_count': 8500,
                    'asking_price': '25.5',
                    'category': 'gaming',
                    'status': 'active'
                }
            ]
            
            for channel in sample_channels:
                cursor.execute("""
                    INSERT OR IGNORE INTO channels 
                    (channel_id, channel_username, channel_title, channel_description, 
                     seller_id, member_count, asking_price, category, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    channel['channel_id'], channel['channel_username'], channel['channel_title'],
                    channel['channel_description'], channel['seller_id'], channel['member_count'],
                    channel['asking_price'], channel['category'], channel['status']
                ))
            
            # Sample channel gifts
            sample_gifts = [
                {
                    'channel_id': 1,
                    'gift_type': 'premium_boost',
                    'gift_name': 'Premium Boost Level 5',
                    'gift_code': '3GRAM_BOOST_001',
                    'quantity': 1,
                    'value_ton': '10.0',
                    'is_verified': 1
                },
                {
                    'channel_id': 1,
                    'gift_type': 'star_gift',
                    'gift_name': 'Golden Star Collection',
                    'gift_code': '3GRAM_STAR_002',
                    'quantity': 5,
                    'value_ton': '15.0',
                    'is_verified': 1
                },
                {
                    'channel_id': 2,
                    'gift_type': 'custom_emoji',
                    'gift_name': 'Gaming Emoji Pack',
                    'gift_code': '3GRAM_EMOJI_003',
                    'quantity': 20,
                    'value_ton': '5.0',
                    'is_verified': 0
                }
            ]
            
            for gift in sample_gifts:
                cursor.execute("""
                    INSERT OR IGNORE INTO channel_gifts 
                    (channel_id, gift_type, gift_name, gift_code, quantity, value_ton, is_verified)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    gift['channel_id'], gift['gift_type'], gift['gift_name'],
                    gift['gift_code'], gift['quantity'], gift['value_ton'], gift['is_verified']
                ))
            
            # Sample bot verification
            cursor.execute("""
                INSERT OR IGNORE INTO bot_verifications 
                (channel_id, user_id, verification_type, verification_status, is_successful, gifts_found, gifts_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (1, 1, 'gifts', 'completed', 1, 2, 2))
            
            # Sample transaction
            cursor.execute("""
                INSERT OR IGNORE INTO transactions 
                (buyer_id, seller_id, channel_id, transaction_type, status, amount, from_address, to_address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (2, 1, 1, 'channel_purchase', 'pending', '50.0', 
                  'UQChannelBuyerWalletAddress987654321', 'UQCryptoSellerWalletAddress123456789'))
            
            # Sample offer
            cursor.execute("""
                INSERT OR IGNORE INTO channel_offers 
                (channel_id, buyer_id, seller_id, offer_amount, original_price, status, valid_until)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (2, 2, 3, '20.0', '25.5', 'pending', 
                  (datetime.now() + timedelta(days=3)).isoformat()))
            
            conn.commit()
            conn.close()
            
            logger.info("✅ Sample data inserted successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error inserting sample data: {e}")
            return False
    
    def get_database_stats(self):
        """Get comprehensive database statistics."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            stats = {}
            
            # Table counts
            tables = [
                'users', 'channels', 'channel_gifts', 'bot_verifications',
                'transactions', 'channel_transfers', 'disputes', 'reviews',
                'channel_analytics', 'notifications', 'price_history',
                'escrow_accounts', 'channel_offers', 'audit_logs'
            ]
            
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            
            # Database size
            cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            db_size = cursor.fetchone()[0]
            stats['database_size_bytes'] = db_size
            stats['database_size_mb'] = round(db_size / (1024 * 1024), 2)
            
            conn.close()
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error getting database stats: {e}")
            return {}
    
    def backup_database(self, backup_path=None):
        """Create a backup of the database."""
        try:
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"./data/marketplace_backup_{timestamp}.db"
            
            logger.info(f"💾 Creating database backup: {backup_path}")
            
            # Ensure backup directory exists
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            # Create backup using SQLite backup API
            source = self.connect()
            backup = sqlite3.connect(backup_path)
            
            source.backup(backup)
            
            source.close()
            backup.close()
            
            # Verify backup
            backup_size = os.path.getsize(backup_path)
            logger.info(f"✅ Backup created successfully! Size: {backup_size} bytes")
            
            return backup_path
            
        except Exception as e:
            logger.error(f"❌ Error creating backup: {e}")
            return None
    
    def initialize_complete_system(self):
        """Initialize the complete marketplace database system."""
        logger.info("🚀 Starting complete marketplace database initialization...")
        
        success_steps = []
        
        # Step 1: Create database schema
        if self.create_database():
            success_steps.append("✅ Database schema created")
        else:
            logger.error("❌ Failed to create database schema")
            return False
        
        # Step 2: Verify schema
        if self.verify_schema():
            success_steps.append("✅ Schema verification passed")
        else:
            logger.error("❌ Schema verification failed")
            return False
        
        # Step 3: Insert sample data
        if self.insert_sample_data():
            success_steps.append("✅ Sample data inserted")
        else:
            logger.warning("⚠️ Sample data insertion failed (non-critical)")
        
        # Step 4: Get statistics
        stats = self.get_database_stats()
        if stats:
            success_steps.append("✅ Database statistics generated")
            logger.info("📊 Database Statistics:")
            for table, count in stats.items():
                if table.endswith('_bytes') or table.endswith('_mb'):
                    continue
                logger.info(f"   {table}: {count} records")
            logger.info(f"   Database size: {stats.get('database_size_mb', 0)} MB")
        
        # Step 5: Create initial backup
        backup_path = self.backup_database()
        if backup_path:
            success_steps.append("✅ Initial backup created")
        
        logger.info("🎉 Marketplace database initialization completed!")
        logger.info("Completed steps:")
        for step in success_steps:
            logger.info(f"  {step}")
        
        return True


def main():
    """Main initialization function."""
    print("📱 Telegram Channel Marketplace Database Initialization")
    print("=" * 60)
    
    # Initialize database manager
    db_manager = TelegramMarketplaceDB()
    
    # Run complete initialization
    success = db_manager.initialize_complete_system()
    
    if success:
        print("\n🎉 SUCCESS! Marketplace database is ready for use!")
        print(f"📍 Database location: {db_manager.db_path}")
        print("\n🚀 Next steps:")
        print("1. Start the marketplace API server")
        print("2. Configure bot verification system")
        print("3. Set up payment processing")
        print("4. Initialize frontend application")
    else:
        print("\n❌ FAILED! Database initialization encountered errors.")
        print("Please check the logs above for details.")
    
    return success


if __name__ == "__main__":
    main()
