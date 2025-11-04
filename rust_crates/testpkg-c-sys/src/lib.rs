//! Rust FFI bindings for testpkg_c
//!
//! This crate provides pre-compiled binaries for testpkg_c.
//! The binaries are linked statically.

#![allow(non_upper_case_globals)]
#![allow(non_camel_case_types)]
#![allow(non_snake_case)]

// TODO: Add your FFI declarations here
// You can use bindgen to auto-generate bindings from the C headers in include/
//
// Example:
// extern "C" {
//     pub fn my_function() -> i32;
// }

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_link() {
        // Add a test that uses your FFI functions
    }
}
