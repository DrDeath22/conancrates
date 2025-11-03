from django.db import models


class BinaryPackage(models.Model):
    """
    Represents a compiled binary for a specific configuration.
    One PackageVersion can have many BinaryPackages (different OS, compiler, arch, etc.)
    """
    package_version = models.ForeignKey('PackageVersion', on_delete=models.CASCADE, related_name='binaries')
    package_id = models.CharField(max_length=64, unique=True, db_index=True,
                                   help_text="Conan's unique package ID for this binary")

    # Configuration (settings)
    os = models.CharField(max_length=50, blank=True)
    arch = models.CharField(max_length=50, blank=True)
    compiler = models.CharField(max_length=50, blank=True)
    compiler_version = models.CharField(max_length=50, blank=True)
    build_type = models.CharField(max_length=50, blank=True)  # Debug, Release, etc.

    # Additional options (JSON field for flexibility)
    options = models.JSONField(default=dict, blank=True)

    # Dependency graph from conan graph info (stores exact package_ids of dependencies)
    dependency_graph = models.JSONField(default=dict, blank=True,
                                       help_text="Full Conan dependency graph with resolved package_ids")

    # Binary file
    binary_file = models.FileField(upload_to='binaries/', blank=True, null=True)
    file_size = models.BigIntegerField(default=0, help_text="File size in bytes")

    # Rust crate file (.crate archive)
    rust_crate_file = models.FileField(upload_to='rust_crates/', blank=True, null=True,
                                       help_text="Generated Rust -sys crate archive")

    # Checksums
    sha256 = models.CharField(max_length=64, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    download_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.package_version} ({self.os}/{self.arch}/{self.compiler})"

    def get_config_string(self):
        """Human-readable configuration string"""
        parts = []
        if self.os:
            parts.append(f"OS: {self.os}")
        if self.arch:
            parts.append(f"Arch: {self.arch}")
        if self.compiler:
            parts.append(f"Compiler: {self.compiler} {self.compiler_version}")
        if self.build_type:
            parts.append(f"Build: {self.build_type}")
        return ", ".join(parts)
