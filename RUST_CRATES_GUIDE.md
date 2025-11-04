# Rust Crates Guide

ConanCrates automatically generates Rust `-sys` crates from Conan packages, allowing Rust developers to easily use C/C++ libraries distributed through ConanCrates.

## Overview

When you upload a Conan package to ConanCrates, a Rust crate is automatically generated containing:
- Pre-compiled static libraries
- C/C++ header files
- Cargo build script (build.rs)
- Rust FFI bindings template
- Path-based dependency declarations

## Uploading Packages with Rust Crates

Rust crate generation happens automatically during package upload:

```bash
python conancrates.py upload mylib/1.0.0 -pr <profile>
```

This will:
1. Upload the Conan package binary
2. Generate a Rust `-sys` crate
3. Upload the `.crate` archive to the server
4. Make it available for download

### Disable Rust Crate Generation

If you don't want to generate Rust crates:

```bash
python conancrates.py upload mylib/1.0.0 -pr <profile> --no-rust
```

## Downloading Rust Crates

### Option 1: CLI Download (Recommended)

Download a Rust crate and all its dependencies in one command:

```bash
python conancrates.py download mylib/1.0.0 --crates --package-id <package_id>
```

**Finding the package_id:**
1. Visit: `http://localhost:8000/packages/mylib/1.0.0`
2. Look for the binary that matches your platform
3. Copy the package_id value

**What this does:**
- Downloads the main crate (e.g., `mylib-sys-1.0.0.crate`)
- Downloads all dependency crates automatically
- Saves to `./rust_crates/` directory
- Dependencies already have correct path references

**Example:**
```bash
# Download testpkg_a and its dependencies (testpkg_b, testpkg_c)
python conancrates.py download testpkg_a/1.0.0 --crates --package-id 9ac042e03e2f9a8390927c4e4bfcd91be2f5cb2e

# Output:
# Downloaded testpkg-a-sys-1.0.0.crate (1.8 KB)
# Downloaded testpkg-b-sys-1.0.0.crate (1.8 KB)
# Downloaded testpkg-c-sys-1.0.0.crate (1.7 KB)
```

### Option 2: Web UI Download

1. Navigate to the package page
2. Click the "Crate" download link under the Rust section
3. This downloads only the single crate (no dependencies)

### Option 3: API Endpoint

**Get crate by package_id:**
```bash
curl -O "http://localhost:8000/packages/mylib/1.0.0/binaries/<package_id>/rust-crate/"
```

**Get crate by profile settings:**
```bash
curl -O "http://localhost:8000/api/packages/mylib/1.0.0/rust-crate?os=Windows&arch=x86_64&compiler=gcc&compiler_version=11&build_type=Release"
```

## Using Downloaded Crates

### Step 1: Extract the Crates

```bash
cd rust_crates
tar -xzf mylib-sys-1.0.0.crate
# Extract dependencies too:
tar -xzf deplib-sys-1.0.0.crate
```

### Step 2: Add to Your Rust Project

In your `Cargo.toml`:

```toml
[dependencies]
mylib-sys = { version = "1.0.0", path = "./rust_crates/mylib-sys" }
```

**Note:** Dependencies are already configured with path references inside each crate's Cargo.toml, so you only need to reference the top-level crate.

### Step 3: Build Your Project

```bash
cargo build
```

The build script will automatically:
- Link the pre-compiled static libraries
- Set up the correct library search paths
- Link any transitive dependencies

## Crate Structure

Each generated Rust crate has the following structure:

```
mylib-sys/
├── Cargo.toml          # Package manifest with dependencies
├── build.rs            # Build script that links libraries
├── README.md           # Usage documentation
├── src/
│   └── lib.rs          # Rust FFI bindings (template)
├── native/
│   └── current/        # Pre-compiled libraries (.lib, .a, .so, .dylib)
└── include/            # C/C++ header files
```

### Cargo.toml Example

