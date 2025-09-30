#!/usr/bin/env python3
"""
🚀 Simple Railway API Server for Nova TON Monitor
Minimal, reliable API server for Railway deployment
"""

from flask import Flask, request, jsonify, g
from flask_cors import CORS
import time
import uuid
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import hashlib
import hmac
from functools import wraps
import os

# Simple database connection for Railway
import sqlite3
import sys

app = Flask(__name__)
CORS(app)

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
def get_db():
    """Get database connection."""
    if 'db' not in g:
        g.db = sqlite3.connect('/app/data/nova_ton_monitor.db')
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    """Close database connection."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize database with required tables."""
    db = get_db()

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
            FOREIGN KEY (user_id) REFERENCES users (id)
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
            FOREIGN KEY (user_id) REFERENCES users (id)
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

    db.commit()

# Initialize database on startup
with app.app_context():
    init_db()

# Middleware
@app.before_request
def before_request():
    """Pre-request middleware."""
    g.correlation_id = str(uuid.uuid4())
    g.start_time = time.time()

@app.after_request
def after_request(response):
    """Post-request middleware."""
    response_time = time.time() - g.start_time
    logger.info(f"Request: {request.method} {request.path} - {response.status_code} - {response_time:.3f}s")
    return response

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        # Check database
        db = get_db()
        db.execute('SELECT 1').fetchone()

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected',
            'correlation_id': g.correlation_id
        }), 200

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat(),
            'correlation_id': g.correlation_id
        }), 503

# Create user endpoint
@app.route('/api/users/create', methods=['POST'])
def create_user():
    """Create a new user."""
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400

        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body cannot be empty'}), 400

        wallet_address = data.get('wallet_address')
        telegram_id = data.get('telegram_id')

        if not wallet_address or not telegram_id:
            return jsonify({'error': 'wallet_address and telegram_id are required'}), 400

        db = get_db()

        # Check if user exists
        existing = db.execute(
            'SELECT id FROM users WHERE telegram_id = ?',
            (telegram_id,)
        ).fetchone()

        if existing:
            return jsonify({
                'success': True,
                'message': 'User already exists',
                'user_id': existing['id'],
                'telegram_id': telegram_id,
                'wallet_address': wallet_address,
                'correlation_id': g.correlation_id
            }), 200

        # Create user
        cursor = db.execute(
            'INSERT INTO users (telegram_id, main_wallet_address) VALUES (?, ?)',
            (telegram_id, wallet_address)
        )
        user_id = cursor.lastrowid

        # Initialize balance
        db.execute(
            'INSERT INTO user_balances (user_id, balance) VALUES (?, 0)',
            (user_id,)
        )

        # Store address variant
        db.execute(
            'INSERT INTO user_address_variants (user_id, address_variant, variant_type) VALUES (?, ?, ?)',
            (user_id, wallet_address, 'main')
        )

        db.commit()

        return jsonify({
            'success': True,
            'message': 'User created successfully',
            'user_id': user_id,
            'telegram_id': telegram_id,
            'wallet_address': wallet_address,
            'correlation_id': g.correlation_id
        }), 201

    except Exception as e:
        logger.error(f"User creation failed: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'correlation_id': g.correlation_id
        }), 500

# Get balance by wallet address
@app.route('/api/balance/wallet/<path:wallet_address>', methods=['GET'])
def get_balance_by_wallet(wallet_address: str):
    """Get user balance by wallet address."""
    try:
        db = get_db()

        # Find user by address variant
        user_data = db.execute('''
            SELECT u.id, u.telegram_id, u.main_wallet_address,
                   ub.balance, ub.available_balance, ub.locked_balance
            FROM users u
            JOIN user_address_variants uav ON u.id = uav.user_id
            LEFT JOIN user_balances ub ON u.id = ub.user_id
            WHERE uav.address_variant = ?
        ''', (wallet_address,)).fetchone()

        if not user_data:
            return jsonify({
                'success': False,
                'error': 'Wallet address not found',
                'correlation_id': g.correlation_id
            }), 404

        return jsonify({
            'success': True,
            'user_id': user_data['id'],
            'telegram_id': user_data['telegram_id'],
            'wallet_address': user_data['main_wallet_address'],
            'balance': float(user_data['balance'] or 0),
            'available_balance': float(user_data['available_balance'] or 0),
            'locked_balance': float(user_data['locked_balance'] or 0),
            'correlation_id': g.correlation_id
        }), 200

    except Exception as e:
        logger.error(f"Balance lookup failed: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'correlation_id': g.correlation_id
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
