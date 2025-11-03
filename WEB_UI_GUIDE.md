# ConanCrates Web UI Guide

This guide explains how to browse and download packages using the ConanCrates web interface.

**For CLI tool usage, see [CLI_GUIDE.md](CLI_GUIDE.md)** - recommended for Conan users.

## Accessing the Web UI

Open your browser to: http://localhost:8000/

## Browsing Packages

### Homepage

The homepage shows:
- List of all available packages
- Search functionality
- Package count and statistics

### Package Detail Page

Click on any package to see:
- Package information (name, author, description, license)
- All available versions
- Binaries for selected version
- Dependencies per binary
- Recipe content (conanfile.py)

## Downloading Packages

Each binary in the table has two download methods:

### Method 1: For Conan Users (Recommended)

Each binary shows:

1. **Profile settings** needed to match that binary:
```ini
[settings]
os=Windows
arch=x86_64
compiler=gcc
compiler.version=11
build_type=Release
```

2. **Suggested profile filename** (e.g., `windows_gcc11_release`)

3. **Complete download command**:
```bash
python conancrates.py download package_name/1.0.0 -pr windows_gcc11_release
```

**How to use:**
1. Copy the profile settings shown
2. Save to `~/.conan2/profiles/` with the suggested filename
   - Windows: `%USERPROFILE%\.conan2\profiles\windows_gcc11_release`
   - Linux/Mac: `~/.conan2/profiles/windows_gcc11_release`
3. Run the download command shown
4. Package + dependencies will be downloaded to `./conan_packages/`

**Benefits:**
- Gets package + all dependencies
- Uses profile matching to ensure correct binaries
- Integrates with your Conan workflow
- Can restore to Conan cache

### Method 2: For Non-Conan Users

Click the download links directly on the package page:

#### 📂 Binary Download

Downloads the **extracted binary** in a ready-to-use format:

```
package_name-version-platform.zip
└── package_name-version-platform/
    ├── include/          # Header files
    ├── lib/              # Library files (.a, .lib, .so, .dll)
    ├── bin/              # Executables (if any)
    └── cmake/            # CMake package config files
```

**Use when:** You want to use the library without Conan (copy headers/libs to your project).

#### 🗂️ Bundle Download

Downloads the **extracted bundle** with package + all dependencies:

```
package_name-version-bundle.zip
└── package_name-version-bundle/
    ├── include/          # All headers (main + dependencies, interlaced)
    ├── lib/              # All libraries (main + dependencies)
    ├── bin/              # All executables
    └── cmake/            # All CMake configs (interlaced)
```

**Use when:** You want all dependencies in one place, ready to link without Conan.

**Interlaced means:** Files from different packages are combined in the same directory structure, ready for your build system to find them.

## Understanding the Binary Table

Each binary is shown in a table with these columns:

- **OS**: Operating system (Linux, Windows, macOS)
- **Architecture**: CPU architecture (x86_64, armv8, x86)
- **Compiler**: Compiler used (gcc, msvc, clang, apple-clang) + version
- **Build Type**: Release or Debug
- **Dependencies**: Expandable list (click to see all dependencies)
- **Size**: Binary file size
- **Downloads**: Download count
- **Action**: Download options (Conan CLI or direct downloads)

**Note:** The same package/version may have multiple binaries for different platforms.

## Dependencies

Each binary shows its dependencies:
- Click the summary to expand and see all dependencies
- Each dependency is a clickable link to its package page
- Dependencies are automatically included in Bundle downloads
- Dependencies vary by binary (different platforms may have different deps)

## Recipe Download

If you want the Conan recipe (conanfile.py):

1. Go to package detail page
2. Scroll to "📄 Recipe (conanfile.py)" section
3. Click **View Recipe** (opens in new tab) or **Download conanfile.py**
4. Or click **Show Recipe Content** to expand inline

## Search and Filtering

Use the search box on the homepage to find packages by:
- Package name
- Description keywords
- Author name

