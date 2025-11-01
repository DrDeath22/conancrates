# Storage Backend and Package Upload

This document explains how to enable real package uploads/downloads and configure storage backends.

## Key Concept: Separation of Intelligence and Storage

**ConanCrates Architecture:**
```
ConanCrates (Django)          Storage Backend (MinIO/Artifactory/S3)
├─ Conan intelligence         ├─ File storage only
├─ Metadata (PostgreSQL)      ├─ No Conan knowledge needed
├─ Dependency resolution      ├─ Just stores .tar.gz blobs
├─ Beautiful UI               └─ S3-compatible API
└─ REST API
```

**The storage backend doesn't need to "understand" Conan!** ConanCrates handles all the Conan-specific logic (parsing metadata, resolving dependencies, providing REST API). The storage backend (MinIO, Artifactory, S3) just stores binary files.

This means:
- ✅ You can use free MinIO instead of expensive Artifactory
- ✅ Switch storage backends without changing application code
- ✅ Your beautiful UI instead of Artifactory's terrible UI
- ✅ Better dependency resolution using Conan CLI wrapper

## Current State

### What Works Now
✅ Database models ready (supports file storage)
✅ Download endpoints implemented
✅ Conan dependency resolution
✅ Bundle generation
❌ **Uploads NOT implemented**
❌ **Real file storage NOT configured** (returns placeholders)

### What Needs to Be Done

1. **Enable actual file downloads** - Change placeholder to real file serving
2. **Implement upload endpoints** - Allow uploading Conan packages
3. **Configure storage backend** - S3/MinIO/local filesystem
4. **Add authentication** - Secure uploads

---

## Part 1: Storage Backends

ConanCrates uses Django's storage system, which supports multiple backends:

### Architecture

```
Django Application (ConanCrates)
    ↓
Django Storage API (abstraction layer)
    ↓
Storage Backend (pluggable)
    ↓
├─ Local Filesystem (development)
├─ Amazon S3 (production)
├─ MinIO (self-hosted S3-compatible)
├─ Azure Blob Storage
├─ Google Cloud Storage
└─ Any S3-compatible storage
```

**The key insight**: Your web application doesn't store files directly. It just stores **metadata** in the database (file paths, sizes, checksums) and delegates actual file storage to a backend.

### Two Download Patterns: URL vs Proxy

ConanCrates uses **different download strategies** depending on the use case:

#### Pattern 1: **Direct URL (Redirect)** - For Pre-Existing Files

**Used for:** Individual binary downloads (`/packages/zlib/1.2.13/binaries/abc123/download/`)

```
User clicks download
    ↓
Django checks permissions
    ↓
Django generates signed URL from storage (Artifactory/MinIO/S3)
    ↓
HTTP 302 Redirect to storage URL
    ↓
User downloads directly from storage
```

**Benefits:**
- ⚡ Fast (no Django bottleneck)
- 📈 Scalable (storage handles bandwidth)
- 💰 Cheap (no Django server resources)
- 🔒 Secure (signed/temporary URLs)

**With Artifactory:**
```python
def download_binary(request, package_name, version, binary_id):
    binary = get_object_or_404(BinaryPackage, ...)

    # Increment download counter
    binary.download_count += 1
    binary.save()

    # Generate Artifactory URL (with auth token if needed)
    url = f"https://artifactory.company.com/conan-local/{package_name}/{version}/{binary_id}.tar.gz"

    # Redirect user to Artifactory
    return HttpResponseRedirect(url)
```

#### Pattern 2: **Proxy (Stream)** - For Dynamic Content

**Used for:** Bundle downloads with Conan resolution (`/packages/boost/1.81.0/bundle/`)

```
User requests bundle
    ↓
Django uses Conan to resolve dependencies (runtime computation)
    ↓
Django fetches binaries from storage
    ↓
Django creates ZIP file on-the-fly in memory
    ↓
Django streams ZIP to user
```

**Why Proxy for Bundles?**
- 📦 Bundle doesn't exist pre-built in storage
- 🧮 Uses Conan's resolution logic (computed at request time)
- 🎯 Different for every platform/compiler/version combination
- 💾 Can't/shouldn't pre-generate all possible bundles

