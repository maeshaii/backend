# Messaging System Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the enterprise-grade messaging system to production with Redis, AWS S3, and monitoring infrastructure.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Configuration](#database-configuration)
4. [Redis Configuration](#redis-configuration)
5. [AWS S3 Configuration](#aws-s3-configuration)
6. [Sentry Configuration](#sentry-configuration)
7. [Django Deployment](#django-deployment)
8. [Frontend Deployment](#frontend-deployment)
9. [Mobile App Deployment](#mobile-app-deployment)
10. [Monitoring Setup](#monitoring-setup)
11. [Security Configuration](#security-configuration)
12. [Performance Optimization](#performance-optimization)
13. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- **Server**: Ubuntu 20.04+ or CentOS 8+
- **Python**: 3.11+
- **Node.js**: 18+
- **PostgreSQL**: 13+
- **Redis**: 6.0+
- **Nginx**: 1.18+

### Cloud Services
- **AWS S3**: For file storage
- **Sentry**: For error tracking
- **Domain**: SSL certificate required

---

## Environment Setup

### 1. Create Environment File
Create `.env` file in the backend directory:

```bash
# Django Settings
SECRET_KEY=your-super-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Database
DATABASE_URL=postgresql://username:password@localhost:5432/messaging_db

# Redis
REDIS_URL=redis://localhost:6379/0

# AWS S3
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_STORAGE_BUCKET_NAME=your-messaging-bucket
AWS_S3_REGION_NAME=us-east-1
AWS_S3_CUSTOM_DOMAIN=your-cdn-domain.com

# Sentry
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=1.0.0

# CORS
CORS_ALLOW_CREDENTIALS=True
CORS_ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com

# Email (Optional)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

### 2. Install Dependencies
```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install

# Mobile
cd mobile
npm install
```

---

## Database Configuration

### 1. PostgreSQL Setup
```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE messaging_db;
CREATE USER messaging_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE messaging_db TO messaging_user;
\q
```

### 2. Run Migrations
```bash
cd backend
python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic --noinput
```

### 3. Create Superuser
```bash
python manage.py createsuperuser
```

---

## Redis Configuration

### 1. Install Redis
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install redis-server

# CentOS/RHEL
sudo yum install redis
```

### 2. Configure Redis
Edit `/etc/redis/redis.conf`:

```conf
# Bind to localhost and private IP
bind 127.0.0.1 10.0.0.1

# Set password
requirepass your-redis-password

# Configure memory policy
maxmemory 2gb
maxmemory-policy allkeys-lru

# Enable persistence
save 900 1
save 300 10
save 60 10000

# Configure logging
loglevel notice
logfile /var/log/redis/redis-server.log
```

### 3. Start Redis
```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
sudo systemctl status redis-server
```

### 4. Test Redis Connection
```bash
redis-cli ping
# Should return: PONG
```

---

## AWS S3 Configuration

### 1. Create S3 Bucket
```bash
# Using AWS CLI
aws s3 mb s3://your-messaging-bucket --region us-east-1

# Set bucket policy for public read access to uploaded files
aws s3api put-bucket-policy --bucket your-messaging-bucket --policy '{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::your-messaging-bucket/*"
    }
  ]
}'
```

### 2. Configure CORS
```bash
aws s3api put-bucket-cors --bucket your-messaging-bucket --cors-configuration '{
  "CORSRules": [
    {
      "AllowedHeaders": ["*"],
      "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
      "AllowedOrigins": ["https://your-domain.com"],
      "ExposeHeaders": ["ETag"],
      "MaxAgeSeconds": 3000
    }
  ]
}'
```

### 3. Create IAM User
```bash
# Create IAM user for S3 access
aws iam create-user --user-name messaging-s3-user

# Create policy for S3 access
aws iam create-policy --policy-name MessagingS3Policy --policy-document '{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::your-messaging-bucket/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::your-messaging-bucket"
    }
  ]
}'

# Attach policy to user
aws iam attach-user-policy --user-name messaging-s3-user --policy-arn arn:aws:iam::account:policy/MessagingS3Policy

# Create access keys
aws iam create-access-key --user-name messaging-s3-user
```

---

## Sentry Configuration

### 1. Create Sentry Project
1. Go to [Sentry.io](https://sentry.io)
2. Create new project
3. Select Django as the platform
4. Copy the DSN

### 2. Configure Sentry in Django
The Sentry configuration is already included in `settings.py`. Just set the environment variables:

```bash
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=1.0.0
```

### 3. Test Sentry Integration
```bash
cd backend
python manage.py shell
>>> import sentry_sdk
>>> sentry_sdk.capture_message("Test message from Django")
```

---

## Django Deployment

### 1. Install Gunicorn
```bash
pip install gunicorn
```

### 2. Create Gunicorn Configuration
Create `gunicorn.conf.py`:

```python
bind = "0.0.0.0:8000"
workers = 4
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2
preload_app = True
```

### 3. Create Systemd Service
Create `/etc/systemd/system/messaging.service`:

```ini
[Unit]
Description=Messaging System Django App
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/your/backend
Environment="PATH=/path/to/your/venv/bin"
ExecStart=/path/to/your/venv/bin/gunicorn --config gunicorn.conf.py backend.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### 4. Start Django Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable messaging
sudo systemctl start messaging
sudo systemctl status messaging
```

---

## Frontend Deployment

### 1. Build Frontend
```bash
cd frontend
npm run build
```

### 2. Configure Nginx
Create `/etc/nginx/sites-available/messaging`:

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Frontend
    location / {
        root /path/to/your/frontend/build;
        try_files $uri $uri/ /index.html;
        
        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
        add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' wss: https:;" always;
    }

    # API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Static files
    location /static/ {
        alias /path/to/your/backend/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /path/to/your/backend/media/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### 3. Enable Site
```bash
sudo ln -s /etc/nginx/sites-available/messaging /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Mobile App Deployment

### 1. Build Android APK
```bash
cd mobile
npx expo build:android --type apk
```

### 2. Build iOS IPA
```bash
cd mobile
npx expo build:ios --type archive
```

### 3. Deploy to App Stores
- **Google Play Store**: Upload APK/AAB
- **Apple App Store**: Upload IPA through Xcode or App Store Connect

---

## Monitoring Setup

### 1. System Monitoring
```bash
# Install monitoring tools
sudo apt install htop iotop nethogs

# Monitor system resources
htop
iotop
nethogs
```

### 2. Application Monitoring
```bash
# Check Django logs
sudo journalctl -u messaging -f

# Check Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Check Redis logs
sudo tail -f /var/log/redis/redis-server.log
```

### 3. Database Monitoring
```bash
# Monitor PostgreSQL
sudo -u postgres psql -c "SELECT * FROM pg_stat_activity;"
sudo -u postgres psql -c "SELECT * FROM pg_stat_database;"
```

### 4. Performance Monitoring
```bash
# Run performance tests
cd backend
python manage.py run_messaging_tests --verbose --report

# Check system health
python manage.py messaging_monitoring --health-check

# View performance metrics
python manage.py performance_metrics --summary
```

---

## Security Configuration

### 1. Firewall Setup
```bash
# Install UFW
sudo apt install ufw

# Configure firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 2. SSL Certificate
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### 3. Security Headers
Add to Nginx configuration:
```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' wss: https:;" always;
```

---

## Performance Optimization

### 1. Database Optimization
```bash
# Create indexes
cd backend
python manage.py dbshell
CREATE INDEX CONCURRENTLY idx_message_conversation_created ON shared_message(conversation_id, created_at);
CREATE INDEX CONCURRENTLY idx_message_sender_created ON shared_message(sender_id, created_at);
CREATE INDEX CONCURRENTLY idx_conversation_updated ON shared_conversation(updated_at);
```

### 2. Redis Optimization
```bash
# Configure Redis for performance
sudo nano /etc/redis/redis.conf
# Set: maxmemory 2gb
# Set: maxmemory-policy allkeys-lru
# Set: save 900 1
```

### 3. Nginx Optimization
```nginx
# Add to nginx.conf
worker_processes auto;
worker_connections 1024;
keepalive_timeout 65;
gzip on;
gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
```

---

## Troubleshooting

### Common Issues

#### 1. WebSocket Connection Failed
```bash
# Check WebSocket configuration
sudo systemctl status messaging
sudo journalctl -u messaging -f

# Check Nginx WebSocket proxy
sudo nginx -t
sudo systemctl reload nginx
```

#### 2. Redis Connection Issues
```bash
# Check Redis status
sudo systemctl status redis-server
redis-cli ping

# Check Redis logs
sudo tail -f /var/log/redis/redis-server.log
```

#### 3. S3 Upload Failures
```bash
# Test S3 connection
aws s3 ls s3://your-messaging-bucket

# Check IAM permissions
aws iam list-attached-user-policies --user-name messaging-s3-user
```

#### 4. Database Connection Issues
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Test database connection
sudo -u postgres psql -c "SELECT version();"
```

#### 5. Performance Issues
```bash
# Check system resources
htop
free -h
df -h

# Check application logs
sudo journalctl -u messaging -f
```

### Debug Commands
```bash
# Run comprehensive tests
cd backend
python manage.py run_messaging_tests --verbose --report

# Check system health
python manage.py messaging_monitoring --health-check

# View performance metrics
python manage.py performance_metrics --summary

# Check WebSocket connections
python manage.py websocket_analytics

# Monitor rate limits
python manage.py websocket_rate_limits
```

---

## Maintenance

### Daily Tasks
- Monitor system health and performance
- Check error logs and Sentry alerts
- Verify backup systems

### Weekly Tasks
- Review performance metrics
- Update dependencies
- Check security updates

### Monthly Tasks
- Full system backup
- Performance optimization review
- Security audit

---

## Backup Strategy

### 1. Database Backup
```bash
# Create backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump messaging_db > /backups/messaging_db_$DATE.sql
aws s3 cp /backups/messaging_db_$DATE.sql s3://your-backup-bucket/
```

### 2. Redis Backup
```bash
# Redis automatically creates snapshots
# Manual backup
redis-cli BGSAVE
```

### 3. File Backup
```bash
# S3 files are automatically backed up by AWS
# Local files backup
tar -czf /backups/media_$DATE.tar.gz /path/to/media/
aws s3 cp /backups/media_$DATE.tar.gz s3://your-backup-bucket/
```

---

## Scaling

### Horizontal Scaling
- Use load balancer (AWS ALB, Nginx)
- Multiple Django instances
- Redis cluster for high availability
- Database read replicas

### Vertical Scaling
- Increase server resources
- Optimize database queries
- Add more Redis memory
- Use CDN for static files

---

## Support

For deployment support:
1. Check this documentation
2. Review logs and monitoring
3. Run diagnostic commands
4. Check system health endpoints

The messaging system is now production-ready with enterprise-grade features! 🚀






