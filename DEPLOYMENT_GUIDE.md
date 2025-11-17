# 🚀 Production Deployment Guide
**CTU Alumni Messaging System - Senior Developer Edition**

---

## 📋 **PRE-DEPLOYMENT CHECKLIST**

### **1. Environment Setup**

- [ ] **Production Server Ready**
  - Ubuntu 20.04+ or Windows Server 2019+
  - Python 3.11+ installed
  - PostgreSQL 13+ installed and running
  - Redis 6+ installed and running
  - Nginx installed (for reverse proxy)

- [ ] **Environment Variables Configured**
  ```bash
  # Create .env file with:
  SECRET_KEY=<generate-strong-random-key>
  DEBUG=False
  ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
  
  # Database
  DB_ENGINE=django.db.backends.postgresql
  DB_NAME=ctu_alumni_prod
  DB_USER=ctu_admin
  DB_PASSWORD=<strong-password>
  DB_HOST=localhost
  DB_PORT=5432
  
  # Redis
  REDIS_URL=redis://127.0.0.1:6379/0
  
  # Frontend URL
  FRONTEND_URL=https://yourdomain.com
  
  # Email (Gmail example)
  EMAIL_HOST=smtp.gmail.com
  EMAIL_PORT=587
  EMAIL_USE_TLS=True
  EMAIL_HOST_USER=your-email@gmail.com
  EMAIL_HOST_PASSWORD=your-app-password
  
  # SMS (if using)
  SEMAPHORE_API_KEY=your-api-key
  
  # AWS S3 (if using cloud storage)
  AWS_ACCESS_KEY_ID=your-access-key
  AWS_SECRET_ACCESS_KEY=your-secret-key
  AWS_STORAGE_BUCKET_NAME=your-bucket-name
  AWS_S3_REGION_NAME=us-east-1
  ```

### **2. Code Preparation**

- [ ] **Latest Code Deployed**
  ```bash
  git clone https://github.com/your-repo/ctu-alumni.git
  cd ctu-alumni/backend
  ```

- [ ] **Virtual Environment Created**
  ```bash
  python -m venv venv
  source venv/bin/activate  # Linux/Mac
  # or
  .\venv\Scripts\Activate.ps1  # Windows
  ```

- [ ] **Dependencies Installed**
  ```bash
  pip install -r requirements.txt
  pip install gunicorn  # For production server
  pip install psycopg2-binary  # For PostgreSQL
  ```

### **3. Database Setup**

- [ ] **Database Created**
  ```sql
  CREATE DATABASE ctu_alumni_prod;
  CREATE USER ctu_admin WITH PASSWORD 'strong-password';
  GRANT ALL PRIVILEGES ON DATABASE ctu_alumni_prod TO ctu_admin;
  ```

- [ ] **Migrations Run**
  ```bash
  python manage.py migrate
  ```

- [ ] **Static Files Collected**
  ```bash
  python manage.py collectstatic --no-input
  ```

- [ ] **Superuser Created**
  ```bash
  python manage.py createsuperuser
  ```

### **4. Redis Configuration**

- [ ] **Redis Running**
  ```bash
  # Check Redis status
  redis-cli ping  # Should return "PONG"
  ```

- [ ] **Redis Persistence Configured**
  Edit `/etc/redis/redis.conf`:
  ```conf
  # Enable AOF persistence
  appendonly yes
  appendfilename "appendonly.aof"
  
  # Or RDB snapshots
  save 900 1
  save 300 10
  save 60 10000
  ```

- [ ] **Redis Memory Limit Set**
  ```conf
  maxmemory 512mb
  maxmemory-policy allkeys-lru
  ```

### **5. Security Configuration**

- [ ] **SECRET_KEY Generated**
  ```python
  from django.core.management.utils import get_random_secret_key
  print(get_random_secret_key())
  ```

- [ ] **DEBUG=False** in production

- [ ] **ALLOWED_HOSTS** configured with your domain

- [ ] **CORS Settings** configured:
  ```python
  CORS_ALLOWED_ORIGINS = [
      "https://yourdomain.com",
      "https://www.yourdomain.com",
  ]
  ```

- [ ] **CSRF Settings** configured:
  ```python
  CSRF_TRUSTED_ORIGINS = [
      "https://yourdomain.com",
      "https://www.yourdomain.com",
  ]
  ```

---

## 🔧 **DEPLOYMENT STEPS**