**With Artifactory:**
```python
def download_bundle(request, package_name, version):
    # Use Conan to resolve dependencies (runtime computation)
    resolution = resolve_dependencies(
        package_name, version, os, arch, compiler, compiler_version, build_type
    )

    # Create ZIP in memory
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for pkg in resolution['packages']:
            # Fetch binary from Artifactory
            url = f"https://artifactory.company.com/conan-local/{pkg['name']}/{pkg['version']}/{pkg['package_id']}.tar.gz"
            response = requests.get(url, auth=('user', 'token'))

            # Add to ZIP bundle
            zipf.writestr(f"{pkg['name']}/{pkg['name']}-{pkg['version']}.tar.gz", response.content)

        # Add metadata
        zipf.writestr('bundle_info.json', json.dumps(resolution))

    # Stream ZIP to user
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f'{package_name}-bundle.zip')
```

### Summary: When to Use Each Pattern

| Download Type | Pattern | Reason |
|---------------|---------|--------|
| Individual binary | **URL Redirect** | File exists in storage, just send user there |
| Package manifest (JSON) | **Proxy** | Small, generated dynamically from DB |
| **Bundle ZIP** | **Proxy** | **Created on-the-fly using Conan resolution** |
| Recipe/conanfile | **URL Redirect** | File exists in storage |
| Source archive | **URL Redirect** | File exists in storage |

### How Upload Works

1. **Upload Request** → Django receives file
2. **Django validates** → Checks user, package, etc.
3. **Storage backend saves** → File goes to Artifactory/MinIO/S3
4. **Django saves metadata** → Stores path/URL in database
5. **Download Request** → Django uses URL (redirect) or Proxy (stream) based on use case
6. **User downloads** → Directly from storage OR through Django

### Storage Backends Comparison

| Backend | Use Case | Pros | Cons |
|---------|----------|------|------|
| **Local Filesystem** | Quick dev testing | Simple, fast | Not scalable, no redundancy |
| **MinIO** ⭐ | **Testing Artifactory setup** | **S3-compatible, mimics Artifactory, free, one Docker command** | You manage it |
| **Amazon S3** | Production, cloud | Highly scalable, managed | Requires AWS account, internet |
| **Artifactory** | Production, enterprise | Conan native support, full featured | Commercial license, complex setup |

**Recommendation for Testing**: Use **MinIO** to mimic your eventual Artifactory setup. MinIO uses the same S3-compatible REST API that Artifactory supports, so your code will work identically. You can test URL redirects, signed URLs, authentication, etc. without needing an Artifactory license.

**Important Note: MinIO vs Artifactory for Conan**

| Feature | Artifactory | MinIO | ConanCrates |
|---------|-------------|-------|-------------|
| **Native Conan Support** | ✅ Yes | ❌ No | **Not needed!** |
| **Parse conanfile.py** | ✅ Yes | ❌ No | **You parse it** |
| **Conan REST API** | ✅ Yes | ❌ No | **You provide it** |
| **Dependency Resolution** | ❌ Basic | ❌ No | **You use Conan CLI** |
| **File Storage** | ✅ Yes | ✅ Yes | **All you need!** |
| **S3-compatible API** | ✅ Yes | ✅ Yes | ✅ |

**The Architecture:**
```
ConanCrates = Conan Intelligence (parsing, resolution, API, UI)
MinIO/Artifactory = Dumb Storage (just stores .tar.gz files)
```

In your architecture, **ConanCrates handles all the Conan-specific logic**:
- You parse package metadata and store it in PostgreSQL/SQLite
- You use Conan CLI wrapper for dependency resolution
- You provide the REST API and beautiful UI
- Storage backend (MinIO/Artifactory) just stores binary blobs

