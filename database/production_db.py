#!/usr/bin/env python3
"""
🗄️ Production Database Manager for Nova TON Monitor
Connection pooling, failover, migrations, and monitoring
"""

import sqlite3
import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
import threading
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
from contextlib import contextmanager
import os
import hashlib

from ..utils.production_logger import LoggerFactory, log_performance, log_errors
from ..config.production import get_config

class DatabaseError(Exception):
    """Custom database exception."""
    pass

class ConnectionPoolError(DatabaseError):
    """Connection pool related errors."""
    pass

class ProductionDatabase:
    """Production-ready database manager with advanced features."""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.logger = LoggerFactory.get_database_logger()
        self._connection_pool = None
        self._sqlite_connection = None
        self._lock = threading.RLock()
        self._health_check_thread = None
        self._stop_health_check = False
        
        self._initialize_database()
        self._start_health_monitoring()
    
    def _initialize_database(self):
        """Initialize database connection and schema."""
        try:
            if self.config.database.use_sqlite:
                self._initialize_sqlite()
            else:
                self._initialize_postgresql()
            
            self._ensure_schema()
            self.logger.info("Database initialized successfully", 
                           database_type="sqlite" if self.config.database.use_sqlite else "postgresql")
        
        except Exception as e:
            self.logger.error("Failed to initialize database", error=str(e))
            raise DatabaseError(f"Database initialization failed: {e}")
    
    def _initialize_sqlite(self):
        """Initialize SQLite database."""
        os.makedirs(os.path.dirname(self.config.database.sqlite_path), exist_ok=True)
        
        self._sqlite_connection = sqlite3.connect(
            self.config.database.sqlite_path,
            check_same_thread=False,
            timeout=self.config.database.connection_timeout
        )
        self._sqlite_connection.row_factory = sqlite3.Row
        
        # Enable WAL mode for better concurrency
        self._sqlite_connection.execute("PRAGMA journal_mode=WAL")
        self._sqlite_connection.execute("PRAGMA synchronous=NORMAL")
        self._sqlite_connection.execute("PRAGMA cache_size=10000")
        self._sqlite_connection.execute("PRAGMA temp_store=MEMORY")
        self._sqlite_connection.commit()
    
    def _initialize_postgresql(self):
        """Initialize PostgreSQL connection pool."""
        try:
            self._connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=self.config.database.max_connections,
                host=self.config.database.host,
                port=self.config.database.port,
                database=self.config.database.name,
                user=self.config.database.user,
                password=self.config.database.password,
                sslmode=self.config.database.ssl_mode,
                cursor_factory=RealDictCursor
            )
        except Exception as e:
            self.logger.error("Failed to create PostgreSQL connection pool", error=str(e))
            raise ConnectionPoolError(f"Connection pool creation failed: {e}")
    
    @contextmanager
    def get_connection(self):
        """Get database connection with automatic cleanup."""
        connection = None
        try:
            if self.config.database.use_sqlite:
                connection = self._sqlite_connection
                yield connection
            else:
                connection = self._connection_pool.getconn()
                if connection.closed:
                    self._connection_pool.putconn(connection, close=True)
                    connection = self._connection_pool.getconn()
                yield connection
        
        except Exception as e:
            if connection and not self.config.database.use_sqlite:
                connection.rollback()
            self.logger.error("Database connection error", error=str(e))
            raise
        
        finally:
            if connection and not self.config.database.use_sqlite:
                self._connection_pool.putconn(connection)
    
    @contextmanager
    def get_cursor(self, commit=True):
        """Get database cursor with transaction management."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                yield cursor
                if commit:
                    conn.commit()
            except Exception as e:
                conn.rollback()
                self.logger.error("Database transaction error", error=str(e))
                raise
            finally:
                cursor.close()
    
    def _ensure_schema(self):
        """Ensure database schema is up to date."""
        schema_version = self._get_schema_version()
        latest_version = self._get_latest_schema_version()
        
        if schema_version < latest_version:
            self.logger.info("Running database migrations", 
                           current_version=schema_version, 
                           target_version=latest_version)
            self._run_migrations(schema_version, latest_version)
    
    def _get_schema_version(self) -> int:
        """Get current schema version."""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
                result = cursor.fetchone()
                return result[0] if result else 0
        except:
            return 0
    
    def _get_latest_schema_version(self) -> int:
        """Get latest available schema version."""
        # This would typically read from migration files
        return 1  # Current version
    
    def _run_migrations(self, from_version: int, to_version: int):
        """Run database migrations."""
        migrations = self._get_migrations(from_version, to_version)
        
        for migration in migrations:
            try:
                with self.get_cursor() as cursor:
                    self.logger.info("Running migration", migration_version=migration['version'])
                    cursor.execute(migration['sql'])
                    
                    # Update schema version
                    cursor.execute(
                        "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
                        (migration['version'], datetime.utcnow().isoformat())
                    )
                
                self.logger.info("Migration completed", migration_version=migration['version'])
            
            except Exception as e:
                self.logger.error("Migration failed", 
                                migration_version=migration['version'], 
                                error=str(e))
                raise DatabaseError(f"Migration {migration['version']} failed: {e}")
    
    def _get_migrations(self, from_version: int, to_version: int) -> List[Dict]:
        """Get migration scripts between versions."""
        # This is a simplified version - in production, you'd read from files
        migrations = []
        
        if from_version < 1:
            migrations.append({
                'version': 1,
                'sql': self._get_initial_schema()
            })
        
        return migrations
    
    def _get_initial_schema(self) -> str:
        """Get initial database schema."""
        return """
        -- Schema version tracking
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        
        -- Users table with enhanced fields
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id TEXT UNIQUE NOT NULL,
            main_wallet_address TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            status TEXT DEFAULT 'active',
            metadata TEXT DEFAULT '{}',
            last_activity_at TEXT,
            total_deposited REAL DEFAULT 0,
            total_withdrawn REAL DEFAULT 0,
            transaction_count INTEGER DEFAULT 0
        );
        
        -- User address variants for TON address normalization
        CREATE TABLE IF NOT EXISTS user_address_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            address_variant TEXT NOT NULL,
            variant_type TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            UNIQUE(user_id, address_variant)
        );
        
        -- Enhanced transactions table
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            tx_hash TEXT UNIQUE NOT NULL,
            from_address TEXT NOT NULL,
            to_address TEXT NOT NULL,
            amount REAL NOT NULL,
            fee REAL DEFAULT 0,
            logical_time INTEGER,
            transaction_time TEXT,
            processed_at TEXT DEFAULT (datetime('now')),
            status TEXT DEFAULT 'confirmed',
            block_hash TEXT,
            block_height INTEGER,
            message_hash TEXT,
            metadata TEXT DEFAULT '{}',
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        );
        
        -- User balances with audit trail
        CREATE TABLE IF NOT EXISTS user_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            balance REAL NOT NULL DEFAULT 0,
            available_balance REAL NOT NULL DEFAULT 0,
            locked_balance REAL NOT NULL DEFAULT 0,
            last_updated TEXT DEFAULT (datetime('now')),
            last_transaction_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (last_transaction_id) REFERENCES transactions (id)
        );
        
        -- System status and monitoring
        CREATE TABLE IF NOT EXISTS system_status (
            id INTEGER PRIMARY KEY DEFAULT 1,
            last_check_at TEXT DEFAULT (datetime('now')),
            last_logical_time INTEGER,
            db_status TEXT DEFAULT 'healthy',
            api_status TEXT DEFAULT 'healthy',
            monitor_status TEXT DEFAULT 'healthy',
            error_count INTEGER DEFAULT 0,
            last_error TEXT,
            metadata TEXT DEFAULT '{}',
            CHECK (id = 1)
        );
        
        -- Audit log for important events
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            user_id INTEGER,
            entity_type TEXT,
            entity_id INTEGER,
            old_values TEXT,
            new_values TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            ip_address TEXT,
            user_agent TEXT,
            correlation_id TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        );
        
        -- Performance metrics
        CREATE TABLE IF NOT EXISTS performance_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            metric_type TEXT NOT NULL,
            tags TEXT DEFAULT '{}',
            recorded_at TEXT DEFAULT (datetime('now'))
        );
        
        -- Create indexes for performance
        CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users (telegram_id);
        CREATE INDEX IF NOT EXISTS idx_users_wallet_address ON users (main_wallet_address);
        CREATE INDEX IF NOT EXISTS idx_users_status ON users (status);
        CREATE INDEX IF NOT EXISTS idx_users_created_at ON users (created_at);
        
        CREATE INDEX IF NOT EXISTS idx_user_address_variants_user_id ON user_address_variants (user_id);
        CREATE INDEX IF NOT EXISTS idx_user_address_variants_address ON user_address_variants (address_variant);
        
        CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions (user_id);
        CREATE INDEX IF NOT EXISTS idx_transactions_hash ON transactions (tx_hash);
        CREATE INDEX IF NOT EXISTS idx_transactions_from_address ON transactions (from_address);
        CREATE INDEX IF NOT EXISTS idx_transactions_to_address ON transactions (to_address);
        CREATE INDEX IF NOT EXISTS idx_transactions_logical_time ON transactions (logical_time);
        CREATE INDEX IF NOT EXISTS idx_transactions_processed_at ON transactions (processed_at);
        CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions (status);
        
        CREATE INDEX IF NOT EXISTS idx_user_balances_user_id ON user_balances (user_id);
        CREATE INDEX IF NOT EXISTS idx_user_balances_updated ON user_balances (last_updated);
        
        CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON audit_log (event_type);
        CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log (user_id);
        CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log (created_at);
        CREATE INDEX IF NOT EXISTS idx_audit_log_correlation_id ON audit_log (correlation_id);
        
        CREATE INDEX IF NOT EXISTS idx_performance_metrics_name ON performance_metrics (metric_name);
        CREATE INDEX IF NOT EXISTS idx_performance_metrics_recorded_at ON performance_metrics (recorded_at);
        
        -- Insert initial system status
        INSERT OR IGNORE INTO system_status (id, db_status) VALUES (1, 'healthy');
        """
    
    @log_performance("database_query")
    @log_errors("nova.database")
    def execute_query(self, query: str, params: tuple = None, fetch_one: bool = False, 
                     fetch_all: bool = False) -> Union[sqlite3.Row, List[sqlite3.Row], None]:
        """Execute a database query with error handling and logging."""
        start_time = time.time()
        
        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, params or ())
                
                if fetch_one:
                    result = cursor.fetchone()
                elif fetch_all:
                    result = cursor.fetchall()
                else:
                    result = cursor.rowcount
                
                query_time = time.time() - start_time
                self.logger.debug("Query executed", 
                                query=query[:100], 
                                execution_time_ms=query_time * 1000,
                                rows_affected=cursor.rowcount if not (fetch_one or fetch_all) else len(result) if result else 0)
                
                return result
        
        except Exception as e:
            query_time = time.time() - start_time
            self.logger.error("Query execution failed", 
                            query=query[:100], 
                            error=str(e),
                            execution_time_ms=query_time * 1000)
            raise DatabaseError(f"Query execution failed: {e}")
    
    def _start_health_monitoring(self):
        """Start background health monitoring."""
        def health_check_worker():
            while not self._stop_health_check:
                try:
                    self._perform_health_check()
                    time.sleep(60)  # Check every minute
                except Exception as e:
                    self.logger.error("Health check failed", error=str(e))
                    time.sleep(60)
        
        self._health_check_thread = threading.Thread(target=health_check_worker, daemon=True)
        self._health_check_thread.start()
    
    def _perform_health_check(self):
        """Perform database health check."""
        try:
            # Test basic connectivity
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                
                if result:
                    # Update system status
                    cursor.execute(
                        "UPDATE system_status SET last_check_at = ?, db_status = ? WHERE id = 1",
                        (datetime.utcnow().isoformat(), 'healthy')
                    )
                    
                    # Log health metrics
                    self.logger.debug("Database health check passed")
                else:
                    raise DatabaseError("Health check query returned no result")
        
        except Exception as e:
            self.logger.error("Database health check failed", error=str(e))
            
            # Update system status
            try:
                with self.get_cursor() as cursor:
                    cursor.execute(
                        "UPDATE system_status SET last_check_at = ?, db_status = ?, last_error = ? WHERE id = 1",
                        (datetime.utcnow().isoformat(), 'unhealthy', str(e))
                    )
            except:
                pass  # Don't fail if we can't update status
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current database health status."""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT * FROM system_status WHERE id = 1")
                status = cursor.fetchone()
                
                if status:
                    return dict(status)
                else:
                    return {'db_status': 'unknown', 'last_check_at': None}
        
        except Exception as e:
            self.logger.error("Failed to get health status", error=str(e))
            return {'db_status': 'error', 'error': str(e)}
    
    def record_audit_event(self, event_type: str, user_id: Optional[int] = None,
                          entity_type: Optional[str] = None, entity_id: Optional[int] = None,
                          old_values: Optional[Dict] = None, new_values: Optional[Dict] = None,
                          correlation_id: Optional[str] = None):
        """Record audit event."""
        try:
            self.execute_query(
                """INSERT INTO audit_log 
                   (event_type, user_id, entity_type, entity_id, old_values, new_values, correlation_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (event_type, user_id, entity_type, entity_id,
                 json.dumps(old_values) if old_values else None,
                 json.dumps(new_values) if new_values else None,
                 correlation_id)
            )
        except Exception as e:
            self.logger.error("Failed to record audit event", error=str(e))
    
    def record_performance_metric(self, metric_name: str, metric_value: float,
                                metric_type: str = 'gauge', tags: Optional[Dict] = None):
        """Record performance metric."""
        try:
            self.execute_query(
                "INSERT INTO performance_metrics (metric_name, metric_value, metric_type, tags) VALUES (?, ?, ?, ?)",
                (metric_name, metric_value, metric_type, json.dumps(tags or {}))
            )
        except Exception as e:
            self.logger.error("Failed to record performance metric", error=str(e))
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old data to prevent database bloat."""
        cutoff_date = (datetime.utcnow() - timedelta(days=days_to_keep)).isoformat()
        
        try:
            # Clean up old audit logs
            deleted_audit = self.execute_query(
                "DELETE FROM audit_log WHERE created_at < ?",
                (cutoff_date,)
            )
            
            # Clean up old performance metrics
            deleted_metrics = self.execute_query(
                "DELETE FROM performance_metrics WHERE recorded_at < ?",
                (cutoff_date,)
            )
            
            self.logger.info("Database cleanup completed", 
                           deleted_audit_records=deleted_audit,
                           deleted_metric_records=deleted_metrics)
        
        except Exception as e:
            self.logger.error("Database cleanup failed", error=str(e))
    
    def close(self):
        """Close database connections and stop monitoring."""
        self._stop_health_check = True
        
        if self._health_check_thread and self._health_check_thread.is_alive():
            self._health_check_thread.join(timeout=5)
        
        if self._connection_pool:
            self._connection_pool.closeall()
        
        if self._sqlite_connection:
            self._sqlite_connection.close()
        
        self.logger.info("Database connections closed")

# Global database instance
_db_instance = None
_db_lock = threading.Lock()

def get_database() -> ProductionDatabase:
    """Get global database instance (singleton)."""
    global _db_instance
    
    if _db_instance is None:
        with _db_lock:
            if _db_instance is None:
                _db_instance = ProductionDatabase()
    
    return _db_instance