Click on Topics to filter by category.

## Typical Workflows

### Workflow 1: Conan User Downloads Package

1. Browse to package page
2. Select version from dropdown
3. Find the binary for your platform
4. Copy the profile settings shown
5. Save as `~/.conan2/profiles/[suggested_name]`
6. Run the download command shown
7. Package + dependencies download to `./conan_packages/`

### Workflow 2: Non-Conan User Needs Library

1. Find the package you need
2. Download the **Binary** for your platform
3. Extract the ZIP
4. Copy `include/` headers to your project
5. Link against libraries in `lib/`
6. Use CMake config from `cmake/` (optional)

### Workflow 3: Non-Conan User Needs Package + Dependencies

1. Find the main package you need
2. Download the **Bundle** for your platform
3. Extract the ZIP
4. All headers and libraries are ready in `include/` and `lib/`
5. No need to download dependencies separately!

## Example: Downloading with Profile

Let's say you're on Windows with gcc 11, Release build:

**On the package page, you'll see:**

```
For Conan Users:
Create profile matching this binary:

[settings]
os=Windows
arch=x86_64
compiler=gcc
compiler.version=11
build_type=Release

Save as: ~/.conan2/profiles/windows_gcc11_release

Then download:
python conancrates.py download zlib/1.2.13 -pr windows_gcc11_release
```

**Steps:**
1. Create file `C:\Users\YourName\.conan2\profiles\windows_gcc11_release`
2. Paste the profile settings shown
3. Run: `python conancrates.py download zlib/1.2.13 -pr windows_gcc11_release`
4. Done! Package downloaded to `./conan_packages/zlib-1.2.13/`

## Package Information

Each package page shows:
- **License**: Software license
- **Homepage**: Link to project website (if available)
- **Download Count**: Total downloads
- **Topics**: Categories/tags
- **Author**: Package uploader
- **Upload Date**: When the version was uploaded
- **Recipe Revision**: Conan recipe revision hash
- **Conan Version**: Conan version used to create package

## Direct URLs

You can link directly to:

- **Package list**: http://localhost:8000/packages/
- **Specific package**: http://localhost:8000/packages/zlib/
- **Specific version**: http://localhost:8000/packages/zlib/?version=1.2.13

## Download Formats Explained

### Conan CLI Download (Recommended)

Using `python conancrates.py download`:
- Downloads recipe (conanfile.py)
- Downloads all matching binaries (based on profile)
- Downloads all dependencies (from pre-computed graph)
- Can restore to Conan cache
- Maintains Conan metadata

### Binary (Extracted ZIP)

Direct download from web UI:
- Single binary package only
- No dependencies included
- No Conan metadata
- Ready-to-use headers/libs

### Bundle (Extracted ZIP)

Direct download from web UI:
- Main package + all dependencies
- Files interlaced (merged into same folders)
- No Conan metadata
- Ready-to-use headers/libs

## Limitations of Web UI Downloads

**What Web UI Downloads Do NOT Include:**
- Conan metadata (package_info, settings, options)
- Conan cache integration
- Profile-based matching for CLI
- Automatic dependency version resolution

**For Full Conan Integration:** Use the CLI tool with `-pr` flag (see [CLI_GUIDE.md](CLI_GUIDE.md))

## Tips

1. **Use the profile shown** - Each binary shows the exact profile needed
2. **Copy suggested profile name** - Makes it easier to remember which profile is for what
3. **Check dependencies** - Expand to see what will be included
4. **Verify platform** - Make sure OS/arch/compiler match your system
5. **Bundle saves time** - For non-Conan users, bundle includes everything

## See Also

- **[CLI_GUIDE.md](CLI_GUIDE.md)** - Complete CLI tool documentation
- **[README.md](README.md)** - Project overview
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Server setup
- **[UPLOAD_GUIDE.md](UPLOAD_GUIDE.md)** - Manual upload via Django admin
