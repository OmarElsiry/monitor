# 📚 Nova TON Monitor - Complete API & Debugging Documentation

## 🏗️ Overview

This document provides comprehensive documentation for all API endpoints, debugging commands, and utility scripts available in the Nova TON Monitor system.

## 🚀 API Endpoints

### 1. Production API Server (`/api/production_server.py`)

#### Core Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|---------------|
| `GET` | `/api/health` | Comprehensive health check with database and system status | None |
| `POST` | `/api/users/create` | Create new user with wallet address and telegram ID | None |
| `GET` | `/api/balance/wallet/{wallet_address}` | Get user balance by wallet address | None |
| `GET` | `/api/users/{user_id}/transactions` | Get user transaction history with pagination | None |
| `GET` | `/api/metrics` | Get system metrics in Prometheus format | None |

#### Request/Response Examples

**Create User:**
```bash
POST /api/users/create
Content-Type: application/json

{
  "wallet_address": "UQDrY5iulWs_MyWTP9JSGedWBzlbeRmhCBoqsSaNiSLOs315",
  "telegram_id": "123456789"
}
```

**Get Balance:**
```bash
GET /api/balance/wallet/UQDrY5iulWs_MyWTP9JSGedWBzlbeRmhCBoqsSaNiSLOs315
```

---

### 2. Marketplace API (`/src/api/marketplace_api_complete.py`)

#### Bot Verification Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|---------------|
| `POST` | `/api/marketplace/verify` | Initiate channel verification through bot | Required |
| `GET` | `/api/marketplace/verification/{verification_id}` | Get verification status and results | Required |

#### Listing Management Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|---------------|
| `POST` | `/api/marketplace/listings` | Create channel listing after verification | Required |
| `GET` | `/api/marketplace/listings` | Get available channel listings with filtering | None |

#### Purchase & Escrow Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|---------------|
| `POST` | `/api/marketplace/purchase` | Initiate channel purchase with escrow | Required |
| `POST` | `/api/marketplace/confirm-payment` | Confirm payment received in escrow | Required |
| `POST` | `/api/marketplace/confirm-transfer` | Confirm ownership transfer | Required |

#### Transaction Status Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|---------------|
| `GET` | `/api/marketplace/transaction/{transaction_id}` | Get transaction status and details | Required |
| `GET` | `/api/marketplace/my-transactions` | Get user's transactions (buying and selling) | Required |

#### Utility Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|---------------|
| `GET` | `/api/marketplace/health` | API health check | None |

#### Query Parameters for Listings

- `category` - Filter by channel category
- `min_price` - Minimum price filter
- `max_price` - Maximum price filter
- `search` - Search in channel title/username
- `page` - Page number (default: 1)
- `limit` - Items per page (default: 20)

---

### 3. Telegram Marketplace API (`/src/api/telegram_marketplace_api.py`)

#### User Management Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|---------------|
| `POST` | `/api/users/register` | Register new user in marketplace | None |
| `GET` | `/api/users/{user_id}` | Get user profile information | Required |
| `PUT` | `/api/users/{user_id}` | Update user profile | Required |

#### Channel Management Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|---------------|
| `POST` | `/api/channels` | Create new channel listing | Required |
| `GET` | `/api/channels` | Get all channel listings | None |
| `GET` | `/api/channels/{channel_id}` | Get specific channel details | None |
| `PUT` | `/api/channels/{channel_id}` | Update channel listing | Required |
| `DELETE` | `/api/channels/{channel_id}` | Delete channel listing | Required |

#### Transaction Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|---------------|
| `POST` | `/api/transactions` | Create new transaction | Required |
| `GET` | `/api/transactions/{transaction_id}` | Get transaction details | Required |
| `GET` | `/api/users/{user_id}/transactions` | Get user's transactions | Required |

#### Review & Rating Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|---------------|
| `POST` | `/api/reviews` | Create review for transaction | Required |
| `GET` | `/api/channels/{channel_id}/reviews` | Get channel reviews | None |
| `GET` | `/api/users/{user_id}/reviews` | Get user reviews | None |

#### Search & Analytics Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|---------------|
| `GET` | `/api/search` | Search channels and users | None |
| `GET` | `/api/analytics/overview` | Get marketplace analytics | None |
| `GET` | `/api/analytics/channels` | Get channel analytics | None |

