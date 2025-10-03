# 🌐 Nova TON Monitor - Configuration Guide

## 🎯 Quick Server URL Change

To change the server URL throughout the entire monitor project, you have **3 easy options**:

### **Option 1: Environment Variables (Recommended)**
1. Copy `.env.example` to `.env`
2. Edit the `.env` file:
```bash
SERVER_PROTOCOL=http
SERVER_HOST=95.181.212.120
SERVER_PORT=5001
```

### **Option 2: Direct Code Change**
Edit `config/server_config.py`:
```python
# Change these values:
PROTOCOL = 'http'
HOST = '95.181.212.120'
PORT = 5001
```

### **Option 3: Runtime Configuration**
```python
from config.server_config import server_config
server_config.update_server_config(
    protocol='https',
    host='your-domain.com', 
    port=443
)
```

## 📁 Files That Use Centralized Configuration

✅ **Automatically Updated Files:**
- `main.py` - Server startup
- `src/api/marketplace_api_complete.py` - API endpoints and CORS
- `config/production.py` - Production configuration
- All future files that import `server_config`

## 🔧 Configuration Structure

```
monitor/
├── config/
│   ├── server_config.py      # 🎯 MAIN CONFIG - Change URLs here
│   ├── production.py         # Production settings
│   └── .env.example          # Environment template
├── .env                      # Your local environment (create this)
└── main.py                   # Uses centralized config
```

## 🌐 Available URLs

The centralized config provides these URLs:

| Method | URL | Description |
|--------|-----|-------------|
| `get_server_url()` | `http://95.181.212.120:5001` | Base server URL |
| `get_api_base_url()` | `http://95.181.212.120:5001/api` | API base URL |
| `get_health_url()` | `http://95.181.212.120:5001/health` | Health check |
| `get_endpoint_url('users/create')` | `http://95.181.212.120:5001/api/users/create` | Specific endpoint |

## 🚀 Testing Configuration

Test your configuration:
```bash
cd monitor
python config/server_config.py
```

This will show all configured URLs.

## 🔄 Frontend Integration

Update your frontend `environment.ts`:
```typescript
// Use the same server URL
baseUrl: import.meta.env.VITE_API_BASE_URL || 'http://95.181.212.120:5001'
```

## 🛡️ Security Notes

- **Never commit `.env`** files to git
- **Use HTTPS in production** (`SERVER_PROTOCOL=https`)
- **Configure proper CORS origins** for your frontend domains
- **Use environment variables** for sensitive data

## 📊 CORS Configuration

The system automatically configures CORS for:
- Your server URL
- Common development URLs (localhost:3000, localhost:8080)
- Custom origins from `CORS_ORIGINS` environment variable

## 🎉 Benefits

✅ **Single Source of Truth** - Change URL in one place  
✅ **Environment Flexibility** - Different URLs for dev/prod  
✅ **Automatic CORS** - Server URL automatically added to CORS  
✅ **Type Safety** - Centralized configuration with validation  
✅ **Easy Testing** - Built-in configuration display  

---

**Need help?** Check the configuration by running:
```bash
python config/server_config.py
```
