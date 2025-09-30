# 🏭 Nova TON Monitor - Production Deployment Guide

## Overview

This is a production-ready TON blockchain monitoring system with advanced features including:

- **High-performance monitoring** with circuit breakers and retry logic
- **Secure API server** with rate limiting and authentication
- **Structured logging** with correlation IDs and metrics
- **Database connection pooling** with failover support
- **Docker containerization** with health checks
- **Comprehensive monitoring** with Prometheus and Grafana
- **Automated deployment** with backup and rollback capabilities

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Linux/Unix environment (for deployment scripts)
- TON API key from TONCenter
- SSL certificates (optional, for HTTPS)

### 1. Clone and Setup

```bash
git clone <your-repo>
cd nova/monitor

# Copy environment template
cp .env.production.template .env.production

# Edit environment variables
nano .env.production
```

### 2. Configure Environment

Edit `.env.production` with your actual values:

```bash
# Required Configuration
DB_PASSWORD=your_secure_database_password
TON_API_KEY=your_ton_api_key_from_toncenter
API_SECRET_KEY=your_32_character_secret_key
JWT_SECRET=your_jwt_secret_key
REDIS_PASSWORD=your_redis_password

# Optional Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
SENTRY_DSN=your_sentry_dsn
```

### 3. Deploy

```bash
# Make deployment script executable
chmod +x scripts/deploy.sh

# Deploy the full stack
./scripts/deploy.sh deploy
```

### 4. Verify Deployment

```bash
# Check service status
./scripts/deploy.sh status

# View logs
./scripts/deploy.sh logs

# Test API
curl http://localhost:5001/api/health
```

## 📋 Architecture

### Core Components

1. **Nova Monitor** (`production_monitor.py`)
   - Blockchain monitoring with async processing
   - Transaction detection and user matching
   - Balance updates and notifications

2. **Production API** (`api/production_server.py`)
   - RESTful API with security features
   - Rate limiting and authentication
   - Comprehensive error handling

3. **Database Layer** (`database/production_db.py`)
   - Connection pooling and failover
   - Migration management
   - Performance monitoring

4. **Logging System** (`utils/production_logger.py`)
   - Structured JSON logging
   - Correlation ID tracking
   - Performance metrics

### Infrastructure Stack

- **Application**: Python 3.11 with Flask and asyncio
- **Database**: PostgreSQL 15 with connection pooling
- **Cache**: Redis 7 for rate limiting and caching
- **Reverse Proxy**: Nginx with SSL termination
- **Monitoring**: Prometheus + Grafana
- **Containerization**: Docker with health checks

## 🔧 Configuration

### Environment Variables

#### Core Application
```bash
ENVIRONMENT=production
APP_VERSION=1.0.0
API_HOST=0.0.0.0
API_PORT=5001
```

#### Database
```bash
DB_HOST=postgres
DB_NAME=nova_ton_monitor
DB_USER=nova_user
DB_PASSWORD=your_password
DB_MAX_CONNECTIONS=20
```

#### TON Blockchain
```bash
TON_API_KEY=your_api_key
TON_NETWORK=mainnet
TON_REQUEST_TIMEOUT=30
TON_MAX_RETRIES=3
```

#### Security
```bash
ENABLE_API_KEY_AUTH=false
ENABLE_RATE_LIMITING=true
API_RATE_LIMIT=100 per minute
SSL_CERT_PATH=/path/to/cert.pem
SSL_KEY_PATH=/path/to/key.pem
```

#### Monitoring
```bash
LOG_LEVEL=INFO
LOG_JSON_FORMAT=true
METRICS_PORT=9090
HEALTH_CHECK_PORT=8080
```

## 🛡️ Security Features

### API Security
- **Rate Limiting**: Configurable per-endpoint limits
- **CORS Protection**: Whitelist allowed origins
- **Input Validation**: Comprehensive request sanitization
- **API Key Authentication**: Optional API key validation
- **SSL/TLS Support**: HTTPS with certificate management

### Database Security
- **Connection Pooling**: Secure connection management
- **Parameterized Queries**: SQL injection prevention
- **Audit Logging**: Complete action tracking
- **Data Encryption**: At-rest and in-transit encryption

### Infrastructure Security
- **Non-root Containers**: Security-hardened Docker images
- **Network Isolation**: Private Docker networks
- **Secret Management**: Environment-based configuration
- **Health Monitoring**: Automated security event detection

## 📊 Monitoring and Observability

### Metrics Collection
- **Application Metrics**: API response times, error rates
- **Business Metrics**: Transaction processing, user activity
- **System Metrics**: Database performance, memory usage
- **Custom Metrics**: Domain-specific KPIs

### Logging
- **Structured Logging**: JSON format with correlation IDs
- **Log Levels**: Configurable verbosity
- **Log Rotation**: Automatic log file management
- **Centralized Logging**: Optional ELK stack integration

