#!/usr/bin/env python3
"""
🔄 Production TON Monitor for Nova
High-performance, fault-tolerant blockchain monitoring with advanced features
"""

import asyncio
import aiohttp
import time
import json
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
import threading
from concurrent.futures import ThreadPoolExecutor
import hashlib

from database.production_db import get_database
from utils.production_logger import LoggerFactory, log_performance, log_errors
from config.production import get_config
from utils.address_normalizer import get_mainnet_variants
from api.production_server import create_production_server

class ProductionTONMonitor:
    """Production-grade TON blockchain monitor with advanced features."""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.db = get_database()
        self.logger = LoggerFactory.get_monitor_logger()
        
        # Monitoring state
        self.is_running = False
        self.last_logical_time = 0
        self.processed_transactions: Set[str] = set()
        self.error_count = 0
        self.last_successful_check = None
        
        # Performance tracking
        self.check_count = 0
        self.total_transactions_processed = 0
        self.start_time = time.time()
        
        # Threading
        self.executor = ThreadPoolExecutor(max_workers=self.config.performance.worker_processes)
        self.api_server = None
        self.api_thread = None
        
        # Circuit breaker for external API calls
        self.circuit_breaker = {
            'failures': 0,
            'last_failure': None,
            'is_open': False
        }
        
        self._setup_signal_handlers()
        self._load_initial_state()
    
    def _setup_signal_handlers(self):
        """Set up graceful shutdown signal handlers."""
        def signal_handler(signum, frame):
            self.logger.info("Received shutdown signal", signal=signum)
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _load_initial_state(self):
        """Load initial monitoring state from database."""
        try:
            # Get last logical time
            status = self.db.execute_query(
                "SELECT last_logical_time FROM system_status WHERE id = 1",
                fetch_one=True
            )
            
            if status and status['last_logical_time']:
                self.last_logical_time = status['last_logical_time']
                self.logger.info("Loaded last logical time", logical_time=self.last_logical_time)
            
            # Load recent transaction hashes to avoid reprocessing
            recent_txs = self.db.execute_query(
                """SELECT tx_hash FROM transactions 
                   WHERE processed_at > datetime('now', '-1 hour')""",
                fetch_all=True
            )
            
            self.processed_transactions = {tx['tx_hash'] for tx in recent_txs}
            self.logger.info("Loaded recent transactions", count=len(self.processed_transactions))
        
        except Exception as e:
            self.logger.error("Failed to load initial state", error=str(e))
    
    def _update_system_status(self, status: str, error: Optional[str] = None):
        """Update system status in database."""
        try:
            self.db.execute_query(
                """UPDATE system_status 
                   SET last_check_at = ?, monitor_status = ?, last_logical_time = ?, 
                       error_count = ?, last_error = ?
                   WHERE id = 1""",
                (datetime.utcnow().isoformat(), status, self.last_logical_time, 
                 self.error_count, error)
            )
        except Exception as e:
            self.logger.error("Failed to update system status", error=str(e))
    
    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker allows requests."""
        if not self.circuit_breaker['is_open']:
            return True
        
        # Check if enough time has passed to try again (30 seconds)
        if (self.circuit_breaker['last_failure'] and 
            time.time() - self.circuit_breaker['last_failure'] > 30):
            self.circuit_breaker['is_open'] = False
            self.circuit_breaker['failures'] = 0
            self.logger.info("Circuit breaker reset")
            return True
        
        return False
    
    def _record_api_failure(self):
        """Record API failure for circuit breaker."""
        self.circuit_breaker['failures'] += 1
        self.circuit_breaker['last_failure'] = time.time()
        
        # Open circuit breaker after 3 failures
        if self.circuit_breaker['failures'] >= 3:
            self.circuit_breaker['is_open'] = True
            self.logger.warning("Circuit breaker opened due to repeated failures")
    
    def _record_api_success(self):
        """Record API success for circuit breaker."""
        self.circuit_breaker['failures'] = 0
        self.circuit_breaker['is_open'] = False
    
    @log_performance("fetch_transactions")
    async def _fetch_transactions(self, session: aiohttp.ClientSession, 
                                 address: str) -> Optional[List[Dict]]:
        """Fetch transactions from TON API with retry logic."""
        if not self._check_circuit_breaker():
            self.logger.warning("Circuit breaker is open, skipping API call")
            return None
        
        endpoint = self.config.get_ton_endpoint()
        
        params = {
            'method': 'getTransactions',
            'params': {
                'address': address,
                'limit': 100,
                'lt': self.last_logical_time,
                'hash': '',
                'to_lt': 0,
                'archival': True
            }
        }
        
        if self.config.ton.api_key:
            params['api_key'] = self.config.ton.api_key
        
        for attempt in range(self.config.ton.max_retries):
            try:
                async with session.post(
                    endpoint,
                    json=params,
                    timeout=aiohttp.ClientTimeout(total=self.config.ton.request_timeout)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('ok'):
                            self._record_api_success()
                            return data.get('result', [])
                        else:
                            self.logger.error("TON API error", error=data.get('error'))
                            self._record_api_failure()
                            return None
                    else:
                        self.logger.warning("TON API HTTP error", 
                                          status=response.status, 
                                          attempt=attempt + 1)
            
            except asyncio.TimeoutError:
                self.logger.warning("TON API timeout", attempt=attempt + 1)
            except Exception as e:
                self.logger.error("TON API request failed", error=str(e), attempt=attempt + 1)
            
            if attempt < self.config.ton.max_retries - 1:
                await asyncio.sleep(self.config.ton.retry_delay)
        
        self._record_api_failure()
        return None
    
    def _process_transaction(self, tx: Dict[str, Any], deposit_address: str) -> Optional[Dict]:
        """Process a single transaction and extract relevant information."""
        try:
            tx_hash = tx.get('transaction_id', {}).get('hash')
            if not tx_hash or tx_hash in self.processed_transactions:
                return None
            
            # Extract transaction details
            in_msg = tx.get('in_msg', {})
            if not in_msg:
                return None
            
            source = in_msg.get('source', '')
            destination = in_msg.get('destination', '')
            value = int(in_msg.get('value', 0))
            
            # Check if this is a deposit to our address
            if destination != deposit_address or value <= 0:
                return None
            
            # Convert nanotons to TON
            amount = value / 1_000_000_000
            
            # Extract additional details
            logical_time = tx.get('transaction_id', {}).get('lt', 0)
            transaction_time = tx.get('utime', 0)
            
            # Get fee information
            fee = 0
            if 'fee' in tx:
                fee = int(tx['fee']) / 1_000_000_000
            
            processed_tx = {
                'tx_hash': tx_hash,
                'from_address': source,
                'to_address': destination,
                'amount': amount,
                'fee': fee,
                'logical_time': logical_time,
                'transaction_time': datetime.fromtimestamp(transaction_time).isoformat(),
                'block_hash': tx.get('transaction_id', {}).get('hash', ''),
                'raw_data': json.dumps(tx)
            }
            
            self.processed_transactions.add(tx_hash)
            return processed_tx
        
        except Exception as e:
            self.logger.error("Failed to process transaction", error=str(e), tx_hash=tx.get('transaction_id', {}).get('hash'))
            return None
    
    def _find_user_by_transaction(self, tx: Dict[str, Any]) -> Optional[int]:
        """Find user associated with a transaction."""
        try:
            from_address = tx['from_address']

            # Try to find user by wallet address (current database schema uses direct address columns)
            user = self.db.execute_query(
                """SELECT id FROM users
                   WHERE main_wallet_address = ? OR variant_address_1 = ?
                      OR variant_address_2 = ? OR variant_address_3 = ?
                      OR variant_address_4 = ?""",
                (from_address, from_address, from_address, from_address, from_address),
                fetch_one=True
            )

            return user['id'] if user else None

        except Exception as e:
            self.logger.error("Failed to find user by transaction", error=str(e))
            return None
    
    def _store_transaction(self, tx: Dict[str, Any], user_id: Optional[int] = None):
        """Store transaction in database."""
        try:
            # Insert transaction (using current database schema)
            self.db.execute_query(
                """INSERT OR IGNORE INTO transactions
                   (user_id, hash, from_address, to_address, amount, fee,
                    logical_time, utime, block_number, status, memo, comment)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, tx['tx_hash'], tx['from_address'], tx['to_address'],
                 tx['amount'], tx['fee'], tx['logical_time'], tx['transaction_time'],
                 tx['block_hash'], 'confirmed', '', '')
            )

            # Update user balance if user found
            if user_id:
                self._update_user_balance(user_id, tx['amount'], tx['tx_hash'])

                # Log transaction processing
                self.logger.log_transaction_processed(
                    tx['tx_hash'], tx['from_address'], tx['amount'], 'confirmed'
                )

            # Record audit event
            self.db.record_audit_event(
                'transaction_processed',
                user_id=user_id,
                entity_type='transaction',
                new_values={'tx_hash': tx['tx_hash'], 'amount': tx['amount']}
            )

        except Exception as e:
            self.logger.error("Failed to store transaction", error=str(e), tx_hash=tx['tx_hash'])
    
    def _update_user_balance(self, user_id: int, amount: float, tx_hash: str):
        """Update user balance after deposit."""
        try:
            # Get current balance
            current_balance = self.db.execute_query(
                "SELECT balance FROM user_balances WHERE user_id = ?",
                (user_id,),
                fetch_one=True
            )
            
            old_balance = current_balance['balance'] if current_balance else 0
            new_balance = old_balance + amount
            
            # Update balance
            if current_balance:
                self.db.execute_query(
                    """UPDATE user_balances 
                       SET balance = ?, available_balance = ?, last_updated = ?
                       WHERE user_id = ?""",
                    (new_balance, new_balance, datetime.utcnow().isoformat(), user_id)
                )
            else:
                self.db.execute_query(
                    """INSERT INTO user_balances (user_id, balance, available_balance)
                       VALUES (?, ?, ?)""",
                    (user_id, new_balance, new_balance)
                )
            
            # Update user statistics (skip columns that don't exist in current schema)
            try:
                # Check if columns exist before updating
                cursor = self.db.get_connection()
                cursor.execute("PRAGMA table_info(users)")
                columns = [col['name'] for col in cursor.fetchall()]

                update_parts = []
                update_values = []

                if 'total_deposited' in columns:
                    update_parts.append("total_deposited = total_deposited + ?")
                    update_values.append(amount)

                if 'transaction_count' in columns:
                    update_parts.append("transaction_count = transaction_count + 1")
                    # No value needed for this

                if 'last_activity_at' in columns:
                    update_parts.append("last_activity_at = ?")
                    update_values.append(datetime.utcnow().isoformat())

                if update_parts:
                    query = f"UPDATE users SET {', '.join(update_parts)} WHERE id = ?"
                    self.db.execute_query(query, (*update_values, user_id))
            except Exception as e:
                self.logger.warning("Failed to update user statistics", error=str(e), user_id=user_id)
            
            # Log balance update
            self.logger.log_balance_updated(user_id, old_balance, new_balance, f'deposit:{tx_hash}')
        
        except Exception as e:
            self.logger.error("Failed to update user balance", error=str(e), user_id=user_id)
    
    @log_performance("monitor_check")
    async def _perform_monitoring_check(self):
        """Perform a single monitoring check."""
        try:
            deposit_address = self.config.monitoring.deposit_address or "UQDrY5iulWs_MyWTP9JSGedWBzlbeRmhCBoqsSaNiSLOs315"
            
            async with aiohttp.ClientSession() as session:
                # Fetch transactions
                transactions = await self._fetch_transactions(session, deposit_address)
                
                if transactions is None:
                    self.error_count += 1
                    return
                
                self.logger.info("Fetched transactions", count=len(transactions))
                
                # Process transactions
                new_transactions = 0
                new_deposits = 0
                
                for tx in transactions:
                    processed_tx = self._process_transaction(tx, deposit_address)
                    if processed_tx:
                        # Find associated user
                        user_id = self._find_user_by_transaction(processed_tx)
                        
                        # Store transaction
                        self._store_transaction(processed_tx, user_id)
                        
                        new_transactions += 1
                        if user_id:
                            new_deposits += 1
                        
                        # Update logical time
                        if processed_tx['logical_time'] > self.last_logical_time:
                            self.last_logical_time = processed_tx['logical_time']
                
                self.total_transactions_processed += new_transactions
                self.last_successful_check = datetime.utcnow()
                self.error_count = 0
                
                self.logger.info("Monitoring check completed",
                               new_transactions=new_transactions,
                               new_deposits=new_deposits,
                               logical_time=self.last_logical_time)
                
                # Update system status
                self._update_system_status('healthy')
                
                # Record performance metrics
                self.db.record_performance_metric('monitor_transactions_processed', new_transactions)
                self.db.record_performance_metric('monitor_deposits_processed', new_deposits)
        
        except Exception as e:
            self.error_count += 1
            self.logger.error("Monitoring check failed", error=str(e))
            self._update_system_status('error', str(e))
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        self.logger.info("Starting monitoring loop",
                        check_interval=self.config.monitoring.check_interval)
        
        while self.is_running:
            try:
                start_time = time.time()
                
                await self._perform_monitoring_check()
                
                self.check_count += 1
                check_duration = time.time() - start_time
                
                # Record performance metrics
                self.db.record_performance_metric('monitor_check_duration', check_duration)
                
                # Calculate sleep time
                sleep_time = max(0, self.config.monitoring.check_interval - check_duration)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
            
            except Exception as e:
                self.logger.error("Error in monitoring loop", error=str(e))
                await asyncio.sleep(self.config.monitoring.check_interval)
    
    def _start_api_server(self):
        """Start API server in separate thread."""
        try:
            self.api_server = create_production_server(self.config)
            self.api_server.run()
        except Exception as e:
            self.logger.error("API server failed", error=str(e))
    
    def start(self):
        """Start the production monitor."""
        if self.is_running:
            self.logger.warning("Monitor is already running")
            return
        
        self.is_running = True
        self.start_time = time.time()
        
        self.logger.info("Starting Nova TON Production Monitor",
                        version=self.config.version,
                        environment=self.config.environment)
        
        # Start API server in separate thread
        self.api_thread = threading.Thread(target=self._start_api_server, daemon=True)
        self.api_thread.start()
        
        # Start monitoring loop
        try:
            asyncio.run(self._monitoring_loop())
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the monitor gracefully."""
        if not self.is_running:
            return
        
        self.logger.info("Stopping Nova TON Production Monitor")
        self.is_running = False
        
        # Update final system status
        uptime = time.time() - self.start_time
        self._update_system_status('stopped')
        
        # Log final statistics
        self.logger.info("Monitor stopped",
                        uptime_seconds=uptime,
                        total_checks=self.check_count,
                        total_transactions=self.total_transactions_processed,
                        error_count=self.error_count)
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        # Close database connections
        self.db.close()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current monitor status."""
        uptime = time.time() - self.start_time if self.is_running else 0
        
        return {
            'is_running': self.is_running,
            'uptime_seconds': uptime,
            'check_count': self.check_count,
            'total_transactions_processed': self.total_transactions_processed,
            'error_count': self.error_count,
            'last_successful_check': self.last_successful_check.isoformat() if self.last_successful_check else None,
            'last_logical_time': self.last_logical_time,
            'circuit_breaker_open': self.circuit_breaker['is_open'],
            'processed_transactions_cache_size': len(self.processed_transactions)
        }

def main():
    """Main entry point."""
    try:
        # Initialize configuration and logging
        config = get_config()
        LoggerFactory.set_config(config)
        
        # Create and start monitor
        monitor = ProductionTONMonitor(config)
        monitor.start()
    
    except Exception as e:
        logger = LoggerFactory.get_logger('nova.main')
        logger.critical("Failed to start production monitor", error=str(e))
        sys.exit(1)

if __name__ == '__main__':
    main()
