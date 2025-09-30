#!/usr/bin/env python3
"""
🚀 Railway-Optimized API Server for Nova TON Monitor
Minimal, reliable API server optimized for Railway deployment
"""

try:
    from flask import Flask, request, jsonify, g
    from flask_cors import CORS
    import time
    import uuid
    import json
    import traceback
    from datetime import datetime
    import sqlite3
    import logging
    import os
except ImportError as e:
    print(f"Import error: {e}")
    raise

# Configure logging for Railway deployment
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure Flask app for Gunicorn
app = Flask(__name__)
CORS(app)

# Configure Flask app for Gunicorn (after app creation)
app.config['TESTING'] = False
app.config['DEBUG'] = False
app.config['PROPAGATE_EXCEPTIONS'] = True

# Global variable to track if app is ready
app_ready = False

# Database configuration for Railway
DATABASE_PATH = '/app/data/nova_ton_monitor.db'

def get_db():
    """Get database connection with Railway optimization."""
    if not hasattr(g, 'db'):
        g.db = sqlite3.connect(DATABASE_PATH, timeout=20.0)
        g.db.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency
        g.db.execute('PRAGMA journal_mode=WAL')
    return g.db

@app.teardown_appcontext
def close_db(error):
    """Close database connection."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize database with Railway-compatible schema."""
    try:
        # Ensure data directory exists
        os.makedirs('/app/data', exist_ok=True)

        db = sqlite3.connect(DATABASE_PATH)
        db.row_factory = sqlite3.Row

        # Create users table
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT UNIQUE NOT NULL,
                main_wallet_address TEXT NOT NULL,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create user_address_variants table
        db.execute('''
            CREATE TABLE IF NOT EXISTS user_address_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                address_variant TEXT NOT NULL,
                variant_type TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(user_id, address_variant)
            )
        ''')

        # Create user_balances table
        db.execute('''
            CREATE TABLE IF NOT EXISTS user_balances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                balance DECIMAL(36, 18) DEFAULT 0,
                available_balance DECIMAL(36, 18) DEFAULT 0,
                locked_balance DECIMAL(36, 18) DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(user_id)
            )
        ''')

        # Create transactions table
        db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                tx_hash TEXT NOT NULL,
                from_address TEXT NOT NULL,
                to_address TEXT NOT NULL,
                amount DECIMAL(36, 18) NOT NULL,
                fee DECIMAL(36, 18) DEFAULT 0,
                transaction_time DATETIME NOT NULL,
                processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'confirmed',
                block_height INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # Create indexes for better performance
        db.execute('CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_address_variants_address ON user_address_variants(address_variant)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)')

        db.commit()
        db.close()

        logger.info("Database initialized successfully")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

# Initialize database at module level (for Gunicorn compatibility)
try:
    init_db()
    logger.info("Database initialized at module level")
except Exception as e:
    logger.error(f"Failed to initialize database at module level: {e}")
    # Don't raise here as it might prevent Gunicorn from starting

# Get balance by wallet address
@app.route('/api/balance/wallet/<path:wallet_address>', methods=['GET'])
def get_balance_by_wallet(wallet_address: str):
    """Get user balance by wallet address."""
    try:
        db = get_db()

        # Find user by address variant
        user_data = db.execute('''
            SELECT u.id, u.telegram_id, u.main_wallet_address,
                   COALESCE(ub.balance, 0) as balance,
                   COALESCE(ub.available_balance, 0) as available_balance,
                   COALESCE(ub.locked_balance, 0) as locked_balance
            FROM users u
            JOIN user_address_variants uav ON u.id = uav.user_id
            LEFT JOIN user_balances ub ON u.id = ub.user_id
            WHERE uav.address_variant = ?
        ''', (wallet_address,)).fetchone()

        if not user_data:
            return jsonify({
                'success': False,
                'error': 'Wallet address not found'
            }), 404

        return jsonify({
            'success': True,
            'user_id': user_data['id'],
            'telegram_id': user_data['telegram_id'],
            'wallet_address': user_data['main_wallet_address'],
            'balance': float(user_data['balance']),
            'available_balance': float(user_data['available_balance']),
            'locked_balance': float(user_data['locked_balance'])
        }), 200

    except Exception as e:
        logger.error(f"Balance lookup failed: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

# Root endpoint
@app.route('/', methods=['GET'])
def root():
    """Root endpoint."""
    return jsonify({
        'message': 'Nova TON Monitor API',
        'version': '1.0.0',
        'status': 'running'
    }), 200

# Health check endpoint for Railway
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Railway."""
    try:
        # Test database connection
        db = get_db()
        db.execute('SELECT 1').fetchone()
        db.close()

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'nova-ton-monitor',
            'database': 'connected'
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }), 503

# Startup endpoint for debugging
@app.route('/startup', methods=['GET'])
def startup_check():
    """Startup check endpoint."""
    return jsonify({
        'status': 'started',
        'timestamp': datetime.utcnow().isoformat(),
        'port': os.environ.get('PORT', '5001'),
        'database_path': DATABASE_PATH
    }), 200

# For local development
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
