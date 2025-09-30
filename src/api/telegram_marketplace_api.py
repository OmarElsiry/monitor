#!/usr/bin/env python3
"""
📱 Telegram Channel Marketplace API Server
🎯 RESTful API for the comprehensive marketplace system

This server provides all API endpoints for:
- Channel management and listing
- User registration and authentication  
- Transaction processing and escrow
- Bot verification system
- Dispute resolution
- Reviews and ratings

Author: Nova Team
Version: 3.0
Last Updated: September 27, 2025
"""

from flask import Flask, request, jsonify, g
from flask_cors import CORS
import sqlite3
import json
import hashlib
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import os
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
DATABASE_PATH = "./data/TelegramMarketplace.db"
API_VERSION = "3.0"

class MarketplaceAPI:
    """Main API class for Telegram Channel Marketplace."""
    
    def __init__(self):
        self.db_path = DATABASE_PATH
        
    def get_db(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn
    
    def log_audit(self, user_id, action, entity_type, entity_id, description):
        """Log audit trail."""
        try:
            conn = self.get_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_logs (user_id, action, entity_type, entity_id, description)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, action, entity_type, entity_id, description))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Audit log error: {e}")

# Initialize API
marketplace = MarketplaceAPI()

def require_auth(f):
    """Authentication decorator."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Simple auth - in production use proper JWT/OAuth
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated_function

# =====================================================
# 👥 USER MANAGEMENT ENDPOINTS
# =====================================================

@app.route('/api/users/register', methods=['POST'])
def register_user():
    """Register new user in marketplace."""
    try:
        data = request.get_json()
        
        conn = marketplace.get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO users (telegram_id, username, full_name, main_wallet_address, user_type)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data['telegram_id'], data.get('username'), data.get('full_name'),
            data['main_wallet_address'], data.get('user_type', 'buyer')
        ))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        marketplace.log_audit(user_id, 'user_registered', 'user', user_id, 'New user registration')
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'message': 'User registered successfully'
        }), 201
        
    except sqlite3.IntegrityError as e:
        return jsonify({'error': 'User already exists or invalid data'}), 400
    except Exception as e:
        logger.error(f"User registration error: {e}")
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/api/users/<user_id>', methods=['GET'])
@require_auth
def get_user_profile(user_id):
    """Get user profile and statistics."""
    try:
        conn = marketplace.get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM user_stats_view WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        conn.close()
        
        return jsonify({
            'success': True,
            'user': dict(user)
        })
        
    except Exception as e:
        logger.error(f"Get user profile error: {e}")
        return jsonify({'error': 'Failed to get user profile'}), 500

# =====================================================
# 📺 CHANNEL MANAGEMENT ENDPOINTS  
# =====================================================

@app.route('/api/channels/create', methods=['POST'])
@require_auth
def create_channel_listing():
    """Create new channel listing."""
    try:
        data = request.get_json()
        
        conn = marketplace.get_db()
        cursor = conn.cursor()
        
        # Generate verification token
        verification_token = str(uuid.uuid4())
        
        cursor.execute("""
            INSERT INTO channels (
                channel_id, channel_username, channel_title, channel_description,
                seller_id, member_count, asking_price, category, verification_token
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['channel_id'], data.get('channel_username'), data['channel_title'],
            data.get('channel_description'), g.user_id, data['member_count'],
            data['asking_price'], data['category'], verification_token
        ))
        
        channel_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        marketplace.log_audit(g.user_id, 'channel_listed', 'channel', channel_id, 
                            f"Channel {data['channel_title']} listed for sale")
        
        return jsonify({
            'success': True,
            'channel_id': channel_id,
            'verification_token': verification_token,
            'message': 'Channel listing created successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"Create channel error: {e}")
        return jsonify({'error': 'Failed to create channel listing'}), 500

@app.route('/api/channels/search', methods=['GET'])
def search_channels():
    """Search and filter channels."""
    try:
        # Get query parameters
        category = request.args.get('category')
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        min_members = request.args.get('min_members', type=int)
        search_term = request.args.get('q', '')
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        
        conn = marketplace.get_db()
        cursor = conn.cursor()
        
        # Build query
        query = "SELECT * FROM active_channels_view WHERE 1=1"
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if min_price:
            query += " AND asking_price >= ?"
            params.append(min_price)
            
        if max_price:
            query += " AND asking_price <= ?"
            params.append(max_price)
            
        if min_members:
            query += " AND member_count >= ?"
            params.append(min_members)
            
        if search_term:
            query += " AND (channel_title LIKE ? OR channel_description LIKE ?)"
            params.extend([f"%{search_term}%", f"%{search_term}%"])
        
        query += " ORDER BY is_featured DESC, listed_at DESC"
        query += f" LIMIT {limit} OFFSET {(page-1)*limit}"
        
        cursor.execute(query, params)
        channels = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'channels': channels,
            'page': page,
            'limit': limit
        })
        
    except Exception as e:
        logger.error(f"Search channels error: {e}")
        return jsonify({'error': 'Search failed'}), 500

