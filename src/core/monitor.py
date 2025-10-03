#!/usr/bin/env python3
"""
TON Monitor - Working Version
Simple, working monitor that combines the best features without complex imports
"""
import asyncio
import sqlite3
import time
import threading
from datetime import datetime
from pathlib import Path
import sys
from flask import Flask, jsonify, request
from flask_cors import CORS
import logging

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import address normalizer
try:
    sys.path.append('./utils')
    from address_normalizer import get_mainnet_variants
    logger.info("✅ Address normalizer imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import address normalizer: {e}")
    # Fallback function if import fails
    def get_mainnet_variants(address):
        return [address]

class WorkingTONMonitor:
    """Simple, working TON monitor that actually works"""

    WEBSITE_WALLET = "UQDrY5iulWs_MyWTP9JSGedWBzlbeRmhCBoqsSaNiSLOs315"

    def __init__(self):
        self.db_path = "./data/NovaTonMonitor.db"
        self.running = False
        self.app = None

    def init_database(self):
        """Initialize database with enhanced schema"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('PRAGMA foreign_keys = ON')

                # Simple users table with 5 address columns
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_id TEXT UNIQUE NOT NULL,
                        main_wallet_address TEXT UNIQUE NOT NULL,
                        variant_address_1 TEXT,
                        variant_address_2 TEXT,
                        variant_address_3 TEXT,
                        variant_address_4 TEXT,
                        username TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Enhanced user balances table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS user_balances (
                        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                        current_balance DECIMAL(20,9) DEFAULT 0.000000000,
                        total_deposited DECIMAL(20,9) DEFAULT 0.000000000,
                        total_withdrawn DECIMAL(20,9) DEFAULT 0.000000000,
                        deposit_count INTEGER DEFAULT 0,
                        withdrawal_count INTEGER DEFAULT 0,
                        last_deposit_at DATETIME,
                        last_withdrawal_at DATETIME,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Enhanced transactions table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        hash TEXT UNIQUE NOT NULL,
                        from_address TEXT NOT NULL,
                        to_address TEXT NOT NULL,
                        amount DECIMAL(20,9) NOT NULL,
                        fee DECIMAL(20,9) DEFAULT 0.000000000,
                        status TEXT DEFAULT 'confirmed',
                        transaction_type TEXT DEFAULT 'deposit',
                        block_number INTEGER,
                        logical_time INTEGER,
                        utime INTEGER,
                        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        memo TEXT,
                        comment TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        processed_at DATETIME,
                        blockchain_timestamp INTEGER
                    )
                ''')

                # Create indexes for the 5 address columns
                variant_indexes = [
                    'CREATE INDEX IF NOT EXISTS idx_users_main_wallet ON users(main_wallet_address)',
                    'CREATE INDEX IF NOT EXISTS idx_users_variant_1 ON users(variant_address_1)',
                    'CREATE INDEX IF NOT EXISTS idx_users_variant_2 ON users(variant_address_2)',
                    'CREATE INDEX IF NOT EXISTS idx_users_variant_3 ON users(variant_address_3)',
                    'CREATE INDEX IF NOT EXISTS idx_users_variant_4 ON users(variant_address_4)'
                ]
                
                for idx_sql in variant_indexes:
                    conn.execute(idx_sql)

                # System status table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS system_status (
                        id INTEGER PRIMARY KEY DEFAULT 1,
                        last_block_number INTEGER DEFAULT 0,
                        last_logical_time INTEGER DEFAULT 0,
                        last_check_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        is_monitoring BOOLEAN DEFAULT 0,
                        api_status TEXT DEFAULT 'unknown',
                        db_status TEXT DEFAULT 'healthy',
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Insert default system status if not exists
                conn.execute('''
                    INSERT OR IGNORE INTO system_status (id) VALUES (1)
                ''')

                # Create indexes for better performance
                indexes = [
                    'CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(telegram_id)',
                    'CREATE INDEX IF NOT EXISTS idx_transactions_hash ON transactions(hash)',
                    'CREATE INDEX IF NOT EXISTS idx_transactions_address ON transactions(to_address, from_address)',
                    'CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id)',
                    'CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status)',
                    'CREATE INDEX IF NOT EXISTS idx_transactions_time ON transactions(created_at)'
                ]

                for idx_sql in indexes:
                    conn.execute(idx_sql)

                logger.info("✅ Enhanced database initialized successfully")

        except Exception as e:
            logger.error(f"❌ Database initialization error: {e}")

    def get_balance(self, telegram_id):
        """Get user balance by telegram ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                # Get user
                cursor = conn.execute(
                    "SELECT * FROM users WHERE telegram_id = ?",
                    (telegram_id,)
                )
                user = cursor.fetchone()

                if not user:
                    return {'success': False, 'error': 'User not found', 'balance': 0}

                # Get balance
                cursor = conn.execute(
                    "SELECT * FROM user_balances WHERE user_id = ?",
                    (user['id'],)
                )
                balance_record = cursor.fetchone()

                if balance_record:
                    return {
                        'success': True,
                        'user_id': user['id'],
                        'telegram_id': telegram_id,
                        'balance': float(balance_record['current_balance']),
                        'total_deposited': float(balance_record['total_deposited']),
                        'deposit_count': balance_record['deposit_count'],
                        'wallet_address': user['main_wallet_address']
                    }
                else:
                    return {
                        'success': True,
                        'user_id': user['id'],
                        'telegram_id': telegram_id,
                        'balance': 0.0,
                        'total_deposited': 0.0,
                        'deposit_count': 0,
                        'wallet_address': user['main_wallet_address']
                    }

        except Exception as e:
            return {'success': False, 'error': str(e), 'balance': 0}

    def get_balance_by_wallet(self, wallet_address):
        """Get user balance by wallet address (checks all 5 address columns)"""
        logger.info(f"🔍 Looking up wallet: {wallet_address}")
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                # Search for user by any of the 5 address columns
                cursor = conn.execute("""
                    SELECT * FROM users 
                    WHERE main_wallet_address = ? 
                       OR variant_address_1 = ?
                       OR variant_address_2 = ?
                       OR variant_address_3 = ?
                       OR variant_address_4 = ?
                """, (wallet_address, wallet_address, wallet_address, wallet_address, wallet_address))
                
                user = cursor.fetchone()

                if not user:
                    logger.warning(f"❌ Wallet address not found: {wallet_address}")
                    return {'success': False, 'error': 'Wallet address not found', 'balance': 0}

                logger.info(f"✅ Found user {user['id']} for wallet: {wallet_address}")

                # Get balance
                cursor = conn.execute(
                    "SELECT * FROM user_balances WHERE user_id = ?",
                    (user['id'],)
                )
                balance_record = cursor.fetchone()

                if balance_record:
                    logger.info(f"💰 User {user['id']} balance: {balance_record['current_balance']} TON")
                    return {
                        'success': True,
                        'user_id': user['id'],
                        'telegram_id': user['telegram_id'],
                        'wallet_address': user['main_wallet_address'],
                        'balance': float(balance_record['current_balance']),
                        'total_deposited': float(balance_record['total_deposited']),
                        'deposit_count': balance_record['deposit_count'],
                        'variants': {
                            'main': user['main_wallet_address'],
                            'variant_1': user['variant_address_1'],
                            'variant_2': user['variant_address_2'],
                            'variant_3': user['variant_address_3'],
                            'variant_4': user['variant_address_4']
                        }
                    }
                else:
                    logger.info(f"💰 User {user['id']} has no balance record, returning 0")
                    return {
                        'success': True,
                        'user_id': user['id'],
                        'telegram_id': user['telegram_id'],
                        'wallet_address': user['main_wallet_address'],
                        'balance': 0.0,
                        'total_deposited': 0.0,
                        'deposit_count': 0,
                        'variants': {
                            'main': user['main_wallet_address'],
                            'variant_1': user['variant_address_1'],
                            'variant_2': user['variant_address_2'],
                            'variant_3': user['variant_address_3'],
                            'variant_4': user['variant_address_4']
                        }
                    }

        except Exception as e:
            logger.error(f"❌ Error getting balance for {wallet_address}: {e}")
            return {'success': False, 'error': str(e), 'balance': 0}

    def refresh_balance(self, user_id):
        """Refresh user balance with detailed debugging and transaction capture logging"""
        logger.info(f"🔄 Refreshing balance for user {user_id}")

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                # Get the actual deposit address
                actual_deposit_address = "EQDrY5iulWs_MyWTP9JSGedWBzlbeRmhCBoqsSaNiSLOsyC8"
                logger.info(f"📍 Looking for deposits to: {actual_deposit_address}")

                # Get total transactions in database
                cursor = conn.execute("SELECT COUNT(*) as total FROM transactions")
                total_tx = cursor.fetchone()['total']
                logger.info(f"📊 Total transactions in database: {total_tx}")
                
                if total_tx > 0:
                    logger.info(f"💰 TRANSACTION CAPTURE: Found {total_tx} transactions in database")
                else:
                    logger.warning(f"⚠️ TRANSACTION CAPTURE: No transactions found in database")

                # Get transactions to the actual address
                cursor = conn.execute("""
                    SELECT COUNT(*) as count, SUM(amount) as total
                    FROM transactions
                    WHERE to_address = ?
                """, (actual_deposit_address,))

                addr_result = cursor.fetchone()
                addr_count = addr_result['count'] if addr_result['count'] else 0
                addr_total = addr_result['total'] if addr_result['total'] else 0
                logger.info(f"🎯 Transactions to deposit address: {addr_count} ({addr_total} TON)")
                
                if addr_count > 0:
                    logger.info(f"✅ TRANSACTION CAPTURE: Found {addr_count} deposits totaling {addr_total} TON")
                else:
                    logger.warning(f"❌ TRANSACTION CAPTURE: No deposits found to address {actual_deposit_address}")

                # Get positive amounts only
                cursor = conn.execute("""
                    SELECT SUM(amount) as total, COUNT(*) as count
                    FROM transactions
                    WHERE to_address = ? AND amount > 0
                """, (actual_deposit_address,))

                result = cursor.fetchone()
                total_deposited = result['total'] if result['total'] else 0
                deposit_count = result['count'] if result['count'] else 0

                logger.info(f"   Database Query Result:")
                logger.info(f"      Total deposited: {total_deposited} TON")
                logger.info(f"      Deposit count: {deposit_count}")

                # Show recent transactions with detailed logging
                cursor = conn.execute("""
                    SELECT hash, from_address, to_address, amount, status, created_at
                    FROM transactions
                    WHERE to_address = ? AND amount > 0
                    ORDER BY created_at DESC
                    LIMIT 3
                """, (actual_deposit_address,))

                recent_txs = cursor.fetchall()
                logger.info(f"📋 Recent transactions ({len(recent_txs)} shown):")
                for i, tx in enumerate(recent_txs):
                    logger.info(f"   🔸 TX {i+1}: {tx['hash'][:20]}... | {tx['amount']} TON | {tx['status']}")
                    logger.info(f"      📤 From: {tx['from_address'][:20]}...")
                    logger.info(f"      📥 To: {tx['to_address'][:20]}...")
                    logger.info(f"      🕒 Time: {tx['created_at']}")
                    
                if len(recent_txs) > 0:
                    logger.info(f"🎉 TRANSACTION CAPTURE: Successfully captured and processed {len(recent_txs)} recent transactions")

                # Update user balance
                conn.execute("""
                    INSERT OR REPLACE INTO user_balances
                    (user_id, current_balance, total_deposited, deposit_count, updated_at)
                    VALUES (?, ?, ?, ?, datetime('now'))
                """, (user_id, total_deposited, total_deposited, deposit_count))

                logger.info(f"💾 Updated user {user_id} balance: {total_deposited} TON")

                # Verify the update
                cursor = conn.execute("SELECT * FROM user_balances WHERE user_id = ?", (user_id,))
                updated_balance = cursor.fetchone()
                if updated_balance:
                    logger.info(f"✅ BALANCE UPDATE: User {user_id} balance verified as {updated_balance['current_balance']} TON")
                    logger.info(f"📈 BALANCE SUMMARY: {deposit_count} deposits, {total_deposited} TON total")
                else:
                    logger.error(f"❌ BALANCE UPDATE: Failed to verify balance update for user {user_id}")

                return {
                    'success': True,
                    'balance': float(total_deposited),
                    'total_deposited': float(total_deposited),
                    'deposit_count': deposit_count,
                    'updated_at': time.time(),
                    'debug_info': {
                        'deposit_address': actual_deposit_address,
                        'query_result': f"{deposit_count} transactions, {total_deposited} TON",
                        'total_db_transactions': total_tx,
                        'address_transactions': f"{addr_count} transactions to address"
                    }
                }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"💥 BALANCE REFRESH ERROR: {error_msg}")
            logger.error(f"🔍 Error occurred while refreshing balance for user {user_id}")
            return {'success': False, 'error': error_msg}

    def create_user_with_wallet(self, wallet_address, telegram_id=None):
        """Create a user with main wallet address and 4 variants in simple 5-column table"""
        logger.info(f"👤 Creating user with wallet: {wallet_address}")
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                # Get all address variants
                variants = get_mainnet_variants(wallet_address)
                logger.info(f"📍 Generated {len(variants)} address variants")

                # Check if user already exists with any of the 5 addresses
                cursor = conn.execute("""
                    SELECT * FROM users 
                    WHERE main_wallet_address = ? 
                       OR variant_address_1 = ?
                       OR variant_address_2 = ?
                       OR variant_address_3 = ?
                       OR variant_address_4 = ?
                """, (wallet_address, wallet_address, wallet_address, wallet_address, wallet_address))
                
                existing_user = cursor.fetchone()

                if existing_user:
                    logger.info(f"✅ User already exists with ID: {existing_user['id']}")
                    return {
                        'success': True,
                        'message': 'User already exists',
                        'user_id': existing_user['id'],
                        'telegram_id': existing_user['telegram_id'],
                        'wallet_address': existing_user['main_wallet_address'],
                        'variants': {
                            'main': existing_user['main_wallet_address'],
                            'variant_1': existing_user['variant_address_1'],
                            'variant_2': existing_user['variant_address_2'],
                            'variant_3': existing_user['variant_address_3'],
                            'variant_4': existing_user['variant_address_4']
                        }
                    }

                # Prepare the 5 addresses: main + 4 variants
                main_address = wallet_address
                telegram_id = telegram_id or f"user_{main_address[:10]}"
                
                # Fill the 4 variant slots with generated variants (or duplicates if not enough)
                variant_1 = variants[0] if len(variants) > 0 else main_address
                variant_2 = variants[1] if len(variants) > 1 else main_address
                variant_3 = variants[2] if len(variants) > 2 else main_address
                variant_4 = variants[3] if len(variants) > 3 else main_address
                
                logger.info(f"💾 Storing addresses:")
                logger.info(f"   Main: {main_address}")
                logger.info(f"   Variant 1: {variant_1}")
                logger.info(f"   Variant 2: {variant_2}")
                logger.info(f"   Variant 3: {variant_3}")
                logger.info(f"   Variant 4: {variant_4}")
                
                # Create new user with 5 address columns
                conn.execute("""
                    INSERT INTO users (
                        telegram_id, 
                        main_wallet_address,
                        variant_address_1,
                        variant_address_2,
                        variant_address_3,
                        variant_address_4
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (telegram_id, main_address, variant_1, variant_2, variant_3, variant_4))

                user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                # Initialize balance
                conn.execute("""
                    INSERT INTO user_balances (user_id, current_balance, total_deposited, deposit_count)
                    VALUES (?, 0, 0, 0)
                """, (user_id,))

                logger.info(f"✅ Created user {user_id} with 5 address columns")

                return {
                    'success': True,
                    'message': 'User created successfully',
                    'user_id': user_id,
                    'telegram_id': telegram_id,
                    'wallet_address': main_address,
                    'variants': {
                        'main': main_address,
                        'variant_1': variant_1,
                        'variant_2': variant_2,
                        'variant_3': variant_3,
                        'variant_4': variant_4
                    }
                }

        except Exception as e:
            logger.error(f"❌ Error creating user: {e}")
            return {'success': False, 'error': str(e)}

    def create_test_user(self, wallet_address):
        """Create a test user with wallet address for testing (legacy method)"""
        return self.create_user_with_wallet(wallet_address)

    def start_api_server(self):
        """Start the Flask API server"""
        try:
            self.app = Flask(__name__)
            CORS(self.app)
            
            # Add request logging middleware
            @self.app.before_request
            def log_request_info():
                logger.info(f"🌐 INCOMING REQUEST: {request.method} {request.url}")
                # Only try to get JSON if content type is application/json
                if request.content_type and 'application/json' in request.content_type:
                    try:
                        json_data = request.get_json(silent=True)
                        if json_data:
                            logger.info(f"📝 REQUEST BODY: {json_data}")
                    except Exception:
                        pass  # Ignore JSON parsing errors
            
            @self.app.after_request
            def log_response_info(response):
                logger.info(f"📤 RESPONSE: {response.status_code} for {request.method} {request.url}")
                if response.status_code >= 400:
                    logger.error(f"❌ ERROR RESPONSE: {response.get_data(as_text=True)}")
                return response
            
            @self.app.errorhandler(Exception)
            def handle_exception(e):
                logger.error(f"💥 UNHANDLED EXCEPTION: {str(e)}")
                logger.error(f"🔍 REQUEST: {request.method} {request.url}")
                # Only try to get JSON if content type is application/json
                if request.content_type and 'application/json' in request.content_type:
                    try:
                        json_data = request.get_json(silent=True)
                        if json_data:
                            logger.error(f"📝 REQUEST DATA: {json_data}")
                    except Exception:
                        pass  # Ignore JSON parsing errors
                return jsonify({
                    'success': False,
                    'error': f'Server error: {str(e)}'
                }), 500

            @self.app.route('/health', methods=['GET'])
            @self.app.route('/api/health', methods=['GET'])
            def health_check():
                """Health check endpoint"""
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.row_factory = sqlite3.Row  # This makes results accessible by column name
                        cursor = conn.execute("SELECT COUNT(*) FROM transactions")
                        tx_count = cursor.fetchone()[0]

                        # Try to get system status, but handle if table doesn't exist
                        try:
                            cursor = conn.execute("SELECT * FROM system_status WHERE id = 1")
                            status = cursor.fetchone()
                        except sqlite3.OperationalError:
                            status = None  # Table doesn't exist

                    return jsonify({
                        'status': 'healthy',
                        'timestamp': time.time(),
                        'database': 'connected',
                        'transactions': tx_count,
                        'monitor': 'running',
                        'deposit_address': self.WEBSITE_WALLET,
                        'last_check': status['last_check_at'] if status else 'never',
                        'db_status': status['db_status'] if status else 'unknown'
                    })
                except Exception as e:
                    return jsonify({
                        'status': 'unhealthy',
                        'error': str(e),
                        'timestamp': time.time()
                    }), 500

            @self.app.route('/api/balance/wallet/<path:wallet_address>', methods=['GET'])
            def get_balance_by_wallet_endpoint(wallet_address):
                """Get user balance by wallet address"""
                result = self.get_balance_by_wallet(wallet_address)
                if result['success']:
                    return jsonify(result)
                else:
                    return jsonify(result), 404

            @self.app.route('/api/get-balance', methods=['POST'])
            def get_balance_post():
                """Get user balance by wallet address (POST method)"""
                data = request.get_json()
                wallet_address = data.get('wallet_address') if data else None

                if not wallet_address:
                    return jsonify({
                        'success': False,
                        'error': 'wallet_address is required'
                    }), 400

                result = self.get_balance_by_wallet(wallet_address)
                if result['success']:
                    return jsonify(result)
                else:
                    return jsonify(result), 404

            @self.app.route('/api/users/create', methods=['POST'])
            def create_user_endpoint():
                """Create a user with wallet address"""
                try:
                    data = request.get_json()
                    if not data:
                        return jsonify({
                            'success': False,
                            'error': 'JSON data required'
                        }), 400

                    wallet_address = data.get('wallet_address')
                    telegram_id = data.get('telegram_id')

                    if not wallet_address:
                        return jsonify({
                            'success': False,
                            'error': 'wallet_address is required'
                        }), 400

                    result = self.create_user_with_wallet(wallet_address, telegram_id)
                    if result['success']:
                        return jsonify(result)
                    else:
                        return jsonify(result), 500
                        
                except Exception as e:
                    return jsonify({
                        'success': False,
                        'error': f'Server error: {str(e)}'
                    }), 500

            @self.app.route('/api/create-test-user/<wallet_address>', methods=['POST'])
            def create_test_user_endpoint(wallet_address):
                """Create a test user with wallet address (legacy endpoint)"""
                result = self.create_test_user(wallet_address)
                if result['success']:
                    return jsonify(result)
                else:
                    return jsonify(result), 500

            @self.app.route('/api/balance/<telegram_id>', methods=['GET'])
            def get_balance_endpoint(telegram_id):
                """Get user balance by telegram ID (frontend compatibility)"""
                logger.info(f"🔍 FRONTEND REQUEST: Get balance for telegram_id: {telegram_id}")
                result = self.get_balance(telegram_id)
                if result['success']:
                    logger.info(f"✅ FRONTEND SUCCESS: Found balance for telegram_id {telegram_id}: {result['balance']} TON")
                    return jsonify({
                        'success': True,
                        'data': {
                            'balance': result['balance'],
                            'availableForWithdrawal': result['balance'],
                            'total_deposited': result.get('total_deposited', 0),
                            'deposit_count': result.get('deposit_count', 0)
                        }
                    })
                else:
                    logger.error(f"❌ FRONTEND ERROR: User with telegram_id {telegram_id} not found")
                    return jsonify(result), 404

            @self.app.route('/api/balance/refresh/<int:user_id>', methods=['POST'])
            def refresh_balance(user_id):
                """Refresh user balance"""
                result = self.refresh_balance(user_id)
                if result['success']:
                    return jsonify(result)
                else:
                    return jsonify(result), 500

            @self.app.route('/api/balance/refresh/<telegram_id>', methods=['POST'])
            def refresh_balance_by_telegram_id(telegram_id):
                """Refresh user balance by telegram ID (frontend compatibility)"""
                logger.info(f"🔄 FRONTEND REQUEST: Balance refresh for telegram_id: {telegram_id}")
                
                # Get user by telegram_id first
                user_result = self.get_balance(telegram_id)
                if not user_result['success']:
                    logger.error(f"❌ FRONTEND ERROR: User with telegram_id {telegram_id} not found")
                    return jsonify({
                        'success': False,
                        'error': f'User with telegram_id {telegram_id} not found'
                    }), 404
                
                user_id = user_result['user_id']
                logger.info(f"✅ FRONTEND: Found user_id {user_id} for telegram_id {telegram_id}")
                
                refresh_result = self.refresh_balance(user_id)
                
                if refresh_result['success']:
                    logger.info(f"✅ FRONTEND SUCCESS: Balance refreshed for telegram_id {telegram_id}")
                    return jsonify({
                        'success': True,
                        'data': {
                            'balance': refresh_result['balance'],
                            'availableForWithdrawal': refresh_result['balance'],
                            'total_deposited': refresh_result.get('total_deposited', 0),
                            'deposit_count': refresh_result.get('deposit_count', 0)
                        }
                    })
                else:
                    logger.error(f"❌ FRONTEND ERROR: Balance refresh failed for telegram_id {telegram_id}: {refresh_result.get('error')}")
                    return jsonify(refresh_result), 500

            @self.app.route('/api/balance/refresh/wallet/<path:wallet_address>', methods=['POST'])
            def refresh_balance_by_wallet(wallet_address):
                """Refresh user balance by wallet address"""
                try:
                    # First get the user by wallet address
                    balance_result = self.get_balance_by_wallet(wallet_address)
                    if not balance_result['success']:
                        return jsonify(balance_result), 404
                    
                    user_id = balance_result['user_id']
                    
                    # Then refresh the balance
                    result = self.refresh_balance(user_id)
                    if result['success']:
                        return jsonify(result)
                    else:
                        return jsonify(result), 500
                        
                except Exception as e:
                    return jsonify({
                        'success': False,
                        'error': f'Server error: {str(e)}'
                    }), 500

            @self.app.route('/api/transactions/<int:user_id>', methods=['GET'])
            def get_user_transactions(user_id):
                """Get user transactions"""
                try:
                    limit = request.args.get('limit', 50, type=int)

                    with sqlite3.connect(self.db_path) as conn:
                        conn.row_factory = sqlite3.Row

                        actual_deposit_address = "EQDrY5iulWs_MyWTP9JSGedWBzlbeRmhCBoqsSaNiSLOsyC8"
                        cursor = conn.execute("""
                            SELECT * FROM transactions
                            WHERE to_address = ? OR from_address = ?
                            ORDER BY created_at DESC
                            LIMIT ?
                        """, (actual_deposit_address, actual_deposit_address, limit))

                        transactions = []
                        for row in cursor.fetchall():
                            transactions.append({
                                'hash': row['hash'],
                                'from_address': row['from_address'],
                                'to_address': row['to_address'],
                                'amount': row['amount'],
                                'status': row['status'],
                                'type': row['type'],
                                'created_at': row['created_at'],
                                'blockchain_timestamp': row['blockchain_timestamp']
                            })

                        return jsonify({
                            'success': True,
                            'transactions': transactions,
                            'count': len(transactions)
                        })

                except Exception as e:
                    return jsonify({
                        'success': False,
                        'error': str(e),
                        'transactions': []
                    }), 500

            logger.info("🌐 Starting API server on http://localhost:5001")
            logger.info("🔇 Logging: Only requests and important events will be shown")
            self.app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)

        except Exception as e:
            logger.error(f"❌ API server error: {e}")

    async def monitoring_loop(self):
        """Main monitoring loop - REAL deposit monitoring"""
        logger.info("🔄 Starting REAL deposit monitoring loop...")
        
        import requests
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        # Get last logical time from database to avoid reprocessing
        last_lt = None
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT last_logical_time FROM system_status WHERE id = 1")
                result = cursor.fetchone()
                if result and result[0]:
                    last_lt = result[0]
                    logger.info(f"📍 Resuming from logical time: {last_lt}")
                else:
                    logger.info("📍 Starting fresh - no previous logical time found")
        except Exception as e:
            logger.error(f"❌ Error reading last logical time: {e}")
            last_lt = None

        while self.running:
            try:
                logger.info(f"🔍 Checking deposits for wallet: {self.WEBSITE_WALLET}")
                
                # Get transactions from TONCenter API
                url = f"https://toncenter.com/api/v2/getTransactions"
                params = {
                    'address': self.WEBSITE_WALLET,
                    'limit': 20,
                    'to_lt': last_lt if last_lt else 0,
                    'archival': True
                }
                
                response = requests.get(url, params=params, timeout=30)
                if response.status_code != 200:
                    logger.error(f"❌ API error: {response.status_code}")
                    raise Exception(f"API returned {response.status_code}")
                
                data = response.json()
                if not data.get('ok'):
                    logger.error(f"❌ API response not ok: {data}")
                    raise Exception("API response not ok")
                
                transactions = data.get('result', [])
                logger.info(f"📊 Found {len(transactions)} transactions")
                
                # Process new transactions
                new_deposits = 0
                for tx in transactions:
                    try:
                        # Skip if we've seen this transaction
                        tx_lt = int(tx.get('transaction_id', {}).get('lt', 0))
                        if last_lt and tx_lt <= last_lt:
                            continue
                        
                        # Check if it's an incoming transaction
                        in_msg = tx.get('in_msg', {})
                        if not in_msg or in_msg.get('source') == '':
                            continue
                        
                        # Get sender address and amount
                        sender_address = in_msg.get('source', '')
                        value = int(in_msg.get('value', 0))
                        
                        if value <= 0:
                            continue
                        
                        value_ton = value / 1_000_000_000  # Convert to TON
                        logger.info(f"💰 Incoming: {value_ton} TON from {sender_address[:20]}...")
                        
                        # Find user by sender address
                        user_found = False
                        with sqlite3.connect(self.db_path) as conn:
                            # Check all address variants
                            variants = get_mainnet_variants(sender_address)
                            for variant in variants:
                                cursor = conn.execute("""
                                    SELECT id, telegram_id FROM users 
                                    WHERE main_wallet_address = ? 
                                    OR variant_address_1 = ?
                                    OR variant_address_2 = ?
                                    OR variant_address_3 = ?
                                    OR variant_address_4 = ?
                                """, (variant, variant, variant, variant, variant))
                                
                                user = cursor.fetchone()
                                if user:
                                    user_id, telegram_id = user
                                    logger.info(f"✅ Found user: {telegram_id} (ID: {user_id})")
                                    
                                    # Record transaction (check for duplicates first)
                                    tx_hash = tx.get('transaction_id', {}).get('hash', f'tx_{int(time.time())}_{tx_lt}')
                                    
                                    # Check if transaction already exists
                                    existing = conn.execute("""
                                        SELECT id FROM transactions WHERE hash = ?
                                    """, (tx_hash,)).fetchone()
                                    
                                    if existing:
                                        logger.info(f"⚠️ Transaction already processed: {tx_hash}")
                                        user_found = True
                                        break
                                    
                                    conn.execute("""
                                        INSERT INTO transactions (
                                            hash, from_address, to_address, amount, 
                                            user_id, status, transaction_type, logical_time, created_at
                                        ) VALUES (?, ?, ?, ?, ?, 'confirmed', 'deposit', ?, CURRENT_TIMESTAMP)
                                    """, (tx_hash, sender_address, self.WEBSITE_WALLET, value_ton, user_id, tx_lt))
                                    
                                    # Update user balance in user_balances table
                                    conn.execute("""
                                        INSERT OR REPLACE INTO user_balances (
                                            user_id, current_balance, total_deposited, deposit_count, 
                                            last_deposit_at, updated_at
                                        ) VALUES (
                                            ?, 
                                            COALESCE((SELECT current_balance FROM user_balances WHERE user_id = ?), 0) + ?,
                                            COALESCE((SELECT total_deposited FROM user_balances WHERE user_id = ?), 0) + ?,
                                            COALESCE((SELECT deposit_count FROM user_balances WHERE user_id = ?), 0) + 1,
                                            CURRENT_TIMESTAMP,
                                            CURRENT_TIMESTAMP
                                        )
                                    """, (user_id, user_id, value_ton, user_id, value_ton, user_id))
                                    
                                    logger.info(f"🎉 DEPOSIT PROCESSED: {value_ton} TON for user {telegram_id}")
                                    new_deposits += 1
                                    user_found = True
                                    break
                        
                        if not user_found:
                            logger.warning(f"⚠️ No user found for sender: {sender_address[:20]}...")
                        
                        # Update last logical time
                        if not last_lt or tx_lt > last_lt:
                            last_lt = tx_lt
                    
                    except Exception as e:
                        logger.error(f"❌ Error processing transaction: {e}")
                        continue
                
                if new_deposits > 0:
                    logger.info(f"🎉 Processed {new_deposits} new deposits!")
                else:
                    logger.info("📭 No new deposits found")
                
                # Update system status and save logical time
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute("""
                            UPDATE system_status SET
                            last_check_at = CURRENT_TIMESTAMP,
                            last_logical_time = ?,
                            is_monitoring = 1,
                            updated_at = CURRENT_TIMESTAMP
                            WHERE id = 1
                        """, (last_lt,))
                        logger.info(f"💾 Saved logical time: {last_lt}")
                except Exception as e:
                    logger.error(f"❌ Error updating system status: {e}")

                consecutive_errors = 0
                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Monitoring error: {e}")
                consecutive_errors += 1

                if consecutive_errors >= max_consecutive_errors:
                    logger.error("💥 Too many errors, stopping monitor")
                    break

                await asyncio.sleep(60)  # Wait longer after error

        logger.info("🏁 Monitoring loop ended")

    async def start(self):
        """Start the monitor"""
        logger.info("🚀 Starting TON Monitor (Working Version)")
        logger.info(f"👀 Monitoring website wallet: {self.WEBSITE_WALLET}")

        # Initialize database
        self.init_database()

        self.running = True

        # Start monitoring task
        monitor_task = asyncio.create_task(self.monitoring_loop())

        # Start API server in a separate thread
        api_thread = threading.Thread(target=self.start_api_server, daemon=True)
        api_thread.start()

        # Wait for monitor task
        await monitor_task

    async def stop(self):
        """Stop the monitor"""
        logger.info("🛑 Stopping TON Monitor...")
        self.running = False

        if self.app:
            # Stop Flask app
            import os
            os._exit(0)

def main():
    """Main entry point"""
    monitor = WorkingTONMonitor()

    async def run():
        try:
            await monitor.start()
        except KeyboardInterrupt:
            logger.info("🛑 Keyboard interrupt received")
        except Exception as e:
            logger.error(f"❌ Application error: {e}")
        finally:
            await monitor.stop()
            logger.info("👋 TON Monitor stopped")

    asyncio.run(run())

if __name__ == '__main__':
    main()
