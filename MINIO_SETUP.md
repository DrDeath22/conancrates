# MinIO Setup for ConanCrates

## Current Status: ✅ CONFIGURED

MinIO is now set up and ready to use as the storage backend for ConanCrates!

## Access Points

- **MinIO API**: http://localhost:9000
- **MinIO Console (Web UI)**: http://localhost:9001
  - Username: `admin`
  - Password: `password123`

## Setup Completed

- ✅ MinIO Docker container running
- ✅ django-storages and boto3 installed
- ✅ Django configured to use MinIO
- ⏳ Bucket creation (manual step needed)

## Create the Bucket (One-Time Setup)

1. Open http://localhost:9001 in your browser
2. Login with `admin` / `password123`
3. Click "Buckets" in the left sidebar
4. Click "Create Bucket" button
5. Enter bucket name: `conan-packages`
6. Click "Create Bucket"

## Testing the Setup

### 1. Test Upload

1. Go to http://localhost:8000/admin/
2. Login (username: `admin`, password: `admin`)
3. Click "Binary packages"
4. Edit any binary package
5. Upload a file using the "Binary file" field
6. Save
7. **The file is now in MinIO!**

### 2. Test Download

1. Go to the package page
2. Click the download link for the binary
3. The file will be served from MinIO

### 3. Verify in MinIO Console

1. Go to http://localhost:9001
2. Click on "conan-packages" bucket
3. Browse the uploaded files

## Django Configuration

Location: `conancrates/settings.py`

```python
USE_MINIO = True  # Set to False to use local filesystem

if USE_MINIO:
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    AWS_ACCESS_KEY_ID = 'admin'
    AWS_SECRET_ACCESS_KEY = 'password123'
    AWS_STORAGE_BUCKET_NAME = 'conan-packages'
    AWS_S3_ENDPOINT_URL = 'http://localhost:9000'
    AWS_S3_REGION_NAME = 'us-east-1'
    AWS_QUERYSTRING_AUTH = True  # Signed URLs
    AWS_QUERYSTRING_EXPIRE = 3600  # 1 hour
```

## Toggle Between Local Filesystem and MinIO

Simply change `USE_MINIO` in settings.py:

```python
# Use MinIO
USE_MINIO = True

# Use local filesystem
USE_MINIO = False
```

No other code changes needed!

## Managing MinIO Container

```bash
# Stop MinIO
docker stop minio-conan

# Start MinIO
docker start minio-conan

# Remove MinIO (warning: deletes all data)
docker rm -f minio-conan

# View MinIO logs
docker logs minio-conan
```

## How It Works

### Upload Flow
```
Django Admin
    ↓
User uploads file
    ↓
Django saves to storage backend
    ↓
boto3 uploads to MinIO (port 9000)
    ↓
MinIO stores file in conan-packages bucket
    ↓
Django saves file path in database
```

### Download Flow (with signed URLs)
```
User requests download
    ↓
Django checks permissions
    ↓
Django generates signed URL (valid 1 hour)
    ↓
Redirect user to MinIO URL
    ↓
User downloads directly from MinIO
```

## Switching to Artifactory Later

To switch from MinIO to Artifactory, just update the settings:

```python
# Point to Artifactory instead of MinIO
AWS_S3_ENDPOINT_URL = 'https://artifactory.company.com/s3/'
AWS_ACCESS_KEY_ID = 'artifactory-token'
AWS_SECRET_ACCESS_KEY = 'artifactory-secret'
AWS_STORAGE_BUCKET_NAME = 'conan-local'
AWS_S3_USE_SSL = True
```

No code changes needed - same Django storage API!

## Architecture

```
ConanCrates (Django)
├─ Web UI
├─ REST API
├─ Conan dependency resolution
├─ Metadata (SQLite/PostgreSQL)
└─ File storage → MinIO

MinIO
├─ S3-compatible API
├─ Web console
└─ Stores .tar.gz binaries
```

**Key Point**: MinIO doesn't know about Conan! It just stores binary blobs. ConanCrates handles all the Conan intelligence.

## Troubleshooting

**Q: Upload fails with "No such bucket"**
A: Create the `conan-packages` bucket in MinIO console

**Q: Download returns 403 Forbidden**
A: Check MinIO credentials in settings.py

**Q: MinIO container not running**
A: Run `docker start minio-conan`

**Q: Want to see what's in MinIO**
A: Open http://localhost:9001 and browse the buckets

## Next Steps

1. Create the `conan-packages` bucket (see above)
2. Upload a test file via Django admin
3. Download it to verify it works
4. Start uploading real Conan packages!

---

**Note**: This is a development setup. For production:
- Use HTTPS (set `AWS_S3_USE_SSL = True`)
- Use strong passwords
- Consider using MinIO in distributed mode
- Or switch to Artifactory/S3
