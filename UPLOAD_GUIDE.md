# How to Upload Binary Files

This guide shows you how to upload Conan binary packages to ConanCrates using the Django admin interface.

## Quick Start (5 minutes)

### 1. Create the MinIO Bucket (One-Time Setup)

**Before uploading, you must create the bucket:**

1. Open http://localhost:9001 in your browser
2. Login: `admin` / `password123`
3. Click "Buckets" → "Create Bucket"
4. Bucket name: `conan-packages`
5. Click "Create Bucket"

✅ You only need to do this once!

### 2. Access Django Admin

1. Open http://localhost:8000/admin/
2. Login: `admin` / `admin`

### 3. Find a Binary Package to Upload To

1. Click **"Binary packages"** under the PACKAGES section
2. You'll see a list like this:

```
Binary Packages
┌──────────────────────────────────────────────────────────────┐
│ zlib/1.2.13 - Linux/x86_64/gcc/Release                       │
│ boost/1.81.0 - Linux/x86_64/gcc/Release                      │
│ openssl/3.0.0 - Linux/x86_64/gcc/Release                     │
└──────────────────────────────────────────────────────────────┘
```

3. Click on any row to edit

### 4. Upload the File

You'll see a form with many fields. Scroll down to find:

```
Binary file:    [Currently: (no file)]
                [Choose File] [No file chosen]
```

**Click "Choose File"** and select any file from your computer.

For testing, you can use:
- A text file
- A zip file
- Any .tar.gz file
- Even a random file just to test

### 5. Save

Click **"Save"** or **"Save and continue editing"** at the bottom.

✅ **The file is now uploaded to MinIO!**

## Verify the Upload

### Option 1: Check in MinIO Console

1. Go to http://localhost:9001
2. Click on "conan-packages" bucket
3. Click "Browse"
4. You should see your uploaded file!

### Option 2: Download from ConanCrates

1. Go to http://localhost:8000/packages/
2. Click on the package you uploaded to
3. Click the download link
4. **The actual file downloads** (not a placeholder!)

## Understanding the Upload

### What Happens When You Upload?

```
Django Admin
    ↓
You click "Save"
    ↓
Django receives file
    ↓
boto3 library uploads file to MinIO (port 9000)
    ↓
MinIO stores file in "conan-packages" bucket
    ↓
Django saves the file path in the database
    ↓
Upload complete!
```

### Where is the File Stored?

**NOT on your local disk!** It's stored in MinIO:

- MinIO URL: http://localhost:9000
- Bucket: `conan-packages`
- Path format: `binaries/package_name/version/binary_id/filename.tar.gz`

### How to View the File?

**Option 1: MinIO Console**
- http://localhost:9001 → Buckets → conan-packages → Browse

**Option 2: Download from ConanCrates**
- http://localhost:8000/packages/package_name/ → Click download link

## Creating Sample Data First

If you don't have any packages yet, create sample data:

```bash
python create_sample_data.py
```

This creates:
- 6 sample packages (zlib, boost, openssl, fmt, gtest, nlohmann_json)
- Multiple versions and binaries
- You can then upload files to these binaries

## Upload Real Conan Packages

For real Conan packages:

1. Build your C++ package with Conan:
   ```bash
   conan create . --build=missing
   ```

2. Find the package in Conan cache:
   ```bash
   # On Windows
   %USERPROFILE%\.conan2\p\

   # On Linux/Mac
   ~/.conan2/p/
   ```

3. The binary is a `.tar.gz` file in the package folder

4. Upload this `.tar.gz` file through Django admin

## Troubleshooting

### "No file chosen" - Can't upload?

Make sure the bucket exists:
1. Go to http://localhost:9001
2. Login: admin/password123
3. Check if "conan-packages" bucket exists
4. If not, create it

### Upload succeeds but file not in MinIO?

Check Django settings:
1. Open `conancrates/settings.py`
2. Verify `USE_MINIO = True`
3. Restart Django server: Ctrl+C, then `python manage.py runserver`

### "Access Denied" error?

Check MinIO credentials in settings.py:
```python
AWS_ACCESS_KEY_ID = 'admin'
AWS_SECRET_ACCESS_KEY = 'password123'
```

### Can't see Django admin?

Make sure you created a superuser:
```bash
python manage.py createsuperuser
```

Or use the sample data script which creates admin/admin user.

## Advanced: Uploading via API (Future)

Currently, uploads are only available through Django admin.

To implement API uploads, you would:
1. Create an upload endpoint in `packages/views/upload_views.py`
2. Add authentication (API tokens)
3. Accept multipart form data
4. Validate and save the file

See [STORAGE_AND_UPLOAD.md](STORAGE_AND_UPLOAD.md) Part 3 for implementation details.

## File Upload Flow Diagram

```
┌─────────────────┐
│  Django Admin   │ ← You upload file here
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Django Backend  │ ← Validates, processes
│  (FileField)    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  boto3 Library  │ ← Handles S3 protocol
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  MinIO Server   │ ← Stores the file
│  (port 9000)    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ conan-packages  │ ← File lives here
│     bucket      │
└─────────────────┘
```

## Download Flow Diagram

```
┌─────────────────┐
│ User clicks     │
│ "Download"      │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Django checks   │ ← Verifies binary exists
│ database        │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Django opens    │ ← Opens file from MinIO
│ binary_file     │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ FileResponse    │ ← Streams to browser
│ streams file    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ User receives   │ ← Download starts
│ file            │
└─────────────────┘
```

## Next Steps

1. ✅ Create MinIO bucket (`conan-packages`)
2. ✅ Run sample data script (`python create_sample_data.py`)
3. ✅ Upload a test file through Django admin
4. ✅ Download it to verify it works
5. 🎯 Start uploading real Conan packages!

---

**Note**: This is the admin interface for managing packages. In the future, you can implement:
- Web UI for uploading (file upload form)
- REST API for programmatic uploads
- Conan client integration (`conan upload`)