```toml
[package]
name = "mylib-sys"
version = "1.0.0"
edition = "2021"
links = "mylib"

[dependencies]
# Path dependencies are set automatically
deplib-sys = { version = "1.0.0", path = "../deplib-sys" }
```

### build.rs Example

```rust
fn main() {
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").unwrap();
    let lib_path = std::path::Path::new(&manifest_dir).join("native/current");

    println!("cargo:rustc-link-search=native={}", lib_path.display());
    println!("cargo:rustc-link-lib=static=mylib");
    println!("cargo:rerun-if-changed=native/");
}
```

## Adding FFI Bindings

The generated `src/lib.rs` is a template. You need to add actual FFI declarations:

### Manual Approach

```rust
// src/lib.rs
extern "C" {
    pub fn my_function(arg: i32) -> i32;
    pub fn another_function() -> *const i8;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_my_function() {
        unsafe {
            let result = my_function(42);
            assert_eq!(result, 42);
        }
    }
}
```

### Automated with bindgen

For complex libraries, use `bindgen` to auto-generate bindings:

1. Add bindgen to build dependencies in `Cargo.toml`:
```toml
[build-dependencies]
bindgen = "0.69"
```

2. Update `build.rs` to generate bindings:
```rust
use std::env;
use std::path::PathBuf;

fn main() {
    // Link libraries
    let manifest_dir = env::var("CARGO_MANIFEST_DIR").unwrap();
    let lib_path = PathBuf::from(&manifest_dir).join("native/current");
    println!("cargo:rustc-link-search=native={}", lib_path.display());
    println!("cargo:rustc-link-lib=static=mylib");

    // Generate bindings
    let bindings = bindgen::Builder::default()
        .header(PathBuf::from(&manifest_dir)
            .join("include/mylib/mylib.h")
            .to_str()
            .unwrap())
        .generate()
        .expect("Unable to generate bindings");

    let out_path = PathBuf::from(env::var("OUT_DIR").unwrap());
    bindings
        .write_to_file(out_path.join("bindings.rs"))
        .expect("Couldn't write bindings!");
}
```

3. Include the generated bindings in `src/lib.rs`:
```rust
#![allow(non_upper_case_globals)]
#![allow(non_camel_case_types)]
#![allow(non_snake_case)]

include!(concat!(env!("OUT_DIR"), "/bindings.rs"));
```

## Dependency Management

### Automatic Path Dependencies

When you download crates using the CLI tool, dependencies are automatically configured:

```toml
# In mylib-sys/Cargo.toml
[dependencies]
deplib-sys = { version = "1.0.0", path = "../deplib-sys" }
```

This means:
- All crates must be extracted to the same directory
- Dependencies work immediately without manual configuration
- No need to publish to crates.io for private use

### Publishing to crates.io

If you want to publish to crates.io, you'll need to:

1. Publish dependencies first (bottom-up)
2. Change path dependencies to version dependencies
3. Add metadata (description, license, repository)

Example for publishing:
```toml
[package]
description = "Rust FFI bindings for mylib"
license = "MIT"
repository = "https://github.com/user/mylib-sys"

[dependencies]
deplib-sys = "1.0.0"  # Remove path, use version only
```

## API Reference

### Package Info API

Get package information including dependencies:

```bash
GET /api/packages/<name>/<version>/binaries/<package_id>/info
```

**Response:**
```json
{
  "package": {
    "name": "mylib",
    "version": "1.0.0",
    "package_id": "abc123..."
  },
  "rust_crate": {
    "available": true,
    "download_url": "/packages/mylib/1.0.0/binaries/abc123/rust-crate/"
  },
  "dependencies": [
    {
      "name": "deplib",
      "version": "1.0.0",
      "package_id": "def456...",
      "rust_crate_url": "/packages/deplib/1.0.0/binaries/def456/rust-crate/"
    }
  ]
}
```

### Profile-based Download API

Get crate matching your platform settings:

```bash
GET /api/packages/<name>/<version>/rust-crate?os=Windows&arch=x86_64&compiler=gcc&compiler_version=11&build_type=Release
```

