fn main() {
    println!("cargo:rustc-link-arg-bins=--nmagic");
    println!("cargo:rustc-link-arg-bins=-Tlink.x");
    // The network is not in the repository: export.py writes it from a run.
    println!("cargo:rerun-if-changed=net/net.rs");
    println!("cargo:rerun-if-changed=net/net.bin");
    if !std::path::Path::new("net/net.rs").exists() {
        panic!(
            "firmware/policy/net/ is missing: write it from a run with\n    \
             uv run firmware/policy/export.py exports/rl/<run>"
        );
    }
}