### **OPTION A: Gunicorn + Nginx (Recommended for Linux)**

#### **1. Create Gunicorn Service**

Create `/etc/systemd/system/ctu-alumni.service`:

```ini
[Unit]
Description=CTU Alumni Messaging System
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/var/www/ctu-alumni/backend
Environment="PATH=/var/www/ctu-alumni/backend/venv/bin"
ExecStart=/var/www/ctu-alumni/backend/venv/bin/gunicorn \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 60 \
    --access-logfile /var/log/ctu-alumni/access.log \
    --error-logfile /var/log/ctu-alumni/error.log \
    backend.asgi:application

[Install]
WantedBy=multi-user.target
```

**Start the service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable ctu-alumni
sudo systemctl start ctu-alumni
sudo systemctl status ctu-alumni
```

#### **2. Create Daphne Service (for WebSockets)**

Create `/etc/systemd/system/ctu-alumni-ws.service`:

```ini
[Unit]
Description=CTU Alumni WebSocket Server
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/ctu-alumni/backend
Environment="PATH=/var/www/ctu-alumni/backend/venv/bin"
ExecStart=/var/www/ctu-alumni/backend/venv/bin/daphne \
    -b 0.0.0.0 \
    -p 8001 \
    backend.asgi:application

[Install]
WantedBy=multi-user.target
```

**Start the service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable ctu-alumni-ws
sudo systemctl start ctu-alumni-ws
sudo systemctl status ctu-alumni-ws
```

#### **3. Configure Nginx**

Create `/etc/nginx/sites-available/ctu-alumni`:

```nginx
upstream django_app {
    server 127.0.0.1:8000;
}

upstream websocket_app {
    server 127.0.0.1:8001;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    # SSL Configuration (use Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    client_max_body_size 50M;
    
    # Static files
    location /static/ {
        alias /var/www/ctu-alumni/backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # Media files
    location /media/ {
        alias /var/www/ctu-alumni/backend/media/;
        expires 7d;
        add_header Cache-Control "public";
    }
    
    # WebSocket connections
    location /ws/ {
        proxy_pass http://websocket_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
    
    # API endpoints
    location /api/ {
        proxy_pass http://django_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
    
    # Admin interface
    location /admin/ {
        proxy_pass http://django_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Health checks (no auth required)
    location /api/messaging/health/ {
        proxy_pass http://django_app;
        proxy_set_header Host $host;
        access_log off;
    }
}
```

**Enable the site:**
```bash
sudo ln -s /etc/nginx/sites-available/ctu-alumni /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl reload nginx
```

#### **4. SSL Certificate (Let's Encrypt)**

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

---

### **OPTION B: Daphne Only (Simpler, all-in-one)**

If you prefer a single server for both HTTP and WebSocket:

```bash
# Install daphne
pip install daphne

# Run daphne
daphne -b 0.0.0.0 -p 8000 backend.asgi:application
```

Then configure Nginx to proxy to port 8000 for both HTTP and WebSocket.

---

## 📊 **POST-DEPLOYMENT VERIFICATION**

### **1. Health Checks**

```bash
# Basic health check
curl https://yourdomain.com/api/messaging/health/

# Detailed health check
curl https://yourdomain.com/api/messaging/health/detailed/

# Expected response:
{
  "status": "healthy",
  "checks": {
    "database": {"status": "healthy"},
    "redis_cache": {"status": "healthy"},
    "channel_layer": {"status": "healthy"},
    "configuration": {"status": "healthy"},
    "circuit_breakers": {"status": "healthy"}
  }
}
```

### **2. WebSocket Connection Test**

```javascript
// Open browser console on your site and run:
const ws = new WebSocket('wss://yourdomain.com/ws/notifications/');
ws.onopen = () => console.log('✅ WebSocket connected!');
ws.onerror = (e) => console.error('❌ WebSocket error:', e);
ws.onclose = () => console.log('🔌 WebSocket closed');
```

### **3. Load Testing**

```bash
# Install locust
pip install locust

# Run load test
cd backend
locust -f locustfile.py --host=https://yourdomain.com \
    --users 100 --spawn-rate 10 --run-time 5m --headless
```

**Expected Results:**
- ✅ Success rate: >99%
- ✅ Avg response time: <200ms
- ✅ No database connection errors
- ✅ No Redis failures

### **4. Database Performance Check**

```sql
-- Check slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0 AND indexname NOT LIKE 'pg_toast%'
ORDER BY pg_relation_size(indexrelid) DESC;
```