**Response:**
```json
{
  "package": "mylib",
  "version": "1.0.0",
  "package_id": "abc123...",
  "rust_crate_url": "/packages/mylib/1.0.0/binaries/abc123/rust-crate/",
  "dependencies": [...]
}
```

## Platform Support

Rust crates include binaries for the specific platform they were built on. The crate name pattern is:

```
<package_name>-sys-<version>.crate
```

Each crate contains binaries for one specific platform configuration (OS/arch/compiler). If you need multi-platform support:

1. Upload packages for each platform with different profiles
2. Download the appropriate crate for your target platform
3. Or use Cargo's platform-specific dependencies:

```toml
[target.'cfg(windows)'.dependencies]
mylib-sys = { version = "1.0.0", path = "./rust_crates/mylib-sys-windows" }

[target.'cfg(unix)'.dependencies]
mylib-sys = { version = "1.0.0", path = "./rust_crates/mylib-sys-linux" }
```

## Troubleshooting

### Crate Not Available

**Problem:** "Rust crate not available" when trying to download

**Solutions:**
- The package may have been uploaded with `--no-rust`
- Re-upload the package without the `--no-rust` flag
- Check that the package was uploaded (not just the recipe)

### Dependency Not Found

**Problem:** Cargo can't find dependency crates

**Solutions:**
- Make sure all crates are extracted to the same directory
- Verify path references in Cargo.toml point to `../<dep-name>`
- Check that dependency crates were downloaded (use `--crates` flag)

### Link Errors

**Problem:** Undefined symbols or link errors during build

**Solutions:**
- Check that the binary was built for your platform
- Verify the compiler matches (gcc vs msvc vs clang)
- Ensure all transitive dependencies were downloaded
- Check library file extensions (.lib on Windows, .a on Unix)

### Wrong Platform

**Problem:** Downloaded crate doesn't match your system

**Solutions:**
- Verify you're using the correct package_id for your platform
- Check available binaries on the package web page
- Use a Conan profile that matches your system

## Examples

### Example 1: Simple Library

```bash
# Upload
python conancrates.py upload mymath/1.0.0 -pr default

# Download
python conancrates.py download mymath/1.0.0 --crates --package-id abc123

# Extract
cd rust_crates && tar -xzf mymath-sys-1.0.0.crate

# Use in Rust project
cat >> Cargo.toml <<EOF
[dependencies]
mymath-sys = { version = "1.0.0", path = "./rust_crates/mymath-sys" }
EOF
```

### Example 2: Library with Dependencies

```bash
# Upload with dependencies
python conancrates.py upload myapp/2.0.0 -pr default --with-dependencies

# Download (automatically gets all deps)
python conancrates.py download myapp/2.0.0 --crates --package-id def456

# Extract all
cd rust_crates
for crate in *.crate; do tar -xzf "$crate"; done

# Use top-level crate (dependencies already configured)
cat >> Cargo.toml <<EOF
[dependencies]
myapp-sys = { version = "2.0.0", path = "./rust_crates/myapp-sys" }
EOF
```

### Example 3: Multi-Platform Support

```bash
# Build and upload for Windows
conan create . --profile=windows
python conancrates.py upload mylib/1.0.0 -pr windows

# Build and upload for Linux
conan create . --profile=linux
python conancrates.py upload mylib/1.0.0 -pr linux

# Download Windows version
python conancrates.py download mylib/1.0.0 --crates --package-id <windows_id>

# Download Linux version to different directory
python conancrates.py download mylib/1.0.0 --crates --package-id <linux_id> -o ./rust_crates_linux
```

## Testing Downloaded Crates

After downloading Rust crates, you should verify they work correctly before integrating them into your project.

### Quick Test: Extract and Build

1. **Extract the crate archives:**
```bash
cd rust_crates
tar -xzf mylib-sys-1.0.0.crate
# Extract dependencies too
tar -xzf deplib-sys-1.0.0.crate
```

