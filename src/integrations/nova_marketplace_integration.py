#!/usr/bin/env python3
"""
🔗 Nova TON Marketplace Integration
🎯 Integration layer between Nova TON system and Telegram Marketplace

This integration provides:
- Seamless user account linking
- Shared wallet address management
- Unified balance tracking
- Cross-system transaction synchronization
- Shared notification system

Author: Nova Team
Version: 3.0
Last Updated: September 27, 2025
"""

import sqlite3
import json
import requests
import os
from datetime import datetime
from decimal import Decimal
import logging
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NovaMarketplaceIntegration:
    """
    Integration layer between Nova TON monitoring system and Telegram Marketplace.
    
    Provides seamless integration of user accounts, wallet management,
    and transaction synchronization between both systems.
    """
    
    def __init__(self, nova_db_path="./data/nova_monitor.db", marketplace_db_path="./data/TelegramMarketplace.db"):
        """Initialize integration with both database paths."""
        self.nova_db_path = nova_db_path
        self.marketplace_db_path = marketplace_db_path
        
        logger.info("🔗 Nova Marketplace Integration initialized")
    
    def get_nova_db(self):
        """Get Nova database connection."""
        if not os.path.exists(self.nova_db_path):
            logger.warning(f"Nova database not found: {self.nova_db_path}")
            return None
        
        conn = sqlite3.connect(self.nova_db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_marketplace_db(self):
        """Get Marketplace database connection."""
        if not os.path.exists(self.marketplace_db_path):
            logger.warning(f"Marketplace database not found: {self.marketplace_db_path}")
            return None
        
        conn = sqlite3.connect(self.marketplace_db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn
    
    def sync_user_accounts(self):
        """Synchronize user accounts between Nova and Marketplace systems."""
        try:
            logger.info("👥 Synchronizing user accounts between systems")
            
            nova_conn = self.get_nova_db()
            marketplace_conn = self.get_marketplace_db()
            
            if not nova_conn or not marketplace_conn:
                logger.error("❌ Cannot connect to both databases")
                return False
            
            nova_cursor = nova_conn.cursor()
            marketplace_cursor = marketplace_conn.cursor()
            
            # Get Nova users (assuming Nova has a users table)
            try:
                nova_cursor.execute("SELECT * FROM users")
                nova_users = [dict(row) for row in nova_cursor.fetchall()]
            except sqlite3.OperationalError:
                logger.warning("⚠️ Nova users table not found, creating user mapping")
                nova_users = []
            
            # Get Marketplace users
            marketplace_cursor.execute("SELECT * FROM users")
            marketplace_users = [dict(row) for row in marketplace_cursor.fetchall()]
            
            sync_count = 0
            
            # Sync Nova users to Marketplace
            for nova_user in nova_users:
                # Check if user already exists in marketplace
                marketplace_cursor.execute(
                    "SELECT id FROM users WHERE main_wallet_address = ?",
                    (nova_user.get('wallet_address', nova_user.get('main_wallet_address')),)
                )
                
                existing_user = marketplace_cursor.fetchone()
                
                if not existing_user:
                    # Create marketplace user from Nova user
                    marketplace_cursor.execute("""
                        INSERT INTO users (
                            telegram_id, username, full_name, main_wallet_address, 
                            user_type, verification_status, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        nova_user.get('telegram_id', f"nova_user_{nova_user['id']}"),
                        nova_user.get('username', f"nova_user_{nova_user['id']}"),
                        nova_user.get('full_name', 'Nova User'),
                        nova_user.get('wallet_address', nova_user.get('main_wallet_address')),
                        'buyer',  # Default type
                        'verified' if nova_user.get('verified', False) else 'unverified',
                        nova_user.get('created_at', datetime.now().isoformat())
                    ))
                    sync_count += 1
            
            marketplace_conn.commit()
            
            nova_conn.close()
            marketplace_conn.close()
            
            logger.info(f"✅ Synchronized {sync_count} user accounts")
            return True
            
        except Exception as e:
            logger.error(f"❌ User account sync error: {e}")
            return False
    
    def sync_wallet_addresses(self):
        """Synchronize wallet addresses and create address variants."""
        try:
            logger.info("💳 Synchronizing wallet addresses with variants")
            
            marketplace_conn = self.get_marketplace_db()
            if not marketplace_conn:
                return False
            
            cursor = marketplace_conn.cursor()
            
            # Import address normalizer from existing Nova system
            try:
                import sys
                sys.path.append('./utils')
                from address_normalizer import get_mainnet_variants
                
                # Get all users without address variants
                cursor.execute("""
                    SELECT id, main_wallet_address FROM users 
                    WHERE variant_address_1 IS NULL AND main_wallet_address IS NOT NULL
                """)
                
                users_to_update = cursor.fetchall()
                
                for user in users_to_update:
                    try:
                        # Get all address variants
                        variants = get_mainnet_variants(user['main_wallet_address'])
                        
                        # Update user with variants
                        cursor.execute("""
                            UPDATE users SET 
                                variant_address_1 = ?, variant_address_2 = ?,
                                variant_address_3 = ?, variant_address_4 = ?
                            WHERE id = ?
                        """, (
                            variants.get('bounceable_base64'),
                            variants.get('non_bounceable_base64'),
                            variants.get('bounceable_base64url'),
                            variants.get('non_bounceable_base64url'),
                            user['id']
                        ))
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Could not generate variants for user {user['id']}: {e}")
                
                marketplace_conn.commit()
                marketplace_conn.close()
                
                logger.info(f"✅ Updated address variants for {len(users_to_update)} users")
                return True
                
            except ImportError:
                logger.warning("⚠️ Address normalizer not found, skipping variant generation")
                marketplace_conn.close()
                return False
            
        except Exception as e:
            logger.error(f"❌ Wallet address sync error: {e}")
            return False
    
    def sync_transactions(self):
        """Synchronize transactions between Nova and Marketplace systems."""
        try:
            logger.info("💰 Synchronizing transactions between systems")
            
            nova_conn = self.get_nova_db()
            marketplace_conn = self.get_marketplace_db()
            
            if not nova_conn or not marketplace_conn:
                return False
            
            nova_cursor = nova_conn.cursor()
            marketplace_cursor = marketplace_conn.cursor()
            
            # Get Nova transactions that might be marketplace-related
            try:
                nova_cursor.execute("""
                    SELECT * FROM transactions 
                    WHERE memo LIKE '%marketplace%' OR memo LIKE '%channel%'
                    ORDER BY created_at DESC LIMIT 100
                """)
                nova_transactions = [dict(row) for row in nova_cursor.fetchall()]
            except sqlite3.OperationalError:
                logger.warning("⚠️ Nova transactions table structure unknown")
                nova_transactions = []
            
            sync_count = 0
            
            for nova_tx in nova_transactions:
                # Check if transaction already exists in marketplace
                marketplace_cursor.execute(
                    "SELECT id FROM transactions WHERE transaction_hash = ?",
                    (nova_tx.get('hash', nova_tx.get('transaction_hash')),)
                )
                
                existing_tx = marketplace_cursor.fetchone()
                
                if not existing_tx and nova_tx.get('amount', 0) > 0:
                    # Find corresponding users
                    marketplace_cursor.execute(
                        "SELECT id FROM users WHERE main_wallet_address = ? OR variant_address_1 = ? OR variant_address_2 = ?",
                        (nova_tx.get('from_address'), nova_tx.get('from_address'), nova_tx.get('from_address'))
                    )
                    from_user = marketplace_cursor.fetchone()
                    
                    marketplace_cursor.execute(
                        "SELECT id FROM users WHERE main_wallet_address = ? OR variant_address_1 = ? OR variant_address_2 = ?",
                        (nova_tx.get('to_address'), nova_tx.get('to_address'), nova_tx.get('to_address'))
                    )
                    to_user = marketplace_cursor.fetchone()
                    
                    if from_user and to_user:
                        # Create marketplace transaction
                        marketplace_cursor.execute("""
                            INSERT INTO transactions (
                                transaction_hash, buyer_id, seller_id, transaction_type,
                                status, amount, from_address, to_address, memo,
                                created_at, blockchain_timestamp
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            nova_tx.get('hash', nova_tx.get('transaction_hash')),
                            from_user['id'], to_user['id'], 'deposit',
                            'completed', nova_tx.get('amount'),
                            nova_tx.get('from_address'), nova_tx.get('to_address'),
                            nova_tx.get('memo', 'Synced from Nova'),
                            nova_tx.get('created_at', datetime.now().isoformat()),
                            nova_tx.get('timestamp', nova_tx.get('blockchain_timestamp'))
                        ))
                        sync_count += 1
            
            marketplace_conn.commit()
            
            nova_conn.close()
            marketplace_conn.close()
            
            logger.info(f"✅ Synchronized {sync_count} transactions")
            return True
            
        except Exception as e:
            logger.error(f"❌ Transaction sync error: {e}")
            return False
    
    def create_unified_balance_view(self):
        """Create unified balance view combining Nova and Marketplace data."""
        try:
            logger.info("📊 Creating unified balance view")
            
            marketplace_conn = self.get_marketplace_db()
            if not marketplace_conn:
                return False
            
            cursor = marketplace_conn.cursor()
            
            # Create view that combines marketplace and Nova balances
            cursor.execute("""
                CREATE VIEW IF NOT EXISTS unified_user_balances AS
                SELECT 
                    u.id as user_id,
                    u.telegram_id,
                    u.username,
                    u.main_wallet_address,
                    
                    -- Marketplace transaction totals
                    COALESCE(SUM(CASE 
                        WHEN t.transaction_type = 'channel_purchase' AND t.buyer_id = u.id 
                        THEN -t.amount 
                        WHEN t.transaction_type = 'channel_purchase' AND t.seller_id = u.id 
                        THEN t.amount 
                        ELSE 0 
                    END), 0) as marketplace_balance,
                    
                    -- Transaction counts
                    COUNT(CASE WHEN t.buyer_id = u.id THEN 1 END) as purchases_count,
                    COUNT(CASE WHEN t.seller_id = u.id THEN 1 END) as sales_count,
                    
                    -- Channel statistics
                    COUNT(DISTINCT c.id) as channels_listed,
                    COUNT(CASE WHEN c.status = 'sold' THEN 1 END) as channels_sold,
                    
                    -- Ratings
                    u.seller_rating,
                    u.buyer_rating,
                    
                    -- Status
                    u.verification_status,
                    u.is_active
                    
                FROM users u
                LEFT JOIN transactions t ON (u.id = t.buyer_id OR u.id = t.seller_id)
                LEFT JOIN channels c ON u.id = c.seller_id
                GROUP BY u.id
            """)
            
            marketplace_conn.commit()
            marketplace_conn.close()
            
            logger.info("✅ Unified balance view created")
            return True
            
        except Exception as e:
            logger.error(f"❌ Unified balance view creation error: {e}")
            return False
    
    def sync_notifications(self):
        """Synchronize notifications between systems."""
        try:
            logger.info("🔔 Setting up notification synchronization")
            
            marketplace_conn = self.get_marketplace_db()
            if not marketplace_conn:
                return False
            
            cursor = marketplace_conn.cursor()
            
            # Create notifications for recent marketplace activities
            cursor.execute("""
                INSERT OR IGNORE INTO notifications (user_id, type, title, message, channel_id, transaction_id)
                SELECT 
                    t.buyer_id,
                    'payment_received',
                    'Channel Purchase Completed',
                    'Your channel purchase has been completed successfully',
                    t.channel_id,
                    t.id
                FROM transactions t
                WHERE t.status = 'completed' 
                AND t.transaction_type = 'channel_purchase'
                AND t.completed_at > datetime('now', '-7 days')
            """)
            
            cursor.execute("""
                INSERT OR IGNORE INTO notifications (user_id, type, title, message, channel_id, transaction_id)
                SELECT 
                    t.seller_id,
                    'channel_sold',
                    'Channel Sold Successfully',
                    'Your channel has been sold and payment received',
                    t.channel_id,
                    t.id
                FROM transactions t
                WHERE t.status = 'completed' 
                AND t.transaction_type = 'channel_purchase'
                AND t.completed_at > datetime('now', '-7 days')
            """)
            
            marketplace_conn.commit()
            marketplace_conn.close()
            
            logger.info("✅ Notification synchronization completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Notification sync error: {e}")
            return False
    
    def create_integration_api_endpoints(self):
        """Create additional API endpoints for Nova integration."""
        integration_endpoints = """
        
        # Additional API endpoints for Nova integration
        
        @app.route('/api/nova/user/<wallet_address>', methods=['GET'])
        def get_user_by_wallet(wallet_address):
            '''Get marketplace user by Nova wallet address.'''
            try:
                conn = marketplace.get_db()
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM users 
                    WHERE main_wallet_address = ? 
                    OR variant_address_1 = ? 
                    OR variant_address_2 = ? 
                    OR variant_address_3 = ? 
                    OR variant_address_4 = ?
                ''', (wallet_address, wallet_address, wallet_address, wallet_address, wallet_address))
                
                user = cursor.fetchone()
                conn.close()
                
                if user:
                    return jsonify({'success': True, 'user': dict(user)})
                else:
                    return jsonify({'success': False, 'error': 'User not found'}), 404
                    
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @app.route('/api/nova/balance/<wallet_address>', methods=['GET'])
        def get_unified_balance(wallet_address):
            '''Get unified balance including marketplace transactions.'''
            try:
                conn = marketplace.get_db()
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM unified_user_balances 
                    WHERE main_wallet_address = ?
                ''', (wallet_address,))
                
                balance_info = cursor.fetchone()
                conn.close()
                
                if balance_info:
                    return jsonify({'success': True, 'balance': dict(balance_info)})
                else:
                    return jsonify({'success': False, 'error': 'Balance not found'}), 404
                    
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @app.route('/api/nova/sync', methods=['POST'])
        @require_auth
        def trigger_sync():
            '''Manually trigger synchronization between systems.'''
            try:
                integration = NovaMarketplaceIntegration()
                
                results = {
                    'users_synced': integration.sync_user_accounts(),
                    'addresses_synced': integration.sync_wallet_addresses(),
                    'transactions_synced': integration.sync_transactions(),
                    'notifications_synced': integration.sync_notifications()
                }
                
                return jsonify({'success': True, 'sync_results': results})
                
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        """
        
        # Write integration endpoints to a separate file
        with open('nova_integration_endpoints.py', 'w') as f:
            f.write(integration_endpoints)
        
        logger.info("✅ Integration API endpoints created")
        return True
    
    def run_complete_integration(self):
        """Run complete integration process."""
        logger.info("🚀 Starting complete Nova Marketplace integration")
        
        integration_steps = [
            ("👥 User Account Sync", self.sync_user_accounts),
            ("💳 Wallet Address Sync", self.sync_wallet_addresses),
            ("💰 Transaction Sync", self.sync_transactions),
            ("📊 Unified Balance View", self.create_unified_balance_view),
            ("🔔 Notification Sync", self.sync_notifications),
            ("🔌 API Endpoints", self.create_integration_api_endpoints)
        ]
        
        results = {}
        
        for step_name, step_function in integration_steps:
            try:
                logger.info(f"Running: {step_name}")
                result = step_function()
                results[step_name] = result
                
                if result:
                    logger.info(f"✅ {step_name} completed successfully")
                else:
                    logger.warning(f"⚠️ {step_name} completed with warnings")
                    
            except Exception as e:
                logger.error(f"❌ {step_name} failed: {e}")
                results[step_name] = False
        
        # Summary
        successful_steps = sum(1 for result in results.values() if result)
        total_steps = len(results)
        
        logger.info(f"🎯 Integration Summary: {successful_steps}/{total_steps} steps completed successfully")
        
        if successful_steps == total_steps:
            logger.info("🎉 Complete Nova Marketplace integration successful!")
        elif successful_steps > total_steps // 2:
            logger.info("⚠️ Partial integration completed - some features may be limited")
        else:
            logger.error("❌ Integration failed - manual intervention required")
        
        return results


def main():
    """Main integration function."""
    print("🔗 Nova TON Marketplace Integration")
    print("=" * 50)
    
    # Initialize integration
    integration = NovaMarketplaceIntegration()
    
    # Run complete integration
    results = integration.run_complete_integration()
    
    # Print results
    print("\n📊 Integration Results:")
    for step, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"  {step}: {status}")
    
    print("\n🚀 Integration completed!")
    print("Next steps:")
    print("1. Test unified API endpoints")
    print("2. Update Nova frontend to include marketplace features")
    print("3. Configure notification delivery")
    print("4. Set up monitoring for both systems")


if __name__ == "__main__":
    main()