**Why this is better than native Artifactory Conan support:**
- 🎨 Your UI instead of Artifactory's terrible UI
- 🧮 Real Conan dependency resolution (Artifactory's is limited)
- 🔍 Custom search, analytics, features
- 💰 Can use free MinIO instead of expensive Artifactory
- 🔓 Not locked into Artifactory

---

## Part 2: Configuring Storage

### Option 1: Local Filesystem (Current - Development Only)

**Already configured!** Files go to `media/binaries/` directory.

```python
# conancrates/settings.py (already set)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

**To enable real downloads** (local filesystem):

Change [download_views.py:36](d:\ConanCrates\packages\views\download_views.py:36):

```python
# Current (placeholder):
response = HttpResponse("Binary download: ...")

# Change to (real file):
if binary.binary_file:
    return FileResponse(
        binary.binary_file.open('rb'),
        as_attachment=True,
        filename=f"{package_name}-{version}-{binary_id}.tar.gz"
    )
else:
    return HttpResponse("Binary file not available", status=404)
```

**Limitations**:
- Files stored on server disk
- Not scalable beyond single server
- No redundancy
- Expensive for large files

---

### Option 2: MinIO (Self-Hosted S3)

**Best for testing your eventual Artifactory setup!**

MinIO is an open-source, S3-compatible object storage server. It's perfect for:
- **Testing Artifactory integration** - Same S3 API as Artifactory
- **Air-gapped environments** - Runs completely offline
- **Development** - One Docker command to get started
- **Cost-effective** - Free and open source

When you eventually move to Artifactory, your Django code will work identically because both use S3-compatible APIs.

#### Setup MinIO

```bash
# Using Docker
docker run -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=admin \
  -e MINIO_ROOT_PASSWORD=password123 \
  quay.io/minio/minio server /data --console-address ":9001"

# Create bucket
# Visit http://localhost:9001
# Login: admin/password123
# Create bucket: "conan-packages"
```

#### Configure Django for MinIO

```bash
pip install django-storages boto3
```

Update `conancrates/settings.py`:

```python
# Storage configuration
INSTALLED_APPS = [
    # ... existing apps ...
    'storages',
]

# MinIO/S3 settings
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

AWS_ACCESS_KEY_ID = 'admin'
AWS_SECRET_ACCESS_KEY = 'password123'
AWS_STORAGE_BUCKET_NAME = 'conan-packages'
AWS_S3_ENDPOINT_URL = 'http://localhost:9000'  # MinIO endpoint
AWS_S3_REGION_NAME = 'us-east-1'  # MinIO doesn't care, but boto3 requires it
AWS_S3_SIGNATURE_VERSION = 's3v4'
AWS_DEFAULT_ACL = None
AWS_S3_FILE_OVERWRITE = False
AWS_QUERYSTRING_AUTH = True  # Generate signed URLs for downloads
AWS_QUERYSTRING_EXPIRE = 3600  # URLs valid for 1 hour
```

**That's it!** Now when you upload files, they automatically go to MinIO instead of local disk.

#### How Downloads Work with MinIO

**Option A: Signed URLs (Recommended)**
```python
# Django generates a temporary signed URL
# User downloads directly from MinIO (fast, no Django overhead)
url = binary.binary_file.url  # boto3 generates signed URL
# URL: http://localhost:9000/conan-packages/binaries/xyz.tar.gz?signature=...
```

**Option B: Proxy through Django**
```python
# Django fetches from MinIO and streams to user
# Slower, but more control (auth, logging, etc.)
return FileResponse(binary.binary_file.open('rb'), ...)
```

---

### Option 3: Amazon S3 (Cloud Production)

Same as MinIO, but use real S3:

```python
# settings.py
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

AWS_ACCESS_KEY_ID = 'your-aws-key'
AWS_SECRET_ACCESS_KEY = 'your-aws-secret'
AWS_STORAGE_BUCKET_NAME = 'your-bucket-name'
AWS_S3_REGION_NAME = 'us-east-1'
# No AWS_S3_ENDPOINT_URL for real S3
```

**Cost**: S3 is very cheap ($0.023/GB/month + transfer)

---

### Option 4: Artifactory (Enterprise)

Artifactory has native Conan support, but **ConanCrates provides a better UI** while using Artifactory as the storage backend.

#### Architecture with Artifactory

```
User browses ConanCrates beautiful UI
    ↓
ConanCrates (Django) - metadata, search, UI
    ↓
Artifactory - actual file storage
```

**Your UI, their storage!**

#### Implementation Approaches

**Approach A: Use Artifactory's S3-Compatible API** (Recommended)

Artifactory supports S3 API, so you can use the same MinIO/S3 configuration:

```python
# settings.py
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

AWS_ACCESS_KEY_ID = 'artifactory-access-token'
AWS_SECRET_ACCESS_KEY = 'artifactory-secret-token'
AWS_STORAGE_BUCKET_NAME = 'conan-local'
AWS_S3_ENDPOINT_URL = 'https://artifactory.company.com/s3/'  # Artifactory S3 endpoint
AWS_S3_REGION_NAME = 'us-east-1'
```

**Approach B: Custom Artifactory Storage Backend**

For direct REST API integration:

```python
# packages/storage/artifactory.py
from django.core.files.storage import Storage
import requests

class ArtifactoryStorage(Storage):
    def __init__(self):
        self.base_url = 'https://artifactory.company.com/artifactory/conan-local'
        self.auth = ('user', 'api-token')

    def _save(self, name, content):
        # Upload to Artifactory
        url = f"{self.base_url}/{name}"
        response = requests.put(url, data=content, auth=self.auth)
        response.raise_for_status()
        return name

    def url(self, name):
        # Return direct Artifactory URL
        return f"{self.base_url}/{name}"

    def exists(self, name):
        url = f"{self.base_url}/{name}"
        response = requests.head(url, auth=self.auth)
        return response.status_code == 200
```

#### Download Patterns with Artifactory

**Individual Binary (URL Redirect):**
```python
def download_binary(request, package_name, version, binary_id):
    binary = get_object_or_404(BinaryPackage, ...)

    # Increment counter (your tracking)
    binary.download_count += 1
    binary.save()

    # Redirect to Artifactory
    artifactory_url = f"https://artifactory.company.com/artifactory/conan-local/{package_name}/{version}/{binary_id}.tar.gz"
    return HttpResponseRedirect(artifactory_url)
```

**Bundle (Proxy):**
```python
def download_bundle(request, package_name, version):
    # Resolve dependencies with Conan
    resolution = resolve_dependencies(...)

    # Create ZIP bundle on-the-fly
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zipf:
        for pkg in resolution['packages']:
            # Fetch from Artifactory
            url = f"https://artifactory.company.com/artifactory/conan-local/{pkg['name']}/{pkg['version']}/{pkg['package_id']}.tar.gz"
            response = requests.get(url, auth=('user', 'token'))

            # Add to bundle
            zipf.writestr(f"{pkg['name']}.tar.gz", response.content)

        zipf.writestr('bundle_info.json', json.dumps(resolution))

    # Stream to user
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename='bundle.zip')
```

**Why This Architecture?**
- ✅ ConanCrates provides beautiful UI (Artifactory UI is terrible)
- ✅ Artifactory handles storage/replication/enterprise features
- ✅ Use Conan resolution logic for bundles (Artifactory can't do this)
- ✅ Add custom features (analytics, custom search, etc.)

**When to use**: Large enterprise with existing Artifactory license.

---

## Part 3: Implementing Package Upload

Now let's add upload functionality. Here's what we need:

### 1. Upload View (API endpoint)

Create `packages/views/upload_views.py`:

```python
"""
Views for uploading packages
"""
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from packages.models import Package, PackageVersion, BinaryPackage
import hashlib