2. **Try building the crate directly:**
```bash
cd mylib-sys
cargo build
```

This will:
- Verify the Cargo.toml is valid
- Run the build.rs script to link libraries
- Check that all path dependencies are found
- Compile the Rust FFI bindings

**Expected result:** Build should succeed with warnings about unused code (since the template lib.rs has no actual bindings yet).

### Full Test: Create Test Project

For a more thorough test, create a simple Rust project that uses the crate:

1. **Create a test project:**
```bash
# Navigate to where you want to create the test project
cd /path/to/your/workspace

# Create a new Rust binary project
cargo new crate_test
cd crate_test
```

This creates:
```
crate_test/
├── Cargo.toml
└── src/
    └── main.rs
```

2. **Add the crate as a dependency in Cargo.toml:**

Open `Cargo.toml` and add your crate under `[dependencies]`:

```toml
[package]
name = "crate_test"
version = "0.1.0"
edition = "2021"

[dependencies]
mylib-sys = { version = "1.0.0", path = "../rust_crates/mylib-sys" }
```

**Important:** The path is relative to the Cargo.toml file. Adjust based on where you extracted the crates.

3. **Use the crate in src/main.rs:**

```rust
fn main() {
    println!("Testing mylib-sys crate...");

    // If you've added actual FFI bindings:
    // unsafe {
    //     let result = mylib_sys::my_function(42);
    //     println!("Result: {}", result);
    // }

    println!("Crate linked successfully!");
}
```

4. **Build the test project:**
```bash
cargo build
```

This will:
- Download and compile any additional dependencies
- Build the mylib-sys crate and its dependencies
- Link everything together

5. **Run the test:**
```bash
cargo run
```

Expected output:
```
   Compiling mylib-sys v1.0.0 (/path/to/rust_crates/mylib-sys)
   Compiling crate_test v0.1.0 (/path/to/crate_test)
    Finished dev [unoptimized + debuginfo] target(s) in 2.34s
     Running `target/debug/crate_test`
Testing mylib-sys crate...
Crate linked successfully!
```

### Adding Rust Tests

To add proper Rust unit tests that verify the crate works:

1. **Create a test in src/main.rs or src/lib.rs:**

If you created a binary project (with `cargo new`), add tests to `src/main.rs`:

```rust
fn main() {
    println!("Testing mylib-sys crate...");
    println!("Crate linked successfully!");
}

#[cfg(test)]
mod tests {
    // Import the crate
    // use mylib_sys::*;

    #[test]
    fn test_crate_links() {
        // Basic test that the crate compiles and links
        // This will fail at compile time if linking is broken
        assert!(true);
    }

    #[test]
    fn test_ffi_function() {
        // Example test if you have actual FFI bindings:
        // unsafe {
        //     let result = mylib_sys::my_function(42);
        //     assert_eq!(result, 42);
        // }

        // For now, just verify compilation works
        println!("FFI bindings compiled successfully");
    }
}
```

2. **Or create a library project with tests:**

For more extensive testing, create a library project instead:

```bash
cargo new --lib crate_test
cd crate_test
```

Edit `src/lib.rs`:

```rust
// Re-export the FFI crate
pub use mylib_sys;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mylib_links() {
        // Test that the crate links correctly
        // This will fail if there are linker errors
    }

    #[test]
    fn test_dependency_chain() {
        // If mylib-sys has dependencies, they should also link
        // The build.rs in each crate handles this
    }

    // Add actual FFI tests here when you have bindings:
    // #[test]
    // fn test_my_function() {
    //     unsafe {
    //         let result = mylib_sys::my_function(42);
    //         assert_eq!(result, 42);
    //     }
    // }
}
```

3. **Run the tests:**

```bash
cargo test
```

