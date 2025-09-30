#!/usr/bin/env python3
"""
🚀 Minimal Nova TON Monitor for Replit
Simple Flask API that works within Replit's limits
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
CORS(app)

# Simple in-memory database for demo
DATABASE = ':memory:'

def init_db():
    """Initialize simple database."""
    conn = sqlite3.connect(DATABASE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            telegram_id TEXT UNIQUE,
            wallet_address TEXT NOT NULL,
            balance REAL DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/', methods=['GET'])
def root():
    """Root endpoint."""
    return jsonify({
        'message': 'Nova TON Monitor API',
        'version': '1.0.0',
        'status': 'running'
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'nova-ton-monitor'
    })

@app.route('/api/balance/wallet/<wallet_address>', methods=['GET'])
def get_balance(wallet_address):
    """Get balance by wallet address."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.execute(
            'SELECT * FROM users WHERE wallet_address = ?',
            (wallet_address,)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            return jsonify({
                'success': True,
                'user_id': user[0],
                'telegram_id': user[1],
                'wallet_address': user[2],
                'balance': user[3]
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Wallet not found'
            }), 404

    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({
            'success': False,
            'error': 'Server error'
        }), 500

@app.route('/api/users/create', methods=['POST'])
def create_user():
    """Create new user."""
    try:
        data = request.get_json()
        if not data or 'wallet_address' not in data:
            return jsonify({'success': False, 'error': 'Wallet address required'}), 400

        wallet_address = data['wallet_address']

        conn = sqlite3.connect(DATABASE)
        conn.execute(
            'INSERT OR REPLACE INTO users (wallet_address, balance) VALUES (?, 0)',
            (wallet_address,)
        )
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'User created',
            'wallet_address': wallet_address
        })

    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({
            'success': False,
            'error': 'Server error'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