# =====================================================
# 💰 TRANSACTION ENDPOINTS
# =====================================================

@app.route('/api/transactions/initiate', methods=['POST'])
@require_auth
def initiate_purchase():
    """Initiate channel purchase transaction."""
    try:
        data = request.get_json()
        channel_id = data['channel_id']
        offer_amount = data.get('offer_amount')
        
        conn = marketplace.get_db()
        cursor = conn.cursor()
        
        # Get channel details
        cursor.execute("SELECT * FROM channels WHERE id = ? AND status = 'active'", (channel_id,))
        channel = cursor.fetchone()
        
        if not channel:
            return jsonify({'error': 'Channel not found or not available'}), 404
        
        if channel['seller_id'] == int(g.user_id):
            return jsonify({'error': 'Cannot buy your own channel'}), 400
        
        # Determine transaction amount
        amount = offer_amount if offer_amount else channel['asking_price']
        
        # Create transaction
        cursor.execute("""
            INSERT INTO transactions (
                buyer_id, seller_id, channel_id, transaction_type, status, amount,
                from_address, to_address, memo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            g.user_id, channel['seller_id'], channel_id, 'channel_purchase', 'pending',
            amount, data['from_address'], data['to_address'], 
            f"Purchase of channel: {channel['channel_title']}"
        ))
        
        transaction_id = cursor.lastrowid
        
        # Create escrow account
        escrow_address = f"ESCROW_{transaction_id}_{uuid.uuid4().hex[:8]}"
        cursor.execute("""
            INSERT INTO escrow_accounts (
                transaction_id, escrow_address, amount_locked, buyer_id, seller_id
            ) VALUES (?, ?, ?, ?, ?)
        """, (transaction_id, escrow_address, amount, g.user_id, channel['seller_id']))
        
        conn.commit()
        conn.close()
        
        marketplace.log_audit(g.user_id, 'purchase_initiated', 'transaction', transaction_id,
                            f"Purchase initiated for channel {channel['channel_title']}")
        
        return jsonify({
            'success': True,
            'transaction_id': transaction_id,
            'escrow_address': escrow_address,
            'amount': str(amount),
            'message': 'Purchase initiated successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"Initiate purchase error: {e}")
        return jsonify({'error': 'Failed to initiate purchase'}), 500

# =====================================================
# 🤖 BOT VERIFICATION ENDPOINTS
# =====================================================

@app.route('/api/bot/verify-ownership', methods=['POST'])
@require_auth
def verify_channel_ownership():
    """Initiate bot verification for channel ownership."""
    try:
        data = request.get_json()
        channel_id = data['channel_id']
        
        conn = marketplace.get_db()
        cursor = conn.cursor()
        
        # Check if channel exists and belongs to user
        cursor.execute("SELECT * FROM channels WHERE id = ? AND seller_id = ?", 
                      (channel_id, g.user_id))
        channel = cursor.fetchone()
        
        if not channel:
            return jsonify({'error': 'Channel not found or not owned by user'}), 404
        
        # Create verification session
        session_id = str(uuid.uuid4())
        verification_code = f"VERIFY_{uuid.uuid4().hex[:8].upper()}"
        
        cursor.execute("""
            INSERT INTO bot_verifications (
                channel_id, user_id, verification_type, bot_session_id, 
                verification_code, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            channel_id, g.user_id, 'ownership', session_id, verification_code,
            (datetime.now() + timedelta(hours=1)).isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'verification_code': verification_code,
            'instructions': f'Post the code "{verification_code}" in your channel to verify ownership',
            'expires_in': 3600
        })
        
    except Exception as e:
        logger.error(f"Verify ownership error: {e}")
        return jsonify({'error': 'Verification failed'}), 500