Expected output:
```
   Compiling deplib-sys v1.0.0 (/path/to/rust_crates/deplib-sys)
   Compiling mylib-sys v1.0.0 (/path/to/rust_crates/mylib-sys)
   Compiling crate_test v0.1.0 (/path/to/crate_test)
    Finished test [unoptimized + debuginfo] target(s) in 3.21s
     Running unittests src/main.rs (target/debug/deps/crate_test-xxx)

running 2 tests
test tests::test_crate_links ... ok
test tests::test_ffi_function ... ok

test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
```

4. **Run tests with verbose output:**

```bash
cargo test -- --nocapture
```

This shows all println! output from your tests, useful for debugging.

### Integration Test Example

For integration tests, create a `tests/` directory:

```bash
mkdir tests
```

Create `tests/integration_test.rs`:

```rust
// Integration test for mylib-sys

#[test]
fn test_mylib_integration() {
    // Test that we can use the crate in integration tests
    // This simulates how external crates would use mylib-sys

    // Basic smoke test - if this compiles and runs, linking works
    assert!(true);
}

// Example with actual FFI usage:
// #[test]
// fn test_full_workflow() {
//     unsafe {
//         // Initialize
//         mylib_sys::init();
//
//         // Use functions
//         let result = mylib_sys::process_data(42);
//         assert_eq!(result, 84);
//
//         // Cleanup
//         mylib_sys::cleanup();
//     }
// }
```

Run integration tests:
```bash
cargo test --test integration_test
```

### Verify Crate Contents

Check that the crate has all expected files:

```bash
cd rust_crates/mylib-sys
ls -R
```

**Expected structure:**
```
mylib-sys/
├── Cargo.toml          # Package manifest with dependencies
├── build.rs            # Build script that links libraries
├── README.md           # Usage documentation
├── src/
│   └── lib.rs          # Rust FFI bindings (template)
├── native/
│   └── current/        # Pre-compiled libraries (.lib, .a, .so, .dylib)
└── include/            # C/C++ header files
```

### Check Dependencies

Verify that dependencies are correctly referenced:

```bash
cd rust_crates/mylib-sys
cat Cargo.toml | grep -A 2 "\[dependencies\]"
```

**Expected output:**
```toml
[dependencies]
deplib-sys = { version = "1.0.0", path = "../deplib-sys" }
```

### Test Dependency Chain

If your crate has dependencies, verify the entire chain builds:

```bash
cd rust_crates/mylib-sys
cargo build -v
```

The verbose output will show:
- Each dependency being compiled
- Library search paths being set
- Static libraries being linked

### Common Test Failures

**Build fails with "package not found":**
- Dependency crates not extracted to the same directory
- Path in Cargo.toml is incorrect
- Check: `ls ../deplib-sys` should list the dependency crate

**Link errors about undefined symbols:**
- Binary was built for wrong platform
- Verify with: `file native/current/*.a` (Unix) or check .lib files (Windows)
- Re-download with correct package_id for your platform

**Cargo.toml parse errors:**
- Crate archive may be corrupted
- Re-download and extract

## Best Practices

1. **Always download with --crates flag** to get dependencies automatically
2. **Extract all crates to the same directory** to enable path dependencies
3. **Test crates immediately after download** to catch issues early
4. **Use meaningful commit messages** when updating crate bindings
5. **Test FFI bindings** with Rust's `#[test]` framework
6. **Document unsafe code** and FFI usage in your project
7. **Keep header files** in the crate for reference when writing bindings
8. **Version lock dependencies** in your main project's Cargo.lock
9. **CI/CD:** Automate downloads, extraction, and testing in your build pipeline

## Related Documentation

- [CLI Guide](CLI_GUIDE.md) - General CLI usage
- [Upload Guide](UPLOAD_GUIDE.md) - Uploading packages
- [Web UI Guide](WEB_UI_GUIDE.md) - Using the web interface
- [Rust FFI Documentation](https://doc.rust-lang.org/nomicon/ffi.html) - Official Rust FFI guide
- [bindgen Documentation](https://rust-lang.github.io/rust-bindgen/) - Auto-generating bindings
