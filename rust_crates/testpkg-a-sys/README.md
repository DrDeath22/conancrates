# testpkg-a-sys

Rust FFI bindings for testpkg_a 1.0.0.

This crate contains pre-compiled binaries from the Conan package.

## Libraries included:

- testpkg_a

## Usage

Add this to your `Cargo.toml`:

```toml
[dependencies]
testpkg-a-sys = "1.0.0"
```

Then use it in your code:

```rust
extern crate testpkg_a_sys;

// Your code here
```

## Building

This crate includes pre-compiled static libraries and does not require compilation
of the C/C++ source code. The libraries are linked during the Rust build process.

## Source

Generated from Conan package: testpkg_a/1.0.0
