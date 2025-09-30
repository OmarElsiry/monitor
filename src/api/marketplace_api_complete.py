#!/usr/bin/env python3
"""
🏪 Complete Channel Marketplace API
🎯 Integrates bot verification, escrow system, and Nova TON monitoring

Complete Business Flow:
1. Seller adds bot as admin → /verify
2. Bot verifies ownership & gifts → creates listing
3. Buyer purchases → /buy - money held in escrow
4. Both parties confirm transfer → /confirm
5. Funds released automatically

Author: Nova Team
Version: 3.0
"""

from flask import Flask, request, jsonify, g
from flask_cors import CORS
import sqlite3
import json
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import os
import sys

# Add utils path for address normalization
sys.path.append('./utils')

# Import our custom modules
from escrow_system import EscrowTransactionSystem

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Initialize systems
escrow_system = EscrowTransactionSystem()

DATABASE_PATH = "./data/channel_marketplace.db"

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def require_auth(f):
    """Simple authentication decorator."""
    def decorated_function(*args, **kwargs):
        user_id = request.headers.get('X-User-ID')
        wallet_address = request.headers.get('X-Wallet-Address')
        
        if not user_id and not wallet_address:
            return jsonify({'error': 'Authentication required'}), 401
        
        g.user_id = user_id
        g.wallet_address = wallet_address
        return f(*args, **kwargs)
    return decorated_function

# =====================================================
# 🤖 BOT VERIFICATION ENDPOINTS
# =====================================================

@app.route('/api/marketplace/verify', methods=['POST'])
@require_auth
def verify_channel():
    """Initiate channel verification through bot."""
    try:
        data = request.get_json()
        channel_identifier = data.get('channel_identifier')
        
        if not channel_identifier:
            return jsonify({'error': 'Channel identifier required'}), 400
        
        # Create verification request
        verification_id = create_verification_request(
            g.user_id, channel_identifier, g.wallet_address
        )
        
        return jsonify({
            'success': True,
            'verification_id': verification_id,
            'message': 'Verification request created. Please add the bot as admin to your channel.',
            'bot_username': '@YourMarketplaceBot',  # Replace with actual bot username
            'next_step': 'Add bot as admin, then bot will automatically verify'
        })
        
    except Exception as e:
        logger.error(f"Verify channel error: {e}")
        return jsonify({'error': 'Verification failed'}), 500

@app.route('/api/marketplace/verification/<verification_id>', methods=['GET'])
@require_auth
def get_verification_status(verification_id):
    """Get verification status and results."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM channel_verifications 
            WHERE verification_id = ? AND user_id = ?
        """, (verification_id, g.user_id))
        
        verification = cursor.fetchone()
        conn.close()
        
        if not verification:
            return jsonify({'error': 'Verification not found'}), 404
        
        result = {
            'verification_id': verification['verification_id'],
            'status': verification['status'],
            'channel_info': json.loads(verification['verification_data'] or '{}'),
            'gifts_info': json.loads(verification['gifts_data'] or '{}'),
            'created_at': verification['created_at']
        }
        
        return jsonify({'success': True, 'verification': result})
        
    except Exception as e:
        logger.error(f"Get verification error: {e}")
        return jsonify({'error': 'Failed to get verification'}), 500

# =====================================================
# 📝 LISTING MANAGEMENT ENDPOINTS
# =====================================================

