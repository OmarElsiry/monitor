#!/usr/bin/env python3
"""
🚀 Production API Server for Nova TON Monitor
High-performance, secure API with monitoring, rate limiting, and error handling
"""

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import time
import uuid
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import hashlib
import hmac
from functools import wraps
import redis
import os

from ..database.production_db import get_database
from ..utils.production_logger import LoggerFactory, log_performance, log_errors
from ..config.production import get_config
from ..utils.address_normalizer import get_mainnet_variants

class ProductionAPIServer:
    """Production-ready API server with advanced features."""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.app = Flask(__name__)
        self.db = get_database()
        self.logger = LoggerFactory.get_api_logger()
        self.security_logger = LoggerFactory.get_security_logger()
        
        self._setup_app()
        self._setup_middleware()
        self._setup_routes()
        self._setup_error_handlers()
    
    def _setup_app(self):
        """Configure Flask application."""
        self.app.config['SECRET_KEY'] = self.config.api.secret_key
        self.app.config['MAX_CONTENT_LENGTH'] = self.config.api.max_content_length
        self.app.config['JSON_SORT_KEYS'] = False
        
        # CORS configuration
        CORS(self.app, 
             origins=self.config.api.cors_origins,
             allow_headers=['Content-Type', 'Authorization', 'X-API-Key', 'X-Correlation-ID'],
             expose_headers=['X-Correlation-ID', 'X-Rate-Limit-Remaining'])
    
    def _setup_middleware(self):
        """Set up middleware for logging, security, and monitoring."""
        
        # Rate limiting
        if self.config.security.enable_rate_limiting:
            if self.config.security.rate_limit_storage == 'redis':
                limiter = Limiter(
                    app=self.app,
                    key_func=get_remote_address,
                    storage_uri=os.getenv('REDIS_URL', 'redis://localhost:6379'),
                    default_limits=[self.config.api.rate_limit]
                )
            else:
                limiter = Limiter(
                    app=self.app,
                    key_func=get_remote_address,
                    default_limits=[self.config.api.rate_limit]
                )
        
        @self.app.before_request
        def before_request():
            """Pre-request middleware."""
            # Generate correlation ID
            g.correlation_id = request.headers.get('X-Correlation-ID', str(uuid.uuid4()))
            g.start_time = time.time()
            
            # Log incoming request
            self.logger.info("Incoming request",
                           method=request.method,
                           path=request.path,
                           remote_addr=request.remote_addr,
                           user_agent=request.headers.get('User-Agent', ''),
                           correlation_id=g.correlation_id)
            
            # API key authentication (if enabled)
            if self.config.security.enable_api_key_auth:
                if not self._validate_api_key():
                    self.security_logger.log_security_event(
                        'invalid_api_key',
                        'medium',
                        {'ip': request.remote_addr, 'path': request.path}
                    )
                    return jsonify({'error': 'Invalid API key'}), 401
            
            # Content type validation for POST/PUT requests
            if request.method in ['POST', 'PUT'] and request.content_type != 'application/json':
                return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        @self.app.after_request
        def after_request(response):
            """Post-request middleware."""
            # Calculate response time
            response_time = time.time() - g.start_time
            
            # Add correlation ID to response headers
            response.headers['X-Correlation-ID'] = g.correlation_id
            
            # Log API request metrics
            self.logger.log_api_request(
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                response_time=response_time,
                user_id=getattr(g, 'user_id', None)
            )
            
            # Record performance metrics
            self.db.record_performance_metric(
                f'api_request_{request.method.lower()}',
                response_time,
                'histogram',
                {'endpoint': request.path, 'status': response.status_code}
            )
            
            return response
    
    def _validate_api_key(self) -> bool:
        """Validate API key from request headers."""
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return False
        
        # Hash the provided key and compare with stored hashes
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        return api_key_hash in [hashlib.sha256(key.encode()).hexdigest() 
                               for key in self.config.security.api_keys]
    
    def _setup_error_handlers(self):
        """Set up global error handlers."""
        
        @self.app.errorhandler(400)
        def bad_request(error):
            return jsonify({
                'error': 'Bad request',
                'message': str(error.description),
                'correlation_id': getattr(g, 'correlation_id', None)
            }), 400
        
        @self.app.errorhandler(401)
        def unauthorized(error):
            return jsonify({
                'error': 'Unauthorized',
                'correlation_id': getattr(g, 'correlation_id', None)
            }), 401
        
        @self.app.errorhandler(403)
        def forbidden(error):
            return jsonify({
                'error': 'Forbidden',
                'correlation_id': getattr(g, 'correlation_id', None)
            }), 403
        
        @self.app.errorhandler(404)
        def not_found(error):
            return jsonify({
                'error': 'Not found',
                'correlation_id': getattr(g, 'correlation_id', None)
            }), 404
        
        @self.app.errorhandler(429)
        def rate_limit_exceeded(error):
            self.security_logger.log_security_event(
                'rate_limit_exceeded',
                'low',
                {'ip': request.remote_addr, 'path': request.path}
            )
            return jsonify({
                'error': 'Rate limit exceeded',
                'message': str(error.description),
                'correlation_id': getattr(g, 'correlation_id', None)
            }), 429
        
        @self.app.errorhandler(500)
        def internal_error(error):
            self.logger.error("Internal server error",
                            error=str(error),
                            traceback=traceback.format_exc(),
                            correlation_id=getattr(g, 'correlation_id', None))
            return jsonify({
                'error': 'Internal server error',
                'correlation_id': getattr(g, 'correlation_id', None)
            }), 500
    
    def _validate_request_data(self, required_fields: List[str], 
                              optional_fields: List[str] = None) -> Dict[str, Any]:
        """Validate and sanitize request data."""
        if not request.is_json:
            raise ValueError("Request must be JSON")
        
        data = request.get_json()
        if not data:
            raise ValueError("Request body cannot be empty")
        
        # Check required fields
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
        
        # Sanitize and validate data
        validated_data = {}
        all_fields = required_fields + (optional_fields or [])
        
        for field in all_fields:
            if field in data:
                value = data[field]
                
                # Basic sanitization
                if isinstance(value, str):
                    value = value.strip()
                    
                    # Validate field-specific constraints
                    if field == 'wallet_address':
                        if len(value) > self.config.security.max_wallet_address_length:
                            raise ValueError("Wallet address too long")
                        if not value.startswith(('UQ', 'EQ', '0:')):
                            raise ValueError("Invalid wallet address format")
                    
                    elif field == 'telegram_id':
                        if len(value) > self.config.security.max_telegram_id_length:
                            raise ValueError("Telegram ID too long")
                
                validated_data[field] = value
        
        return validated_data
    
    def _setup_routes(self):
        """Set up API routes."""
        
        @self.app.route('/api/health', methods=['GET'])
        @log_performance("health_check")
        def health_check():
            """Comprehensive health check endpoint."""
            try:
                # Check database health
                db_health = self.db.get_health_status()
                
                # Check system resources
                health_status = {
                    'status': 'healthy',
                    'timestamp': datetime.utcnow().isoformat(),
                    'version': self.config.version,
                    'build': self.config.build_number,
                    'environment': self.config.environment,
                    'database': db_health,
                    'api': {
                        'status': 'healthy',
                        'uptime_seconds': time.time() - getattr(self, '_start_time', time.time())
                    },
                    'correlation_id': g.correlation_id
                }
                
                # Determine overall health
                if db_health.get('db_status') != 'healthy':
                    health_status['status'] = 'degraded'
                
                status_code = 200 if health_status['status'] == 'healthy' else 503
                return jsonify(health_status), status_code
            
            except Exception as e:
                self.logger.error("Health check failed", error=str(e))
                return jsonify({
                    'status': 'unhealthy',
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat(),
                    'correlation_id': g.correlation_id
                }), 503
        
        @self.app.route('/api/users/create', methods=['POST'])
        @log_performance("create_user")
        def create_user():
            """Create a new user with wallet address."""
            try:
                # Validate request data
                data = self._validate_request_data(['wallet_address', 'telegram_id'])
                
                wallet_address = data['wallet_address']
                telegram_id = data['telegram_id']
                
                self.logger.info("Creating user", 
                               telegram_id=telegram_id, 
                               wallet_address=wallet_address)
                
                # Check if user already exists
                existing_user = self.db.execute_query(
                    "SELECT id FROM users WHERE telegram_id = ?",
                    (telegram_id,),
                    fetch_one=True
                )
                
                if existing_user:
                    self.logger.info("User already exists", 
                                   user_id=existing_user['id'],
                                   telegram_id=telegram_id)
                    return jsonify({
                        'success': True,
                        'message': 'User already exists',
                        'user_id': existing_user['id'],
                        'telegram_id': telegram_id,
                        'wallet_address': wallet_address,
                        'correlation_id': g.correlation_id
                    }), 200
                
                # Generate address variants
                try:
                    address_variants = get_mainnet_variants(wallet_address)
                except Exception as e:
                    self.logger.warning("Failed to generate address variants", 
                                      error=str(e), 
                                      wallet_address=wallet_address)
                    address_variants = {
                        'main': wallet_address,
                        'variant_1': wallet_address,
                        'variant_2': wallet_address,
                        'variant_3': wallet_address,
                        'variant_4': wallet_address
                    }
                
                # Create user
                user_id = self.db.execute_query(
                    """INSERT INTO users (telegram_id, main_wallet_address)
                       VALUES (?, ?)""",
                    (telegram_id, wallet_address)
                )
                
                # Store address variants in the variant_address columns
                try:
                    address_variants = get_mainnet_variants(wallet_address)
                    if address_variants and len(address_variants) >= 4:
                        # Update user with variant addresses
                        self.db.execute_query(
                            """UPDATE users 
                               SET variant_address_1 = ?, variant_address_2 = ?,
                                   variant_address_3 = ?, variant_address_4 = ?
                               WHERE id = ?""",
                            (address_variants.get('variant_1', wallet_address),
                             address_variants.get('variant_2', wallet_address),
                             address_variants.get('variant_3', wallet_address),
                             address_variants.get('variant_4', wallet_address),
                             user_id)
                        )
                except Exception as e:
                    self.logger.warning("Failed to generate address variants", 
                                      error=str(e), 
                                      wallet_address=wallet_address)
                    # Continue without variants
                
                # Initialize user balance
                self.db.execute_query(
                    "INSERT INTO user_balances (user_id, balance, available_balance) VALUES (?, 0, 0)",
                    (user_id,)
                )
                
                # Record audit event
                self.db.record_audit_event(
                    'user_created',
                    user_id=user_id,
                    entity_type='user',
                    entity_id=user_id,
                    new_values={'telegram_id': telegram_id, 'wallet_address': wallet_address},
                    correlation_id=g.correlation_id
                )
                
                # Log user creation
                self.logger.log_user_created(user_id, telegram_id, wallet_address)
                
                g.user_id = user_id  # For response logging
                
                return jsonify({
                    'success': True,
                    'message': 'User created successfully',
                    'user_id': user_id,
                    'telegram_id': telegram_id,
                    'wallet_address': wallet_address,
                    'variants': address_variants,
                    'correlation_id': g.correlation_id
                }), 201
            
            except ValueError as e:
                self.logger.warning("Invalid user creation request", error=str(e))
                return jsonify({
                    'success': False,
                    'error': str(e),
                    'correlation_id': g.correlation_id
                }), 400
            
            except Exception as e:
                self.logger.error("User creation failed", error=str(e))
                return jsonify({
                    'success': False,
                    'error': 'Internal server error',
                    'correlation_id': g.correlation_id
                }), 500
        
        @self.app.route('/api/balance/wallet/<path:wallet_address>', methods=['GET'])
        @log_performance("get_balance_by_wallet")
        def get_balance_by_wallet(wallet_address: str):
            """Get user balance by wallet address."""
            try:
                self.logger.info("Getting balance by wallet", wallet_address=wallet_address)

                # Find user by wallet address (current database schema doesn't have user_address_variants table)
                user_data = self.db.execute_query(
                    """SELECT u.id, u.telegram_id, u.main_wallet_address,
                              ub.balance, ub.available_balance, ub.locked_balance
                       FROM users u
                       LEFT JOIN user_balances ub ON u.id = ub.user_id
                       WHERE u.main_wallet_address = ?""",
                    (wallet_address,),
                    fetch_one=True
                )

                if not user_data:
                    # Try variant addresses as fallback
                    user_data = self.db.execute_query(
                        """SELECT u.id, u.telegram_id, u.main_wallet_address,
                                  ub.balance, ub.available_balance, ub.locked_balance
                           FROM users u
                           LEFT JOIN user_balances ub ON u.id = ub.user_id
                           WHERE u.variant_address_1 = ? OR u.variant_address_2 = ?
                              OR u.variant_address_3 = ? OR u.variant_address_4 = ?""",
                        (wallet_address, wallet_address, wallet_address, wallet_address),
                        fetch_one=True
                    )

                if not user_data:
                    return jsonify({
                        'success': False,
                        'error': 'Wallet address not found',
                        'correlation_id': g.correlation_id
                    }), 404

                g.user_id = user_data['id']  # For response logging

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
                self.logger.error("Failed to get balance by wallet",
                                error=str(e),
                                wallet_address=wallet_address)
                return jsonify({
                    'success': False,
                    'error': 'Internal server error',
                    'correlation_id': g.correlation_id
                }), 500
        
        @self.app.route('/api/users/<int:user_id>/transactions', methods=['GET'])
        @log_performance("get_user_transactions")
        def get_user_transactions(user_id: int):
            """Get user transaction history."""
            try:
                # Pagination parameters
                page = request.args.get('page', 1, type=int)
                per_page = min(request.args.get('per_page', 50, type=int), 100)  # Max 100 per page
                offset = (page - 1) * per_page
                
                # Get transactions
                transactions = self.db.execute_query(
                    """SELECT tx_hash, from_address, to_address, amount, fee,
                              transaction_time, processed_at, status, block_height
                       FROM transactions 
                       WHERE user_id = ? 
                       ORDER BY processed_at DESC 
                       LIMIT ? OFFSET ?""",
                    (user_id, per_page, offset),
                    fetch_all=True
                )
                
                # Get total count
                total_count = self.db.execute_query(
                    "SELECT COUNT(*) as count FROM transactions WHERE user_id = ?",
                    (user_id,),
                    fetch_one=True
                )['count']
                
                g.user_id = user_id  # For response logging
                
                return jsonify({
                    'success': True,
                    'transactions': [dict(tx) for tx in transactions],
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total': total_count,
                        'pages': (total_count + per_page - 1) // per_page
                    },
                    'correlation_id': g.correlation_id
                }), 200
            
            except Exception as e:
                self.logger.error("Failed to get user transactions", 
                                error=str(e), 
                                user_id=user_id)
                return jsonify({
                    'success': False,
                    'error': 'Internal server error',
                    'correlation_id': g.correlation_id
                }), 500
        
        @self.app.route('/api/metrics', methods=['GET'])
        @log_performance("get_metrics")
        def get_metrics():
            """Get system metrics (Prometheus format)."""
            try:
                # Get recent performance metrics
                metrics = self.db.execute_query(
                    """SELECT metric_name, AVG(metric_value) as avg_value, 
                              COUNT(*) as count, MAX(recorded_at) as last_recorded
                       FROM performance_metrics 
                       WHERE recorded_at > datetime('now', '-1 hour')
                       GROUP BY metric_name""",
                    fetch_all=True
                )
                
                # Format as Prometheus metrics
                prometheus_output = []
                for metric in metrics:
                    prometheus_output.append(
                        f"# HELP {metric['metric_name']} Average value over last hour"
                    )
                    prometheus_output.append(
                        f"# TYPE {metric['metric_name']} gauge"
                    )
                    prometheus_output.append(
                        f"{metric['metric_name']} {metric['avg_value']}"
                    )
                    prometheus_output.append("")
                
                return '\n'.join(prometheus_output), 200, {'Content-Type': 'text/plain'}
            
            except Exception as e:
                self.logger.error("Failed to get metrics", error=str(e))
                return "# Error getting metrics\n", 500, {'Content-Type': 'text/plain'}
    
    def run(self):
        """Run the production server."""
        self._start_time = time.time()
        
        self.logger.info("Starting Nova TON Monitor API Server",
                        host=self.config.api.host,
                        port=self.config.api.port,
                        environment=self.config.environment,
                        version=self.config.version)
        
        if self.config.security.ssl_cert_path and self.config.security.ssl_key_path:
            # Run with SSL
            self.app.run(
                host=self.config.api.host,
                port=self.config.api.port,
                debug=self.config.api.debug,
                ssl_context=(self.config.security.ssl_cert_path, self.config.security.ssl_key_path),
                threaded=True
            )
        else:
            # Run without SSL
            self.app.run(
                host=self.config.api.host,
                port=self.config.api.port,
                debug=self.config.api.debug,
                threaded=True
            )

def create_production_server(config=None) -> ProductionAPIServer:
    """Factory function to create production API server."""
    return ProductionAPIServer(config)

if __name__ == '__main__':
    server = create_production_server()
    server.run()