@login_required
@csrf_exempt  # In production, use proper CSRF/API tokens
def upload_binary(request, package_name, version):
    """
    Upload a binary package

    POST /packages/{name}/{version}/upload/

    Form data:
    - file: The binary .tar.gz file
    - os: Operating system
    - arch: Architecture
    - compiler: Compiler name
    - compiler_version: Compiler version
    - build_type: Release/Debug
    - package_id: Conan package ID
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    # Get or create package
    package, _ = Package.objects.get_or_create(
        name=package_name,
        defaults={
            'description': f'Package {package_name}',
            'author': request.user.username
        }
    )

    # Get or create version
    pkg_version, _ = PackageVersion.objects.get_or_create(
        package=package,
        version=version,
        defaults={'uploaded_by': request.user}
    )

    # Get file and metadata
    binary_file = request.FILES.get('file')
    if not binary_file:
        return JsonResponse({'error': 'No file provided'}, status=400)

    # Calculate checksum
    sha256 = hashlib.sha256()
    for chunk in binary_file.chunks():
        sha256.update(chunk)
    checksum = sha256.hexdigest()

    # Create binary package
    binary = BinaryPackage.objects.create(
        package_version=pkg_version,
        package_id=request.POST.get('package_id'),
        os=request.POST.get('os', ''),
        arch=request.POST.get('arch', ''),
        compiler=request.POST.get('compiler', ''),
        compiler_version=request.POST.get('compiler_version', ''),
        build_type=request.POST.get('build_type', ''),
        binary_file=binary_file,  # Django handles storage backend automatically!
        file_size=binary_file.size,
        sha256=checksum
    )

    return JsonResponse({
        'success': True,
        'package': package_name,
        'version': version,
        'package_id': binary.package_id,
        'checksum': checksum,
        'size': binary_file.size
    })
```

### 2. Add URL Route

```python
# packages/urls.py
urlpatterns = [
    # ... existing patterns ...
    path('packages/<str:package_name>/<str:version>/upload/',
         views.upload_binary, name='upload_binary'),
]
```

### 3. Upload Script (for users)

Create a script users can use to upload:

```bash
#!/bin/bash
# upload_to_conancrates.sh

PACKAGE_NAME=$1
VERSION=$2
BINARY_FILE=$3
PACKAGE_ID=$4

curl -X POST \
  -F "file=@$BINARY_FILE" \
  -F "package_id=$PACKAGE_ID" \
  -F "os=Linux" \
  -F "arch=x86_64" \
  -F "compiler=gcc" \
  -F "compiler_version=11" \
  -F "build_type=Release" \
  -u "username:password" \
  "http://localhost:8000/packages/$PACKAGE_NAME/$VERSION/upload/"
```

---

## Part 4: Conan Client Integration

To make ConanCrates work as a real Conan remote:

### What Conan Expects

Conan uses a REST API to interact with remotes. Key endpoints:

```
GET  /v2/conans/{name}/{version}/{channel}/{user}/packages/{package_id}/download_urls
GET  /v2/conans/{name}/{version}/{channel}/{user}/packages/{package_id}/conanmanifest.txt
POST /v2/conans/{name}/{version}/{channel}/{user}/packages/{package_id}/upload_urls
```

### Implementation Path

1. **Use Conan Server as reference** - Look at conan-server source code
2. **Implement V2 API** - Add endpoints matching Conan's expectations
3. **Configure in Conan** - `conan remote add conancrates http://localhost:8000`

**This is significant work** - requires implementing full Conan REST API spec.

**Alternative**: Use Artifactory or just support manual uploads for now.

---

## Part 5: Production Setup Example

### Docker Compose for Production

```yaml
version: '3.8'

services:
  # Django application
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - AWS_S3_ENDPOINT_URL=http://minio:9000
      - AWS_ACCESS_KEY_ID=admin
      - AWS_SECRET_ACCESS_KEY=secret123
    depends_on:
      - db
      - minio

  # PostgreSQL database
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: conancrates
      POSTGRES_USER: conancrates
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # MinIO object storage
  minio:
    image: quay.io/minio/minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: admin
      MINIO_ROOT_PASSWORD: secret123
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  minio_data:
```

---

## Summary: What You Need To Do

### For Real Downloads (5 minutes)

1. Choose storage backend (MinIO recommended for air-gapped)
2. Update `settings.py` with storage config
3. Change placeholder in `download_views.py` to real file serving
4. Test: Upload file via admin, download it

### For Uploads (1-2 hours)

1. Create `upload_views.py` with upload endpoint
2. Add authentication (Django auth or API tokens)
3. Add URL routes
4. Test with curl/Postman

### For Full Conan Client Integration (1-2 weeks)

1. Study Conan REST API v2 spec
2. Implement all required endpoints
3. Handle recipe uploads, package uploads, search
4. Test with real `conan upload` command

---

## Quick Start: Enable Real Files NOW

**5-minute setup for local filesystem:**

1. **Change download code**:

```python
# packages/views/download_views.py line 35-40
# Replace:
response = HttpResponse(...)

# With:
if binary.binary_file:
    return FileResponse(
        binary.binary_file.open('rb'),
        as_attachment=True,
        filename=f"{package_name}-{version}-{binary_id}.tar.gz"
    )
return HttpResponse("No file available", status=404)
```

2. **Upload a test file via Django admin**:
   - Go to http://localhost:8000/admin/packages/binarypackage/
   - Click on a binary
   - Upload a `.tar.gz` file to "Binary file" field
   - Save

3. **Test download**:
```bash
curl -O http://localhost:8000/packages/zlib/1.2.13/binaries/test123/download/
```

Done! You're now serving real files.

---

## Recommended Next Steps

1. ✅ **Enable real downloads** (5 min) - Change placeholder to FileResponse
2. ⬜ **Set up MinIO** (30 min) - Docker + config
3. ⬜ **Implement upload API** (2 hours) - Upload endpoint + auth
4. ⬜ **Test upload/download cycle** (1 hour) - End-to-end test
5. ⬜ **Add authentication** (2 hours) - Secure uploads
6. ⬜ **Conan client integration** (later) - Full REST API

**For your air-gapped use case**: MinIO + manual upload API is perfect. You don't need full Conan client integration if you're just bundling packages for air-gapped deployment.
