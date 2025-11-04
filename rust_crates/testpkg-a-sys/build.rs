fn main() {
    // Tell cargo where to find the pre-compiled libraries
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").unwrap();
    let lib_path = std::path::Path::new(&manifest_dir).join("native/current");

    println!("cargo:rustc-link-search=native={}", lib_path.display());

    // Link the libraries
    println!("cargo:rustc-link-lib=static=testpkg_a");

    // Re-run if libraries change
    println!("cargo:rerun-if-changed=native/");
}
