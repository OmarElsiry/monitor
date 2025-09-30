#!/usr/bin/env python3
"""
🏭 Production Configuration for Nova TON Monitor
Secure, scalable configuration for production deployment
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
import json

@dataclass
class DatabaseConfig:
    """Database configuration with connection pooling and failover."""
    host: str = os.getenv('DB_HOST', 'localhost')
    port: int = int(os.getenv('DB_PORT', '5432'))
    name: str = os.getenv('DB_NAME', 'nova_ton_monitor')
    user: str = os.getenv('DB_USER', 'nova_user')
    password: str = os.getenv('DB_PASSWORD', '')
    ssl_mode: str = os.getenv('DB_SSL_MODE', 'require')
    max_connections: int = int(os.getenv('DB_MAX_CONNECTIONS', '20'))
    connection_timeout: int = int(os.getenv('DB_CONNECTION_TIMEOUT', '30'))
    
    # SQLite fallback for development
    sqlite_path: str = os.getenv('SQLITE_PATH', './data/NovaTonMonitor.db')
    use_sqlite: bool = os.getenv('USE_SQLITE', 'false').lower() == 'true'

@dataclass
class TONConfig:
    """TON blockchain configuration."""
    mainnet_endpoint: str = os.getenv('TON_MAINNET_ENDPOINT', 'https://toncenter.com/api/v2/jsonRPC')
    testnet_endpoint: str = os.getenv('TON_TESTNET_ENDPOINT', 'https://testnet.toncenter.com/api/v2/jsonRPC')
    api_key: str = os.getenv('TON_API_KEY', '')
    network: str = os.getenv('TON_NETWORK', 'mainnet')  # mainnet or testnet
    request_timeout: int = int(os.getenv('TON_REQUEST_TIMEOUT', '30'))
    max_retries: int = int(os.getenv('TON_MAX_RETRIES', '3'))
    retry_delay: int = int(os.getenv('TON_RETRY_DELAY', '5'))

@dataclass
class APIConfig:
    """API server configuration."""
    host: str = os.getenv('API_HOST', '0.0.0.0')
    port: int = int(os.getenv('API_PORT', '5001'))
    debug: bool = os.getenv('API_DEBUG', 'false').lower() == 'true'
    cors_origins: list = json.loads(os.getenv('CORS_ORIGINS', '["http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://localhost:3003", "http://localhost:3004"]'))
    rate_limit: str = os.getenv('API_RATE_LIMIT', '100 per minute')
    max_content_length: int = int(os.getenv('API_MAX_CONTENT_LENGTH', '1048576'))  # 1MB
    
    # Security
    secret_key: str = os.getenv('API_SECRET_KEY', os.urandom(32).hex())
    jwt_secret: str = os.getenv('JWT_SECRET', os.urandom(32).hex())
    jwt_expiry_hours: int = int(os.getenv('JWT_EXPIRY_HOURS', '24'))

@dataclass
class MonitoringConfig:
    """Monitoring and alerting configuration."""
    check_interval: int = int(os.getenv('MONITOR_CHECK_INTERVAL', '30'))  # seconds
    max_transaction_age: int = int(os.getenv('MONITOR_MAX_TX_AGE', '3600'))  # seconds
    alert_webhook_url: Optional[str] = os.getenv('ALERT_WEBHOOK_URL')
    metrics_port: int = int(os.getenv('METRICS_PORT', '9090'))
    health_check_port: int = int(os.getenv('HEALTH_CHECK_PORT', '8080'))
    
    # Telegram notifications
    telegram_bot_token: Optional[str] = os.getenv('TELEGRAM_BOT_TOKEN')
    telegram_chat_id: Optional[str] = os.getenv('TELEGRAM_CHAT_ID')

@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = os.getenv('LOG_LEVEL', 'INFO')
    format: str = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_path: Optional[str] = os.getenv('LOG_FILE_PATH', './logs/nova_monitor.log')
    max_file_size: int = int(os.getenv('LOG_MAX_FILE_SIZE', '10485760'))  # 10MB
    backup_count: int = int(os.getenv('LOG_BACKUP_COUNT', '5'))
    
    # Structured logging
    json_format: bool = os.getenv('LOG_JSON_FORMAT', 'false').lower() == 'true'
    include_trace_id: bool = os.getenv('LOG_INCLUDE_TRACE_ID', 'true').lower() == 'true'

@dataclass
class SecurityConfig:
    """Security configuration."""
    # API Security
    enable_api_key_auth: bool = os.getenv('ENABLE_API_KEY_AUTH', 'false').lower() == 'true'
    api_keys: list = json.loads(os.getenv('API_KEYS', '[]'))
    
    # Rate limiting
    enable_rate_limiting: bool = os.getenv('ENABLE_RATE_LIMITING', 'true').lower() == 'true'
    rate_limit_storage: str = os.getenv('RATE_LIMIT_STORAGE', 'memory')  # memory or redis
    
    # HTTPS
    ssl_cert_path: Optional[str] = os.getenv('SSL_CERT_PATH')
    ssl_key_path: Optional[str] = os.getenv('SSL_KEY_PATH')
    force_https: bool = os.getenv('FORCE_HTTPS', 'false').lower() == 'true'
    
    # Input validation
    max_wallet_address_length: int = int(os.getenv('MAX_WALLET_ADDRESS_LENGTH', '100'))
    max_telegram_id_length: int = int(os.getenv('MAX_TELEGRAM_ID_LENGTH', '50'))

@dataclass
class PerformanceConfig:
    """Performance optimization configuration."""
    # Caching
    enable_caching: bool = os.getenv('ENABLE_CACHING', 'true').lower() == 'true'
    cache_ttl: int = int(os.getenv('CACHE_TTL', '300'))  # 5 minutes
    cache_backend: str = os.getenv('CACHE_BACKEND', 'memory')  # memory or redis
    
    # Database optimization
    db_connection_pool_size: int = int(os.getenv('DB_POOL_SIZE', '10'))
    db_query_timeout: int = int(os.getenv('DB_QUERY_TIMEOUT', '30'))
    
    # Background tasks
    worker_processes: int = int(os.getenv('WORKER_PROCESSES', '2'))
    max_concurrent_requests: int = int(os.getenv('MAX_CONCURRENT_REQUESTS', '100'))

class ProductionConfig:
    """Main production configuration class."""
    
    def __init__(self):
        self.database = DatabaseConfig()
        self.ton = TONConfig()
        self.api = APIConfig()
        self.monitoring = MonitoringConfig()
        self.logging = LoggingConfig()
        self.security = SecurityConfig()
        self.performance = PerformanceConfig()
        
        # Environment
        self.environment = os.getenv('ENVIRONMENT', 'production')
        self.version = os.getenv('APP_VERSION', '1.0.0')
        self.build_number = os.getenv('BUILD_NUMBER', 'unknown')
        
        self._validate_config()
    
    def _validate_config(self):
        """Validate critical configuration values."""
        errors = []
        
        # Database validation
        if not self.database.use_sqlite and not self.database.password:
            errors.append("Database password is required for production")
        
        # TON API validation
        if self.ton.network == 'mainnet' and not self.ton.api_key:
            errors.append("TON API key is required for mainnet")
        
        # Security validation
        if self.security.force_https and not (self.security.ssl_cert_path and self.security.ssl_key_path):
            errors.append("SSL certificate and key paths required when HTTPS is forced")
        
        # API validation
        if len(self.api.secret_key) < 32:
            errors.append("API secret key must be at least 32 characters")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {', '.join(errors)}")
    
    def get_database_url(self) -> str:
        """Get database connection URL."""
        if self.database.use_sqlite:
            return f"sqlite:///{self.database.sqlite_path}"
        
        return (
            f"postgresql://{self.database.user}:{self.database.password}"
            f"@{self.database.host}:{self.database.port}/{self.database.name}"
            f"?sslmode={self.database.ssl_mode}"
        )
    
    def get_ton_endpoint(self) -> str:
        """Get TON API endpoint based on network."""
        if self.ton.network == 'testnet':
            return self.ton.testnet_endpoint
        return self.ton.mainnet_endpoint
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary (excluding sensitive data)."""
        config_dict = {}
        
        for attr_name in dir(self):
            if not attr_name.startswith('_'):
                attr_value = getattr(self, attr_name)
                if hasattr(attr_value, '__dict__'):
                    # Convert dataclass to dict, excluding sensitive fields
                    section_dict = {}
                    for key, value in attr_value.__dict__.items():
                        if 'password' not in key.lower() and 'secret' not in key.lower() and 'key' not in key.lower():
                            section_dict[key] = value
                        else:
                            section_dict[key] = '***REDACTED***'
                    config_dict[attr_name] = section_dict
                elif not callable(attr_value):
                    config_dict[attr_name] = attr_value
        
        return config_dict

# Global configuration instance
config = ProductionConfig()

def get_config() -> ProductionConfig:
    """Get the global configuration instance."""
    return config

def reload_config():
    """Reload configuration from environment variables."""
    global config
    config = ProductionConfig()
    return config