# =====================================================
# 💬 DISPUTE ENDPOINTS
# =====================================================

@app.route('/api/disputes/create', methods=['POST'])
@require_auth
def create_dispute():
    """Create new dispute for transaction."""
    try:
        data = request.get_json()
        
        conn = marketplace.get_db()
        cursor = conn.cursor()
        
        # Get transaction details
        cursor.execute("""
            SELECT * FROM transactions WHERE id = ? 
            AND (buyer_id = ? OR seller_id = ?)
        """, (data['transaction_id'], g.user_id, g.user_id))
        
        transaction = cursor.fetchone()
        if not transaction:
            return jsonify({'error': 'Transaction not found'}), 404
        
        # Determine respondent
        respondent_id = transaction['seller_id'] if transaction['buyer_id'] == int(g.user_id) else transaction['buyer_id']
        
        cursor.execute("""
            INSERT INTO disputes (
                transaction_id, channel_id, initiator_id, respondent_id,
                dispute_type, reason, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data['transaction_id'], transaction['channel_id'], g.user_id, respondent_id,
            data['dispute_type'], data['reason'], data.get('description')
        ))
        
        dispute_id = cursor.lastrowid
        
        # Update transaction status
        cursor.execute("UPDATE transactions SET is_disputed = 1, dispute_id = ? WHERE id = ?",
                      (dispute_id, data['transaction_id']))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'dispute_id': dispute_id,
            'message': 'Dispute created successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"Create dispute error: {e}")
        return jsonify({'error': 'Failed to create dispute'}), 500

# =====================================================
# 📊 ANALYTICS ENDPOINTS
# =====================================================

@app.route('/api/analytics/dashboard', methods=['GET'])
@require_auth
def get_dashboard_analytics():
    """Get dashboard analytics for user."""
    try:
        conn = marketplace.get_db()
        cursor = conn.cursor()
        
        # User statistics
        cursor.execute("SELECT * FROM user_stats_view WHERE id = ?", (g.user_id,))
        user_stats = dict(cursor.fetchone() or {})
        
        # Recent transactions
        cursor.execute("""
            SELECT * FROM transaction_summary_view 
            WHERE buyer_id = ? OR seller_id = ?
            ORDER BY created_at DESC LIMIT 10
        """, (g.user_id, g.user_id))
        recent_transactions = [dict(row) for row in cursor.fetchall()]
        
        # Active listings
        cursor.execute("""
            SELECT COUNT(*) as active_listings FROM channels 
            WHERE seller_id = ? AND status = 'active'
        """, (g.user_id,))
        active_listings = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'analytics': {
                'user_stats': user_stats,
                'recent_transactions': recent_transactions,
                'active_listings': active_listings
            }
        })
        
    except Exception as e:
        logger.error(f"Dashboard analytics error: {e}")
        return jsonify({'error': 'Failed to get analytics'}), 500

# =====================================================
# 🔧 UTILITY ENDPOINTS
# =====================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """API health check."""
    try:
        conn = marketplace.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'version': API_VERSION,
            'database': 'connected',
            'users': user_count,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Get available channel categories."""
    categories = [
        'crypto', 'news', 'entertainment', 'gaming', 
        'education', 'business', 'lifestyle', 'technology', 'other'
    ]
    return jsonify({'categories': categories})

if __name__ == '__main__':
    print("🚀 Starting Telegram Channel Marketplace API Server")
    print(f"📍 Database: {DATABASE_PATH}")
    print(f"🔗 Version: {API_VERSION}")
    
    # Ensure database exists
    if not os.path.exists(DATABASE_PATH):
        print("❌ Database not found! Please run telegram_marketplace_init.py first")
        exit(1)
    
    app.run(host='0.0.0.0', port=8080, debug=True)