@app.route('/api/marketplace/listings', methods=['POST'])
@require_auth
def create_listing():
    """Create channel listing after verification."""
    try:
        data = request.get_json()
        verification_id = data.get('verification_id')
        price = data.get('price')
        
        if not verification_id or not price:
            return jsonify({'error': 'Verification ID and price required'}), 400
        
        try:
            price = float(price)
            if price <= 0:
                return jsonify({'error': 'Price must be greater than 0'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid price format'}), 400
        
        # Create listing
        listing_id = create_channel_listing(verification_id, g.user_id, price)
        
        if listing_id:
            return jsonify({
                'success': True,
                'listing_id': listing_id,
                'message': 'Channel listing created successfully'
            })
        else:
            return jsonify({'error': 'Failed to create listing'}), 500
        
    except Exception as e:
        logger.error(f"Create listing error: {e}")
        return jsonify({'error': 'Failed to create listing'}), 500

@app.route('/api/marketplace/listings', methods=['GET'])
def get_listings():
    """Get available channel listings."""
    try:
        # Get query parameters
        category = request.args.get('category')
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        search = request.args.get('search', '')
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Build query
        query = """
            SELECT l.*, v.channel_title, v.verification_data, v.gifts_data
            FROM channel_listings l
            JOIN channel_verifications v ON l.verification_id = v.verification_id
            WHERE l.status = 'active'
        """
        params = []
        
        if min_price:
            query += " AND CAST(l.price AS REAL) >= ?"
            params.append(min_price)
        
        if max_price:
            query += " AND CAST(l.price AS REAL) <= ?"
            params.append(max_price)
        
        if search:
            query += " AND (v.channel_title LIKE ? OR v.channel_username LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        
        query += " ORDER BY l.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, (page - 1) * limit])
        
        cursor.execute(query, params)
        listings = []
        
        for row in cursor.fetchall():
            listing = dict(row)
            listing['channel_info'] = json.loads(listing['verification_data'] or '{}')
            listing['gifts_info'] = json.loads(listing['gifts_data'] or '{}')
            listings.append(listing)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'listings': listings,
            'page': page,
            'limit': limit
        })
        
    except Exception as e:
        logger.error(f"Get listings error: {e}")
        return jsonify({'error': 'Failed to get listings'}), 500

# =====================================================
# 💰 PURCHASE & ESCROW ENDPOINTS
# =====================================================

@app.route('/api/marketplace/purchase', methods=['POST'])
@require_auth
def initiate_purchase():
    """Initiate channel purchase with escrow."""
    try:
        data = request.get_json()
        listing_id = data.get('listing_id')
        
        if not listing_id:
            return jsonify({'error': 'Listing ID required'}), 400
        
        # Create escrow transaction
        result = await escrow_system.create_escrow_transaction(
            listing_id, int(g.user_id), g.wallet_address
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'transaction_id': result['transaction_id'],
                'escrow_address': result['escrow_address'],
                'amount': result['amount'],
                'timeout_hours': result['timeout_hours'],
                'message': 'Send payment to escrow address to proceed'
            })
        else:
            return jsonify({'error': result['error']}), 400
        
    except Exception as e:
        logger.error(f"Initiate purchase error: {e}")
        return jsonify({'error': 'Failed to initiate purchase'}), 500

@app.route('/api/marketplace/confirm-payment', methods=['POST'])
@require_auth
def confirm_payment():
    """Confirm payment received in escrow."""
    try:
        data = request.get_json()
        transaction_id = data.get('transaction_id')
        payment_hash = data.get('payment_hash')
        
        if not transaction_id or not payment_hash:
            return jsonify({'error': 'Transaction ID and payment hash required'}), 400
        
        result = await escrow_system.confirm_payment_received(transaction_id, payment_hash)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result['error']}), 400
        
    except Exception as e:
        logger.error(f"Confirm payment error: {e}")
        return jsonify({'error': 'Failed to confirm payment'}), 500

@app.route('/api/marketplace/confirm-transfer', methods=['POST'])
@require_auth
def confirm_transfer():
    """Confirm ownership transfer (buyer or seller)."""
    try:
        data = request.get_json()
        transaction_id = data.get('transaction_id')
        role = data.get('role')  # 'buyer' or 'seller'
        
        if not transaction_id or not role:
            return jsonify({'error': 'Transaction ID and role required'}), 400
        
        if role not in ['buyer', 'seller']:
            return jsonify({'error': 'Role must be buyer or seller'}), 400
        
        result = await escrow_system.confirm_ownership_transfer(
            transaction_id, int(g.user_id), role
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result['error']}), 400
        
    except Exception as e:
        logger.error(f"Confirm transfer error: {e}")
        return jsonify({'error': 'Failed to confirm transfer'}), 500