### **5. Redis Performance Check**

```bash
redis-cli INFO stats | grep -E "total_commands_processed|instantaneous_ops_per_sec"
redis-cli INFO memory | grep -E "used_memory_human|maxmemory_human"
```

---

## 🔒 **SECURITY HARDENING**

### **1. Firewall Configuration**

```bash
# Ubuntu UFW
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 80/tcp  # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

### **2. Fail2Ban (DDoS Protection)**

```bash
sudo apt install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### **3. Database Security**

```sql
-- Disable remote access (if not needed)
-- Edit postgresql.conf:
listen_addresses = 'localhost'

-- Revoke public schema privileges
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
```

### **4. Redis Security**

Edit `/etc/redis/redis.conf`:
```conf
# Bind to localhost only
bind 127.0.0.1

# Require password
requirepass your-strong-redis-password

# Disable dangerous commands
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG ""
```

Update `REDIS_URL` in `.env`:
```bash
REDIS_URL=redis://:your-strong-redis-password@127.0.0.1:6379/0
```

---

## 📈 **MONITORING & LOGGING**

### **1. Application Logs**

```bash
# Create log directory
sudo mkdir -p /var/log/ctu-alumni
sudo chown www-data:www-data /var/log/ctu-alumni

# View logs
sudo tail -f /var/log/ctu-alumni/access.log
sudo tail -f /var/log/ctu-alumni/error.log
```

### **2. System Monitoring**

Install monitoring tools:
```bash
# Install htop for process monitoring
sudo apt install htop

# Install iotop for disk I/O monitoring
sudo apt install iotop

# Install netstat for network monitoring
sudo apt install net-tools
```

### **3. Sentry Integration** (Error Tracking)

Already configured in `monitoring.py`. Just add to `.env`:
```bash
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
```

---

## 🔄 **CONTINUOUS DEPLOYMENT**

### **Deployment Script**

Create `deploy.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Starting deployment..."

# Pull latest code
echo "📥 Pulling latest code..."
git pull origin main

# Activate virtual environment
echo "🐍 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Run migrations
echo "🗄️  Running migrations..."
python manage.py migrate --no-input

# Collect static files
echo "📂 Collecting static files..."
python manage.py collectstatic --no-input

# Restart services
echo "🔄 Restarting services..."
sudo systemctl restart ctu-alumni
sudo systemctl restart ctu-alumni-ws

# Health check
echo "🏥 Running health check..."
sleep 5
curl -f http://localhost:8000/api/messaging/health/ || exit 1

echo "✅ Deployment complete!"
```

Make it executable:
```bash
chmod +x deploy.sh
```

---

## 📞 **TROUBLESHOOTING**

### **WebSocket Not Connecting**

1. Check Nginx WebSocket proxy configuration
2. Verify Daphne is running: `sudo systemctl status ctu-alumni-ws`
3. Check firewall: `sudo ufw status`
4. Test WebSocket endpoint: `wscat -c wss://yourdomain.com/ws/notifications/`

### **High Database Load**

1. Check slow queries (see Database Performance Check above)
2. Verify indexes are being used
3. Consider adding more database connections in settings.py:
   ```python
   DATABASES['default']['CONN_MAX_AGE'] = 600
   ```

### **Redis Out of Memory**

1. Check memory usage: `redis-cli INFO memory`
2. Increase maxmemory in redis.conf
3. Verify eviction policy: `maxmemory-policy allkeys-lru`

### **High Response Times**

1. Check Gunicorn workers: Increase if CPU allows
2. Enable query logging: `LOGGING['handlers']['file']`
3. Use Django Debug Toolbar in staging
4. Run load test to identify bottlenecks

---

## 🎯 **SUCCESS CRITERIA**

Your deployment is successful if:

- ✅ Health check returns `{"status": "healthy"}`
- ✅ WebSocket connections work from browser
- ✅ Load test shows >99% success rate
- ✅ Response times < 200ms average
- ✅ No errors in application logs
- ✅ Redis and database are healthy
- ✅ SSL certificate is valid
- ✅ All tests pass

---

**🎉 Congratulations! Your CTU Alumni Messaging System is production-ready!**

For support, refer to:
- `WEBSOCKET_OPTIMIZATION_COMPLETE.md` - Performance optimizations
- `backend/apps/messaging/health.py` - Health check implementation
- `locustfile.py` - Load testing configuration