### Dashboards
- **Grafana Dashboards**: Pre-configured monitoring views
- **Prometheus Metrics**: Time-series data collection
- **Health Checks**: Automated service monitoring
- **Alerting**: Configurable alert rules

## 🚀 Deployment Options

### Docker Compose (Recommended)
```bash
# Full stack deployment
./scripts/deploy.sh deploy

# Individual service management
docker-compose up -d nova-monitor
docker-compose logs -f nova-monitor
```

### Manual Deployment
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export $(cat .env.production | xargs)

# Run application
python production_monitor.py
```

### Kubernetes (Advanced)
```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/

# Monitor deployment
kubectl get pods -l app=nova-monitor
```

## 🔄 Operations

### Daily Operations

#### Health Monitoring
```bash
# Check overall health
curl http://localhost:5001/api/health

# View service status
./scripts/deploy.sh status

# Monitor logs
./scripts/deploy.sh logs nova-monitor
```

#### Performance Monitoring
```bash
# View metrics
curl http://localhost:9090/metrics

# Access Grafana
open http://localhost:3000
```

### Maintenance Tasks

#### Database Maintenance
```bash
# Create backup
./scripts/deploy.sh backup

# Database cleanup (removes old audit logs)
docker exec nova-monitor python -c "
from database.production_db import get_database
db = get_database()
db.cleanup_old_data(days_to_keep=30)
"
```

#### Log Management
```bash
# View recent logs
docker-compose logs --tail=100 nova-monitor

# Log rotation is automatic, but can be triggered manually
docker exec nova-monitor logrotate /etc/logrotate.conf
```

### Troubleshooting

#### Common Issues

1. **API Not Responding**
   ```bash
   # Check container status
   docker ps | grep nova-monitor
   
   # Check logs for errors
   docker-compose logs nova-monitor
   
   # Restart service
   docker-compose restart nova-monitor
   ```

2. **Database Connection Issues**
   ```bash
   # Check PostgreSQL status
   docker exec nova-postgres pg_isready
   
   # Check connection from app
   docker exec nova-monitor python -c "
   from database.production_db import get_database
   print(get_database().get_health_status())
   "
   ```

3. **High Memory Usage**
   ```bash
   # Check memory usage
   docker stats nova-monitor
   
   # Adjust memory limits in docker-compose.yml
   deploy:
     resources:
       limits:
         memory: 512M
   ```

#### Performance Tuning

1. **Database Optimization**
   ```sql
   -- Check slow queries
   SELECT query, mean_time, calls 
   FROM pg_stat_statements 
   ORDER BY mean_time DESC LIMIT 10;
   
   -- Analyze table statistics
   ANALYZE transactions;
   ```

2. **API Performance**
   ```bash
   # Monitor response times
   curl -w "@curl-format.txt" http://localhost:5001/api/health
   
   # Check rate limiting
   curl -I http://localhost:5001/api/users/create
   ```

## 🔐 Security Hardening

### Production Checklist

- [ ] **Environment Variables**: All secrets in environment files
- [ ] **SSL/TLS**: HTTPS enabled with valid certificates
- [ ] **Firewall**: Only necessary ports exposed
- [ ] **Updates**: Regular security updates applied
- [ ] **Monitoring**: Security event monitoring enabled
- [ ] **Backups**: Automated backup system configured
- [ ] **Access Control**: Principle of least privilege applied

### Security Monitoring
```bash
# Check for security events
docker exec nova-monitor python -c "
from database.production_db import get_database
db = get_database()
events = db.execute_query(
    'SELECT * FROM audit_log WHERE event_type LIKE \"%security%\" ORDER BY created_at DESC LIMIT 10',
    fetch_all=True
)
for event in events:
    print(dict(event))
"
```

## 📈 Scaling

### Horizontal Scaling
- **Load Balancer**: Nginx upstream configuration
- **Database Replicas**: Read replicas for query scaling
- **Redis Cluster**: Distributed caching
- **Container Orchestration**: Kubernetes deployment

### Vertical Scaling
- **Resource Limits**: Adjust CPU and memory limits
- **Connection Pools**: Increase database connections
- **Worker Processes**: Scale async workers

## 🆘 Support

### Getting Help
- **Logs**: Always check application logs first
- **Health Endpoints**: Use `/api/health` for diagnostics
- **Metrics**: Monitor Grafana dashboards
- **Documentation**: Refer to inline code documentation

### Emergency Procedures
1. **Service Down**: Use deployment script to restart
2. **Data Loss**: Restore from automated backups
3. **Security Breach**: Rotate all secrets immediately
4. **Performance Issues**: Scale resources or optimize queries

---

## 📝 License

This production system is part of the Nova TON Monitor project. All rights reserved.

## 🤝 Contributing

For production deployments, please follow the established procedures and security guidelines. All changes should be tested in staging environments first.

---

**Production Deployment Status: ✅ READY**

This system is production-ready with enterprise-grade features including security, monitoring, and scalability. Follow the deployment guide for a successful production deployment.
