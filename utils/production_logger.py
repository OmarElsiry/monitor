#!/usr/bin/env python3
"""
📊 Production Logger for Nova TON Monitor
Structured logging with correlation IDs, metrics, and alerting
"""

import logging
import logging.handlers
import json
import time
import uuid
import traceback
import os
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import contextmanager
from threading import local
import sys

# Thread-local storage for correlation IDs
_local = local()

class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        """Format log record as structured JSON."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add correlation ID if available
        correlation_id = getattr(_local, 'correlation_id', None)
        if correlation_id:
            log_entry['correlation_id'] = correlation_id
        
        # Add extra fields
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add stack trace for errors
        if record.levelno >= logging.ERROR and not record.exc_info:
            log_entry['stack_trace'] = traceback.format_stack()
        
        return json.dumps(log_entry, ensure_ascii=False)

class ProductionLogger:
    """Production-ready logger with advanced features."""
    
    def __init__(self, name: str, config=None):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Set up logger with handlers and formatters."""
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Set log level
        log_level = getattr(logging, (self.config.logging.level if self.config else 'INFO').upper())
        self.logger.setLevel(log_level)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        if self.config and self.config.logging.json_format:
            console_handler.setFormatter(StructuredFormatter())
        else:
            console_formatter = logging.Formatter(
                self.config.logging.format if self.config else 
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
        
        self.logger.addHandler(console_handler)
        
        # File handler (if configured)
        if self.config and self.config.logging.file_path:
            os.makedirs(os.path.dirname(self.config.logging.file_path), exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                self.config.logging.file_path,
                maxBytes=self.config.logging.max_file_size,
                backupCount=self.config.logging.backup_count
            )
            
            if self.config.logging.json_format:
                file_handler.setFormatter(StructuredFormatter())
            else:
                file_formatter = logging.Formatter(self.config.logging.format)
                file_handler.setFormatter(file_formatter)
            
            self.logger.addHandler(file_handler)
    
    @contextmanager
    def correlation_context(self, correlation_id: Optional[str] = None):
        """Context manager for correlation ID tracking."""
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())
        
        old_correlation_id = getattr(_local, 'correlation_id', None)
        _local.correlation_id = correlation_id
        
        try:
            yield correlation_id
        finally:
            if old_correlation_id:
                _local.correlation_id = old_correlation_id
            else:
                if hasattr(_local, 'correlation_id'):
                    delattr(_local, 'correlation_id')
    
    def _log_with_extra(self, level: int, message: str, extra_fields: Optional[Dict[str, Any]] = None):
        """Log message with extra fields."""
        if extra_fields:
            # Create a custom LogRecord with extra fields
            record = self.logger.makeRecord(
                self.logger.name, level, __file__, 0, message, (), None
            )
            record.extra_fields = extra_fields
            self.logger.handle(record)
        else:
            self.logger.log(level, message)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log_with_extra(logging.DEBUG, message, kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log_with_extra(logging.INFO, message, kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log_with_extra(logging.WARNING, message, kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        self._log_with_extra(logging.ERROR, message, kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self._log_with_extra(logging.CRITICAL, message, kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log exception with traceback."""
        kwargs['exc_info'] = True
        self._log_with_extra(logging.ERROR, message, kwargs)
    
    # Business logic specific logging methods
    def log_api_request(self, method: str, path: str, status_code: int, 
                       response_time: float, user_id: Optional[str] = None):
        """Log API request with metrics."""
        self.info("API request processed", 
                 method=method, 
                 path=path, 
                 status_code=status_code, 
                 response_time_ms=response_time * 1000,
                 user_id=user_id,
                 event_type="api_request")
    
    def log_transaction_processed(self, tx_hash: str, wallet_address: str, 
                                amount: float, status: str):
        """Log transaction processing."""
        self.info("Transaction processed", 
                 tx_hash=tx_hash, 
                 wallet_address=wallet_address, 
                 amount=amount, 
                 status=status,
                 event_type="transaction_processed")
    
    def log_user_created(self, user_id: int, telegram_id: str, wallet_address: str):
        """Log user creation."""
        self.info("User created", 
                 user_id=user_id, 
                 telegram_id=telegram_id, 
                 wallet_address=wallet_address,
                 event_type="user_created")
    
    def log_balance_updated(self, user_id: int, old_balance: float, 
                          new_balance: float, reason: str):
        """Log balance update."""
        self.info("Balance updated", 
                 user_id=user_id, 
                 old_balance=old_balance, 
                 new_balance=new_balance, 
                 difference=new_balance - old_balance,
                 reason=reason,
                 event_type="balance_updated")
    
    def log_error_with_context(self, error: Exception, context: Dict[str, Any]):
        """Log error with additional context."""
        self.error(f"Error occurred: {str(error)}", 
                  error_type=type(error).__name__,
                  error_message=str(error),
                  context=context,
                  event_type="error")
    
    def log_performance_metric(self, operation: str, duration: float, 
                             success: bool, metadata: Optional[Dict] = None):
        """Log performance metrics."""
        self.info("Performance metric", 
                 operation=operation, 
                 duration_ms=duration * 1000, 
                 success=success,
                 metadata=metadata or {},
                 event_type="performance_metric")
    
    def log_security_event(self, event_type: str, severity: str, 
                          details: Dict[str, Any]):
        """Log security-related events."""
        self.warning("Security event", 
                    security_event_type=event_type, 
                    severity=severity, 
                    details=details,
                    event_type="security_event")

class LoggerFactory:
    """Factory for creating production loggers."""
    
    _loggers: Dict[str, ProductionLogger] = {}
    _config = None
    
    @classmethod
    def set_config(cls, config):
        """Set global configuration for all loggers."""
        cls._config = config
    
    @classmethod
    def get_logger(cls, name: str) -> ProductionLogger:
        """Get or create a logger instance."""
        if name not in cls._loggers:
            cls._loggers[name] = ProductionLogger(name, cls._config)
        return cls._loggers[name]
    
    @classmethod
    def get_api_logger(cls) -> ProductionLogger:
        """Get logger for API operations."""
        return cls.get_logger('nova.api')
    
    @classmethod
    def get_monitor_logger(cls) -> ProductionLogger:
        """Get logger for monitoring operations."""
        return cls.get_logger('nova.monitor')
    
    @classmethod
    def get_database_logger(cls) -> ProductionLogger:
        """Get logger for database operations."""
        return cls.get_logger('nova.database')
    
    @classmethod
    def get_security_logger(cls) -> ProductionLogger:
        """Get logger for security events."""
        return cls.get_logger('nova.security')

# Performance monitoring decorator
def log_performance(operation_name: str):
    """Decorator to log performance metrics."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = LoggerFactory.get_logger(f'nova.performance.{func.__module__}')
            start_time = time.time()
            success = True
            error = None
            
            try:
                with logger.correlation_context():
                    result = func(*args, **kwargs)
                    return result
            except Exception as e:
                success = False
                error = e
                raise
            finally:
                duration = time.time() - start_time
                logger.log_performance_metric(
                    operation=operation_name,
                    duration=duration,
                    success=success,
                    metadata={'function': func.__name__, 'error': str(error) if error else None}
                )
        
        return wrapper
    return decorator

# Error handling decorator
def log_errors(logger_name: str = None):
    """Decorator to log errors with context."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = LoggerFactory.get_logger(logger_name or f'nova.{func.__module__}')
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = {
                    'function': func.__name__,
                    'args': str(args)[:200],  # Truncate long args
                    'kwargs': str(kwargs)[:200]
                }
                logger.log_error_with_context(e, context)
                raise
        
        return wrapper
    return decorator
