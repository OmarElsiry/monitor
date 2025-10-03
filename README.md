# 🏭 Nova TON Monitor - Production System

## Overview

Professional TON blockchain monitoring and API system for the Nova ecosystem.

## 🚀 Quick Start

### Start Monitor
```bash
python main.py
```

### Start API Server  
```bash
python server.py
```

### Docker Deployment
```bash
docker-compose up -d
```

## 📁 Directory Structure

```
monitor/
├── main.py                 # 🚀 Monitor entry point
├── server.py              # 🌐 API server entry point
├── README.md              # 📖 This file
├── requirements.txt       # 📦 Python dependencies
├── Dockerfile             # 🐳 Container configuration
├── docker-compose.yml     # 🐳 Stack orchestration
├── .env.production.template # ⚙️ Environment template
├── src/                   # 📁 Application source code
│   ├── core/             # 🔧 Core monitoring logic
│   ├── api/              # 🌐 API endpoints
│   ├── services/         # 💼 Business services
│   └── integrations/     # 🔗 External integrations
├── tools/                # 🛠️ Development and maintenance tools
├── config/               # ⚙️ Configuration files
├── utils/                # 🔧 Utility functions
├── data/                 # 🗄️ Database storage
└── docs/                 # 📚 Documentation
```

## ⚙️ Configuration

1. **Copy Environment Template:**
   ```bash
   cp .env.production.template .env.production
   ```

2. **Edit Configuration:**
   ```bash
   nano .env.production
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## 🔧 Core Features

- **✅ Real-time TON Monitoring** - Blockchain transaction monitoring
- **✅ Wallet Integration** - Multi-wallet support with address normalization
- **✅ REST API** - Complete API for frontend integration
- **✅ User Management** - Telegram and wallet-based user system
- **✅ Balance Tracking** - Accurate deposit and withdrawal tracking
- **✅ Marketplace System** - Telegram channel marketplace
- **✅ Security** - Production-grade security and validation
- **✅ Docker Support** - Complete containerization

## 🌐 API Endpoints

### Core Balance API
- `GET /api/balance/wallet/{address}` - Get balance by wallet address
- `POST /api/balance/refresh/wallet/{address}` - Refresh balance
- `POST /api/users/create` - Create user with wallet

### Health & Status
- `GET /api/health` - System health check
- `GET /api/status` - Detailed system status

## 🐳 Docker Deployment

The system includes complete Docker configuration:

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 🔒 Security Features

- **Environment Variables** - No hardcoded secrets
- **Input Validation** - Comprehensive request validation
- **Rate Limiting** - API abuse protection
- **CORS Configuration** - Proper cross-origin handling
- **Error Sanitization** - No information leakage

## 📊 Monitoring & Health

- **Health Endpoints** - Built-in health checks
- **Structured Logging** - JSON formatted logs
- **Error Tracking** - Comprehensive error handling
- **Performance Metrics** - Response time monitoring

## 🛠️ Development

### Running Tests
```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src
```

### Code Quality
```bash
# Format code
black src/
isort src/

# Lint code
flake8 src/
mypy src/
```

## 📈 Production Deployment

1. **Environment Setup** - Configure production environment variables
2. **Database Setup** - Initialize database schema
3. **SSL Configuration** - Set up HTTPS certificates
4. **Load Balancer** - Configure reverse proxy (Nginx)
5. **Monitoring** - Set up logging and alerting
6. **Backup Strategy** - Configure automated backups

## 🆘 Troubleshooting

### Common Issues

1. **Database Connection**
   ```bash
   # Check database file
   ls -la data/NovaTonMonitor.db
   
   # Test connection
   python -c "import sqlite3; print('DB OK')"
   ```

2. **API Not Responding**
   ```bash
   # Check if port is in use
   netstat -an | grep 5001
   
   # Check logs
   tail -f logs/api.log
   ```

3. **Monitor Not Processing**
   ```bash
   # Check logical time
   python -c "
   import sqlite3
   conn = sqlite3.connect('data/NovaTonMonitor.db')
   print(conn.execute('SELECT * FROM logical_time').fetchone())
   "
   ```

## 📞 Support

For issues and support:
1. Check logs in `logs/` directory
2. Review configuration in `.env.production`
3. Verify database integrity
4. Check API health endpoints

---

## 🎯 Production Status

**✅ PRODUCTION READY**

This system is optimized for production deployment with:
- Professional code organization
- Comprehensive error handling
- Security best practices
- Performance optimization
- Complete documentation

**Deploy with confidence!** 🚀
