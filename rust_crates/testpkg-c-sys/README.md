# testpkg-c-sys

Rust FFI bindings for testpkg_c 1.0.0.

This crate contains pre-compiled binaries from the Conan package.

## Libraries included:

- testpkg_c

## Usage

Add this to your `Cargo.toml`:

```toml
[dependencies]
testpkg-c-sys = "1.0.0"
```

Then use it in your code:

```rust
extern crate testpkg_c_sys;

// Your code here
```

## Building

This crate includes pre-compiled static libraries and does not require compilation
of the C/C++ source code. The libraries are linked during the Rust build process.

## Source

Generated from Conan package: testpkg_c/1.0.0
