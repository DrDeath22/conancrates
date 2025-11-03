# ConanCrates Deployment Guide

Complete guide for deploying ConanCrates on a new machine.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Setup](#detailed-setup)
  - [1. Clone Repository](#1-clone-repository)
  - [2. Setup Python Environment](#2-setup-python-environment)
  - [3. Setup MinIO](#3-setup-minio)
  - [4. Configure Django](#4-configure-django)
  - [5. Initialize Database](#5-initialize-database)
  - [6. Start Services](#6-start-services)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Production Deployment](#production-deployment)

## Prerequisites

### Required Software

- **Python 3.11+** (3.13 recommended)
- **Git** (for cloning repository)
- **MinIO** (S3-compatible object storage)
- **Conan 2.x** (for dependency resolution)

### System Requirements

- **OS**: Windows, Linux, or macOS
- **RAM**: 2GB minimum, 4GB recommended
- **Disk**: 10GB free space (for packages and database)

## Quick Start

```bash
# 1. Clone repository
git clone <repository-url>
cd ConanCrates

# 2. Create virtual environment
python -m venv venv

# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Setup MinIO (in separate terminal)
# See MinIO Setup section below

# 5. Initialize database
python manage.py migrate

# 6. Create admin user
python manage.py createsuperuser

# 7. Run server
python manage.py runserver
```

Visit http://127.0.0.1:8000/

## Detailed Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd ConanCrates
```

### 2. Setup Python Environment

#### Windows

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Conan (required for dependency resolution)
pip install conan>=2.0
```

#### Linux/macOS

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Conan (required for dependency resolution)
pip install conan>=2.0
```

### 3. Setup MinIO

MinIO is used as S3-compatible storage for package binaries.

#### Option A: Docker (Recommended)

**With persistent local storage:**

```bash
# Windows
docker run -d \
  -p 9000:9000 \
  -p 9001:9001 \
  --name minio-persistent \
  --restart unless-stopped \
  -e "MINIO_ROOT_USER=admin" \
  -e "MINIO_ROOT_PASSWORD=password123" \
  -v "d:/minio-data:/data" \
  quay.io/minio/minio server /data --console-address ":9001"

# Linux/Mac
docker run -d \
  -p 9000:9000 \
  -p 9001:9001 \
  --name minio-persistent \
  --restart unless-stopped \
  -e "MINIO_ROOT_USER=admin" \
  -e "MINIO_ROOT_PASSWORD=password123" \
  -v "/var/minio-data:/data" \
  quay.io/minio/minio server /data --console-address ":9001"
```

**Key features:**
- `-v "d:/minio-data:/data"` - Mounts local directory for persistent storage (survives container removal)
- `--restart unless-stopped` - Auto-restarts MinIO when Docker starts
- `--name minio-persistent` - Named container for easy management

**Alternative: Docker named volume** (data stored in Docker's internal volume):

```bash
docker run -d \
  -p 9000:9000 \
  -p 9001:9001 \
  --name minio \
  -e "MINIO_ROOT_USER=admin" \
  -e "MINIO_ROOT_PASSWORD=password123" \
  -v minio_data:/data \
  quay.io/minio/minio server /data --console-address ":9001"
```

#### Option B: Windows Binary

1. **Download MinIO**:
   - Visit https://min.io/download
   - Download Windows binary (minio.exe)

2. **Create data directory**:
   ```bash
   mkdir C:\minio\data
   ```

3. **Start MinIO**:
   ```bash
   # Set credentials
   set MINIO_ROOT_USER=admin
   set MINIO_ROOT_PASSWORD=password123

   # Start server
   minio.exe server C:\minio\data --console-address ":9001"
   ```

#### Option C: Linux Binary

```bash
# Download MinIO
wget https://dl.min.io/server/minio/release/linux-amd64/minio
chmod +x minio

# Create data directory
mkdir -p ~/minio/data

# Start MinIO
export MINIO_ROOT_USER=admin
export MINIO_ROOT_PASSWORD=password123
./minio server ~/minio/data --console-address ":9001"
```

#### Create MinIO Bucket

1. Open MinIO Console: http://localhost:9001
2. Login with credentials (admin / password123)
3. Go to **Buckets** → **Create Bucket**
4. Enter bucket name: `conancrates`
5. Click **Create Bucket**

Alternatively, use MinIO client (mc):

```bash
# Install mc
# Windows: download from https://dl.min.io/client/mc/release/windows-amd64/mc.exe
# Linux: wget https://dl.min.io/client/mc/release/linux-amd64/mc

# Configure mc
mc alias set myminio http://localhost:9000 admin password123

# Create bucket
mc mb myminio/conancrates
```

### 4. Configure Django

The default configuration should work out of the box, but you can customize:

#### Edit `conancrates/settings.py`

```python
# MinIO Configuration (lines 134-156)
AWS_ACCESS_KEY_ID = 'admin'              # MinIO username
AWS_SECRET_ACCESS_KEY = 'password123'    # MinIO password
AWS_STORAGE_BUCKET_NAME = 'conancrates'  # Bucket name
AWS_S3_ENDPOINT_URL = 'http://localhost:9000'  # MinIO URL
```

**Important**: If you use different MinIO credentials, update these values!

#### Database Configuration

By default, SQLite is used for development:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

For production, use PostgreSQL:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'conancrates',
        'USER': 'postgres',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### 5. Initialize Database

```bash
# Apply database migrations
python manage.py migrate

# Create superuser for admin access
python manage.py createsuperuser
# Follow prompts to set username, email, and password
```

#### Optional: Load Sample Data

```bash
python create_sample_data.py
```

This creates:
- Admin user (username: `admin`, password: `admin`)
- 6 sample packages (zlib, boost, openssl, fmt, gtest, nlohmann_json)
- Multiple versions and binaries
- Sample dependencies and topics

### 6. Start Services

You need two terminals:

#### Terminal 1: MinIO (if not using Docker)

```bash
# Windows
set MINIO_ROOT_USER=admin
set MINIO_ROOT_PASSWORD=password123
minio.exe server C:\minio\data --console-address ":9001"

# Linux/Mac
export MINIO_ROOT_USER=admin
export MINIO_ROOT_PASSWORD=password123
./minio server ~/minio/data --console-address ":9001"
```

#### Terminal 2: Django

```bash
# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Start Django server
python manage.py runserver
```

### Access the Application

- **Main Application**: http://127.0.0.1:8000/
- **Django Admin**: http://127.0.0.1:8000/admin/
- **MinIO Console**: http://127.0.0.1:9001/
- **MinIO API**: http://127.0.0.1:9000/

## Configuration

### Environment Variables (Optional)

For production, use environment variables instead of hardcoding credentials:

```bash
# .env file (create in project root)
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-domain.com,localhost

# MinIO
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=password123
MINIO_BUCKET=conancrates
MINIO_ENDPOINT=http://localhost:9000

# Database (PostgreSQL)
DB_NAME=conancrates
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

Then update `settings.py` to read from environment:

```python
import os
from pathlib import Path

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

AWS_ACCESS_KEY_ID = os.environ.get('MINIO_ACCESS_KEY', 'admin')
AWS_SECRET_ACCESS_KEY = os.environ.get('MINIO_SECRET_KEY', 'password123')
# ... etc
```

### Static Files (Production)

```bash
# Collect static files
python manage.py collectstatic
```

## Troubleshooting

### MinIO Connection Errors

**Problem**: `ConnectionError: Failed to connect to MinIO`

**Solutions**:
1. Verify MinIO is running: http://localhost:9000/minio/health/live
2. Check credentials in `settings.py` match MinIO
3. Verify bucket exists in MinIO Console
4. Check firewall isn't blocking port 9000

### Database Errors

**Problem**: `django.db.utils.OperationalError: no such table`

**Solution**:
```bash
python manage.py migrate
```

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'X'`

**Solution**:
```bash
# Ensure virtual environment is activated
pip install -r requirements.txt
```

### Conan Not Found

**Problem**: Bundle downloads fail with HTTP 503

**Solution**:
```bash
pip install conan>=2.0
```

### Permission Denied on MinIO

**Problem**: `S3ResponseError: Access Denied`

**Solutions**:
1. Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in settings.py
2. Verify bucket exists and has correct permissions
3. Create bucket if missing (see MinIO setup)

## Production Deployment

### Using Gunicorn (Linux/Mac)

```bash
# Install gunicorn
pip install gunicorn

# Run with 4 workers
gunicorn conancrates.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

### Using Nginx as Reverse Proxy

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /path/to/ConanCrates/staticfiles/;
    }
}
```

### Using Docker Compose (Recommended for Production)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: conancrates
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password123
    volumes:
      - postgres_data:/var/lib/postgresql/data

  minio:
    image: quay.io/minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: admin
      MINIO_ROOT_PASSWORD: password123
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

  web:
    build: .
    command: gunicorn conancrates.wsgi:application --bind 0.0.0.0:8000
    environment:
      DEBUG: "False"
      SECRET_KEY: "your-production-secret-key"
      DB_HOST: db
      DB_NAME: conancrates
      DB_USER: postgres
      DB_PASSWORD: password123
      MINIO_ENDPOINT: http://minio:9000
    ports:
      - "8000:8000"
    depends_on:
      - db
      - minio

volumes:
  postgres_data:
  minio_data:
```

### Security Checklist

- [ ] Change SECRET_KEY in settings.py
- [ ] Set DEBUG = False in production
- [ ] Update ALLOWED_HOSTS with your domain
- [ ] Change MinIO credentials from defaults
- [ ] Use HTTPS (SSL/TLS certificates)
- [ ] Enable Django's CSRF protection
- [ ] Set up proper database backups
- [ ] Configure firewall rules
- [ ] Use strong passwords for admin users
- [ ] Keep dependencies updated (`pip list --outdated`)

## Using ConanCrates CLI

The `conancrates.py` CLI tool is in the repository root.

### Upload Package

```bash
# First, create your package with Conan
conan create . --user=youruser --channel=stable

# Upload to ConanCrates
python conancrates.py upload package_name/version
```

### Download Package

```bash
python conancrates.py download package_name/version
```

This downloads the recipe + binaries to `./conan_packages/package_name-version/`

## Backing Up

### Database Backup (SQLite)

```bash
# Simply copy the database file
cp db.sqlite3 db.sqlite3.backup
```

### Database Backup (PostgreSQL)

```bash
pg_dump -U postgres conancrates > backup.sql
```

### MinIO Backup

```bash
# Using mc (MinIO client)
mc mirror myminio/conancrates /backup/path/
```

## Monitoring

### Check Application Health

```bash
# Test homepage
curl http://localhost:8000/

# Test API
curl http://localhost:8000/v2/v1/ping

# Check database
python manage.py dbshell
```

### View Logs

```bash
# Django development server logs (stdout)
python manage.py runserver

# Production logs (configure in settings.py)
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': '/var/log/conancrates/django.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
        },
    },
}
```

## Support

For issues or questions:
1. Check this deployment guide
2. Review [README.md](README.md) for general information
3. Check [RESUME_SESSION.md](RESUME_SESSION.md) for latest development status
4. Review error logs in Django and MinIO

## Summary

Minimal deployment steps:

```bash
# 1. Clone and setup Python
git clone <repo>
cd ConanCrates
python -m venv venv
source venv/bin/activate  # or .\venv\Scripts\activate on Windows
pip install -r requirements.txt

# 2. Start MinIO (separate terminal)
docker run -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=admin -e MINIO_ROOT_PASSWORD=password123 \
  quay.io/minio/minio server /data --console-address ":9001"

# Create bucket: http://localhost:9001 → Buckets → Create "conancrates"

# 3. Initialize Django
python manage.py migrate
python manage.py createsuperuser

# 4. Run
python manage.py runserver
```

Access http://127.0.0.1:8000/ 🎉