## 🔧 Debugging & Development Commands

### 1. Main Entry Points

#### Production Monitor
```bash
# Start the main production monitor
python main.py

# Or run directly
python src/core/production_monitor.py
```

#### API Server
```bash
# Start the API server
python server.py

# Or run directly
python src/api/marketplace_api_complete.py
```

### 2. Database Management Scripts

#### Initialize Database
```bash
# Initialize Telegram marketplace database
python tools/database/telegram_marketplace_init.py
```

#### Database Utilities
```bash
# Reset logical time tracking
python reset_logical_time.py

# Fix missing deposits
python fix_missing_deposits.py

# Cleanup for production
python tools/cleanup_for_production.py
```

### 3. Testing & Debugging Scripts

#### Test Scripts
```bash
# Test new endpoints
python test_new_endpoints.py

# Business flow testing
python business_flow_test.py

# Integration testing
python integration-test.py
```

#### Debug Scripts
```bash
# Wallet analysis
python wallet-analysis.js

# Balance debugging
python balance-debugger.py

# Transaction debugging
python transaction-debugger.py
```

### 4. Utility Scripts

#### Address Normalization
```bash
# Test address normalization
python utils/address_normalizer.py

# Generate address variants
python -c "from utils.address_normalizer import get_mainnet_variants; print(get_mainnet_variants('UQDrY5iulWs_MyWTP9JSGedWBzlbeRmhCBoqsSaNiSLOs315'))"
```

#### Logging Utilities
```bash
# Production logging
python utils/production_logger.py
```

## ⚙️ Configuration Files

### Environment Configuration
- `.env.production.template` - Production environment variables template
- `config/production.py` - Production configuration settings

### Database Configuration
- `database/production_db.py` - Database connection and management
- `tools/database/telegram_marketplace_schema.sql` - Complete database schema

## 🛠️ Development Tools

### 1. Build & Deployment
```bash
# Deploy script
bash scripts/deploy.sh

# Docker deployment
docker-compose up
```

### 2. Testing Framework
```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run tests in UI mode
npm run test:ui
```

### 3. Code Quality
```bash
# Format code
npm run format

# Lint code
npm run lint

# Type checking
npm run type-check
```

## 🚨 Troubleshooting Commands

### Database Issues
```bash
# Check database schema
python check_database_schema.py

# Inspect database
python inspect_database.py

# Debug balance issues
python debug_balance.py

# Simple balance debugging
python simple_balance_debug.py
```

### API Issues
```bash
# Test API endpoints
python test_api.py

# Check API connectivity
curl http://localhost:5001/api/health
```

### Monitor Issues
```bash
# Check monitor status
python check_db.py

# Debug monitor processes
python debug_monitor.py
```

## 📊 Monitoring & Health Checks

### Health Endpoints
```bash
# Production API health
GET /api/health

# Marketplace API health
GET /api/marketplace/health

# Monitor health
GET /api/website/info
```

### Log Monitoring
- Monitor logs in `logs/` directory
- Check `utils/production_logger.py` for log configuration
- Use structured logging for debugging

## 🔒 Security Features

### Authentication Headers
```
X-User-ID: <telegram_user_id>
X-Wallet-Address: <wallet_address>
X-API-Key: <api_key> (if enabled)
X-Correlation-ID: <correlation_id>
```

### Rate Limiting
- Default limits applied per endpoint
- Redis-based rate limiting for production
- Configurable in `config/production.py`

## 📈 Performance Monitoring

### Metrics Endpoint
```bash
# Get Prometheus metrics
GET /api/metrics
```

### Performance Logging
- Automatic performance logging on all endpoints
- Database query performance tracking
- Response time monitoring

## 🔄 API Versioning

Current API Version: `3.0`

All endpoints are versioned and backward compatible. Breaking changes will be released as new major versions.

---

## 📞 Support

For issues or questions:
1. Check the troubleshooting commands above
2. Review the log files in `logs/` directory
3. Test endpoints using the health check endpoints
4. Use the debugging scripts for specific issues

**Last Updated:** September 30, 2025
**Version:** 3.0