# =====================================================
# 📊 TRANSACTION STATUS ENDPOINTS
# =====================================================

@app.route('/api/marketplace/transaction/<transaction_id>', methods=['GET'])
@require_auth
def get_transaction_status(transaction_id):
    """Get transaction status and details."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT et.*, cl.channel_title, cl.channel_username
            FROM escrow_transactions et
            JOIN channel_listings cl ON et.listing_id = cl.listing_id
            WHERE et.transaction_id = ? 
            AND (et.buyer_id = ? OR et.seller_id = ?)
        """, (transaction_id, g.user_id, g.user_id))
        
        transaction = cursor.fetchone()
        conn.close()
        
        if not transaction:
            return jsonify({'error': 'Transaction not found'}), 404
        
        return jsonify({
            'success': True,
            'transaction': dict(transaction)
        })
        
    except Exception as e:
        logger.error(f"Get transaction error: {e}")
        return jsonify({'error': 'Failed to get transaction'}), 500

@app.route('/api/marketplace/my-transactions', methods=['GET'])
@require_auth
def get_my_transactions():
    """Get user's transactions (buying and selling)."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT et.*, cl.channel_title, cl.channel_username,
                   CASE WHEN et.buyer_id = ? THEN 'buyer' ELSE 'seller' END as user_role
            FROM escrow_transactions et
            JOIN channel_listings cl ON et.listing_id = cl.listing_id
            WHERE et.buyer_id = ? OR et.seller_id = ?
            ORDER BY et.created_at DESC
        """, (g.user_id, g.user_id, g.user_id))
        
        transactions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'transactions': transactions
        })
        
    except Exception as e:
        logger.error(f"Get my transactions error: {e}")
        return jsonify({'error': 'Failed to get transactions'}), 500

# =====================================================
# 🔧 UTILITY FUNCTIONS
# =====================================================

def create_verification_request(user_id: str, channel_identifier: str, wallet_address: str) -> str:
    """Create verification request in database."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        verification_id = f"verify_{user_id}_{int(datetime.now().timestamp())}"
        
        cursor.execute("""
            INSERT INTO channel_verifications (
                verification_id, user_id, channel_id, status, created_at
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            verification_id, user_id, channel_identifier, 'pending', 
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        return verification_id
        
    except Exception as e:
        logger.error(f"Create verification request error: {e}")
        return None

def create_channel_listing(verification_id: str, user_id: str, price: float) -> str:
    """Create channel listing."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Verify ownership
        cursor.execute("""
            SELECT * FROM channel_verifications 
            WHERE verification_id = ? AND user_id = ? AND status = 'verified'
        """, (verification_id, user_id))
        
        verification = cursor.fetchone()
        if not verification:
            return None
        
        listing_id = f"listing_{user_id}_{int(datetime.now().timestamp())}"
        
        cursor.execute("""
            INSERT INTO channel_listings (
                listing_id, verification_id, seller_id, channel_id,
                channel_username, channel_title, price, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            listing_id, verification_id, user_id, verification['channel_id'],
            verification['channel_username'], verification['channel_title'],
            str(price), 'active', datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        return listing_id
        
    except Exception as e:
        logger.error(f"Create listing error: {e}")
        return None

# =====================================================
# 🏥 HEALTH CHECK
# =====================================================

@app.route('/api/marketplace/health', methods=['GET'])
def health_check():
    """API health check."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM channel_listings WHERE status = 'active'")
        active_listings = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'active_listings': active_listings
        })
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# =====================================================
# 🚀 MAIN APPLICATION
# =====================================================

def init_database():
    """Initialize database with all required tables."""
    try:
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Import escrow schema
        from escrow_system import ESCROW_SCHEMA
        cursor.executescript(ESCROW_SCHEMA)
        
        conn.commit()
        conn.close()
        
        logger.info("✅ Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")

if __name__ == '__main__':
    print("🏪 Channel Marketplace API Server")
    print("=" * 40)
    
    # Initialize database
    init_database()
    
    # Start server
    app.run(host='0.0.0.0', port=8080, debug=True)
