#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ConanCrates CLI tool

Usage:
    conancrates upload <package_ref>
    conancrates download <package_ref>

Example:
    conancrates upload boost/1.81.0
    conancrates download testlib/1.0.0

This tool:
- Upload: Finds package in Conan cache, creates tarball, uploads to ConanCrates
- Download: Uses ConanCrates bundle (with Conan dependency resolution) to download package + dependencies
"""

import sys
import os
import subprocess
import json
import requests
import tarfile
import tempfile
from pathlib import Path
import argparse

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def get_conan_executable():
    """Get the path to conan executable (prefer venv version)."""
    # Try venv first
    script_dir = Path(__file__).parent.parent  # Go up to ConanCrates root (conancrates.py is in conancrates/)
    venv_conan = script_dir / 'venv' / 'Scripts' / 'conan.exe'
    if venv_conan.exists():
        return str(venv_conan)

    # Fall back to system conan
    return 'conan'


def get_conan_version():
    """Get the version of Conan being used."""
    try:
        result = subprocess.run(
            [get_conan_executable(), '--version'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            # Output is typically "Conan version 2.x.x"
            version_line = result.stdout.strip()
            # Extract just the version number
            import re
            match = re.search(r'(\d+\.\d+\.\d+)', version_line)
            if match:
                return match.group(1)
            return version_line  # Return full line if we can't extract
        return "unknown"
    except Exception:
        return "unknown"


def run_conan_command(args):
    """Run a conan command and return the output."""
    try:
        # Replace 'conan' with actual executable path
        conan_exe = get_conan_executable()
        if args[0] == 'conan':
            args[0] = conan_exe

        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running conan: {e}")
        print(f"Stderr: {e.stderr}")
        return None


def get_package_cache_path(package_ref):
    """
    Get the cache path for a package recipe.

    Args:
        package_ref: Package reference like "boost/1.81.0"

    Returns:
        Path to the package in Conan cache
    """
    output = run_conan_command(['conan', 'cache', 'path', package_ref])
    if output:
        return output.strip()
    return None


def find_recipe_file(cache_path):
    """
    Find the conanfile.py in the cache path.

    Args:
        cache_path: Path to package in Conan cache

    Returns:
        Path to conanfile.py
    """
    cache_path = Path(cache_path)

    # Look for conanfile.py
    recipe_path = cache_path / 'conanfile.py'
    if recipe_path.exists():
        return recipe_path

    # Sometimes it's in export/
    recipe_path = cache_path / 'export' / 'conanfile.py'
    if recipe_path.exists():
        return recipe_path

    # Search recursively
    for p in cache_path.rglob('conanfile.py'):
        return p

    return None


def get_package_binaries(package_ref, profile):
    """
    Get the binary package ID for a package using a specific profile.

    Args:
        package_ref: Package reference like "boost/1.81.0"
        profile: Conan profile name or path (REQUIRED - no default)

    Returns:
        List containing the package ID that matches the profile settings

    Raises:
        ValueError: If profile is not provided
    """
    if not profile:
        raise ValueError("Profile parameter is required for get_package_binaries()")

    # Use graph info to get the specific package ID for this profile
    cache_path = get_package_cache_path(package_ref)
    if not cache_path:
        return []

    cmd = ['conan', 'graph', 'info', cache_path, '--format=json', '-pr', profile]
    output = run_conan_command(cmd)
    if not output:
        return []

    try:
        # Find the JSON part (skip the profile/graph header output)
        json_start = output.find('{')
        if json_start != -1:
            json_str = output[json_start:]
            data = json.loads(json_str)
            # Find the package node (not the root "0" node)
            nodes = data.get('graph', {}).get('nodes', {})
            for node_id, node in nodes.items():
                ref = node.get('ref', '')
                if package_ref in ref:
                    pkg_id = node.get('package_id')
                    if pkg_id:
                        return [pkg_id]
        return []
    except Exception as e:
        print(f"Warning: Could not parse graph info: {e}")
        return []


def get_binary_package_path(package_ref, package_id):
    """
    Get the cache path for a specific binary package.

    Args:
        package_ref: Package reference like "boost/1.81.0"
        package_id: Package ID hash

    Returns:
        Path object to the binary package directory, or None if not found
    """
    full_ref = f"{package_ref}:{package_id}"
    output = run_conan_command(['conan', 'cache', 'path', full_ref])
    if output:
        return Path(output.strip())
    return None


def get_dependency_graph(package_ref, package_id, cache_path, profile):
    """
    Get the full dependency graph for a package using conan graph info.

    Args:
        package_ref: Package reference like "boost/1.81.0"
        package_id: Package ID hash
        cache_path: Path to the recipe in cache
        profile: Conan profile name or path (REQUIRED - no default)

    Returns:
        Dict with graph data, or None if failed

    Raises:
        ValueError: If profile is not provided
    """
    if not profile:
        raise ValueError("Profile parameter is required for get_dependency_graph()")

    # Run graph info from the cache directory where conanfile.py is located
    cmd = ['conan', 'graph', 'info', cache_path, '--format=json', '-pr', profile]

    output = run_conan_command(cmd)
    if output:
        try:
            # Find the JSON part (skip the profile/graph header output)
            json_start = output.find('{')
            if json_start != -1:
                json_str = output[json_start:]
                return json.loads(json_str)
        except Exception as e:
            print(f"Warning: Could not parse graph info JSON: {e}")
    return None


def create_binary_tarball(package_ref, package_id, output_path):
    """
    Create a .tgz using conan cache save (proper Conan format).

    Args:
        package_ref: Package reference like "boost/1.81.0"
        package_id: Package ID hash
        output_path: Where to save the .tgz

    Returns:
        Path to created tarball
    """
    full_ref = f"{package_ref}:{package_id}"
    output_path = Path(output_path)

    # Use conan cache save to create proper .tgz format
    # This creates a file that can be imported with conan cache restore
    result = subprocess.run(
        [get_conan_executable(), 'cache', 'save', full_ref, '--file', str(output_path)],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Warning: conan cache save failed, falling back to manual tarball")
        print(f"  Error: {result.stderr}")
        # Fallback: manual tarball creation
        package_path = get_binary_package_path(package_ref, package_id)
        if package_path:
            with tarfile.open(output_path, 'w:gz') as tar:
                for item in Path(package_path).rglob('*'):
                    if item.is_file():
                        arcname = item.relative_to(package_path)
                        tar.add(item, arcname=arcname)

    return output_path


def check_package_exists(server_url, package_ref, package_id):
    """
    Check if a specific binary package already exists on ConanCrates server.

    Args:
        server_url: ConanCrates server URL
        package_ref: Package reference like "boost/1.81.0"
        package_id: Specific package ID hash

    Returns:
        True if this specific binary exists, False otherwise
    """
    try:
        package_name, version = package_ref.split('/', 1)
        # Try to access the specific binary download endpoint
        # This will return 200 if the binary exists, 404 if not
        check_url = f"{server_url}/packages/{package_name}/{version}/binaries/{package_id}/download/"
        response = requests.head(check_url)  # Use HEAD to avoid downloading
        return response.status_code == 200
    except Exception:
        return False


def is_release_version(version):
    """
    Check if a version string is a release version (not RC, beta, etc.).

    Args:
        version: Version string like "1.81.0" or "1.0.0-rc1"

    Returns:
        True if release version, False if pre-release
    """
    version_lower = version.lower()
    pre_release_markers = ['-rc', '-beta', '-alpha', '-dev', '-pre', '-snapshot']
    return not any(marker in version_lower for marker in pre_release_markers)


def extract_dependencies_from_graph(dependency_graph):
    """
    Extract list of dependency package refs and their package_ids from a dependency graph.

    Args:
        dependency_graph: Dependency graph dict from conan graph info

    Returns:
        List of tuples: [(package_ref, package_id), ...]
        e.g., [("zlib/1.2.13", "abc123"), ("boost/1.81.0", "def456")]
    """
    dependencies = []
    if not dependency_graph:
        return dependencies

    nodes = dependency_graph.get('graph', {}).get('nodes', {})
    for node_id, node in nodes.items():
        # Skip root node (the package itself)
        if node_id == "0":
            continue

        ref = node.get('ref', '')
        package_id = node.get('package_id', None)

        if '/' in ref and package_id:
            # Remove revision hash if present (e.g., "boost/1.81.0#hash" -> "boost/1.81.0")
            package_ref = ref.split('#')[0]
            dependencies.append((package_ref, package_id))

    return dependencies


def upload_package(server_url, recipe_path, binary_path, package_ref, package_id=None, dependency_graph=None):
    """
    Upload package to ConanCrates server.

    Args:
        server_url: ConanCrates server URL (e.g., http://localhost:8000)
        recipe_path: Path to conanfile.py
        binary_path: Path to .tar.gz binary
        package_ref: Package reference like "boost/1.81.0" (name/version)
        package_id: Real Conan package_id (optional, recommended)
        dependency_graph: Dependency graph dict from conan graph info (optional, recommended)

    Returns:
        True if successful, False otherwise
    """
    upload_url = f"{server_url}/api/package/upload"

    try:
        # Parse package reference
        package_name, version = package_ref.split('/', 1)

        # Get Conan version
        conan_version = get_conan_version()

        with open(recipe_path, 'rb') as recipe_file, open(binary_path, 'rb') as binary_file:
            files = {
                'recipe': ('conanfile.py', recipe_file, 'text/plain'),
                'binary': (binary_path.name, binary_file, 'application/gzip')
            }

            data = {
                'package_name': package_name,
                'version': version,
                'conan_version': conan_version
            }
            if package_id:
                data['package_id'] = package_id
            if dependency_graph:
                data['dependency_graph'] = json.dumps(dependency_graph)

            print(f"Uploading to {upload_url}...")
            print(f"  Recipe: {recipe_path}")
            print(f"  Binary: {binary_path}")
            print(f"  Conan version: {conan_version}")
            if package_id:
                print(f"  Package ID: {package_id}")
            if dependency_graph:
                dep_count = len(dependency_graph.get('graph', {}).get('nodes', {})) - 1  # -1 for root
                print(f"  Dependencies: {dep_count} package(s) in graph")

            response = requests.post(upload_url, files=files, data=data)

            if response.status_code == 200:
                result = response.json()
                print(f"\nSuccess!")
                print(f"  Package: {result['package']['name']}/{result['package']['version']}")
                print(f"  Package ID: {result['package']['package_id']}")
                print(f"  Size: {result['package']['size']} bytes")
                print(f"  SHA256: {result['package']['sha256']}")
                return True
            else:
                print(f"\nUpload failed!")
                print(f"  Status: {response.status_code}")
                print(f"  Response: {response.text}")
                return False

    except Exception as e:
        print(f"\nError uploading: {e}")
        import traceback
        traceback.print_exc()
        return False


def upload_single_package(server_url, package_ref, profile, package_id=None):
    """
    Upload a single package to ConanCrates.

    Args:
        server_url: ConanCrates server URL
        package_ref: Package reference like "boost/1.81.0"
        profile: Conan profile name or path (REQUIRED - no default)
        package_id: Specific package ID to upload (optional, will be determined from profile if not specified)

    Returns:
        0 on success, 1 on failure

    Raises:
        ValueError: If profile is not provided
    """
    if not profile:
        raise ValueError("Profile parameter is required for upload_single_package()")

    # Get package cache path (recipe)
    cache_path = get_package_cache_path(package_ref)
    if not cache_path:
        print(f"  Error: Package {package_ref} not found in Conan cache")
        return 1

    # Find recipe
    recipe_path = find_recipe_file(cache_path)
    if not recipe_path:
        print(f"  Error: Could not find conanfile.py in {cache_path}")
        return 1

    # Find binary packages for this profile
    package_ids = get_package_binaries(package_ref, profile)
    if not package_ids:
        print(f"  Error: No binary packages found for {package_ref} with profile {profile}")
        return 1

    # Use specified package_id or first one
    if not package_id:
        package_id = package_ids[0]

    # Get binary package path
    binary_cache_path = get_binary_package_path(package_ref, package_id)
    if not binary_cache_path:
        print(f"  Error: Could not find binary package path")
        return 1

    # Get dependency graph with profile
    dependency_graph = get_dependency_graph(package_ref, package_id, cache_path, profile)

    # Create tarball
    with tempfile.TemporaryDirectory() as tmpdir:
        tarball_path = Path(tmpdir) / f"{package_ref.replace('/', '-')}-{package_id}.tgz"
        create_binary_tarball(package_ref, package_id, tarball_path)

        # Upload
        if upload_package(server_url, recipe_path, tarball_path, package_ref, package_id=package_id, dependency_graph=dependency_graph):
            return 0
        else:
            return 1


def cmd_upload(args):
    """Handle the 'upload' command."""
    package_ref = args.package_ref
    server_url = args.server or "http://localhost:8000"
    profile = args.profile
    with_deps = args.with_dependencies if hasattr(args, 'with_dependencies') else False

    print(f"ConanCrates Upload")
    print(f"{'='*60}")
    print(f"Package: {package_ref}")
    print(f"Profile: {profile}")
    print(f"Server: {server_url}")
    print(f"Upload dependencies: {with_deps}")
    print(f"{'='*60}")

    # Step 1: Get package cache path (recipe)
    print("\n1. Finding package in Conan cache...")
    cache_path = get_package_cache_path(package_ref)
    if not cache_path:
        print(f"Error: Package {package_ref} not found in Conan cache")
        print(f"  Make sure you've built the package with 'conan create' first")
        return 1

    # Step 2: Find binary packages
    print("\n2. Finding binary packages...")
    package_ids = get_package_binaries(package_ref, profile=profile)
    if not package_ids:
        print(f"Error: No binary packages found for {package_ref} with profile {profile}")
        return 1

    package_id = package_ids[0]
    print(f"  Found {len(package_ids)} binary package(s), using: {package_id}")

    # Step 3: Get dependency graph
    print("\n3. Analyzing dependencies...")
    dependency_graph = get_dependency_graph(package_ref, package_id, cache_path, profile=profile)

    # packages_to_upload is now a list of (package_ref, package_id) tuples
    packages_to_upload = [(package_ref, package_id)]

    if with_deps and dependency_graph:
        # Extract dependencies from graph (returns list of tuples)
        dependencies = extract_dependencies_from_graph(dependency_graph)
        if dependencies:
            print(f"  Found {len(dependencies)} dependencies")
            packages_to_upload.extend(dependencies)
        else:
            print(f"  No dependencies found")
    else:
        print(f"  Uploading only main package (use --with-dependencies to include deps)")

    # Step 4: Check version strings (no RC versions allowed)
    print("\n4. Validating versions...")
    non_release_packages = []
    for pkg_ref, pkg_id in packages_to_upload:
        _, version = pkg_ref.split('/', 1)
        if not is_release_version(version):
            non_release_packages.append(pkg_ref)

    if non_release_packages:
        print(f"\n❌ Error: Pre-release versions detected!")
        print(f"  ConanCrates only accepts release versions (no -rc, -beta, -alpha, etc.)")
        print(f"\n  Pre-release packages:")
        for pkg in non_release_packages:
            print(f"    - {pkg}")
        print(f"\n  Please use release versions only.")
        return 1

    print(f"  ✓ All versions are release versions")

    # Step 5: Check which packages already exist on server
    print("\n5. Checking server for existing packages...")
    existing_packages = []
    missing_packages = []

    for pkg_ref, pkg_id in packages_to_upload:
        print(f"  Checking {pkg_ref} ({pkg_id[:8]}...)...", end=' ')
        if check_package_exists(server_url, pkg_ref, pkg_id):
            print("EXISTS")
            existing_packages.append((pkg_ref, pkg_id))
        else:
            print("NOT FOUND")
            missing_packages.append((pkg_ref, pkg_id))

    # Step 6: Show upload plan and ask for confirmation
    print(f"\n{'='*60}")
    print(f"Upload Plan:")
    print(f"{'='*60}")

    if existing_packages:
        print(f"\n✓ Already on server ({len(existing_packages)} binaries):")
        for pkg_ref, pkg_id in existing_packages:
            print(f"  - {pkg_ref} ({pkg_id[:8]}...)")

    if missing_packages:
        print(f"\n↑ Will upload ({len(missing_packages)} binaries):")
        for pkg_ref, pkg_id in missing_packages:
            print(f"  - {pkg_ref} ({pkg_id[:8]}...)")
    else:
        print(f"\n✓ All binaries already exist on server. Nothing to upload!")
        return 0

    print(f"\n{'='*60}")

    # Ask for confirmation
    try:
        response = input("\nProceed with upload? [y/N]: ").strip().lower()
        if response not in ['y', 'yes']:
            print("Upload cancelled.")
            return 1
    except (KeyboardInterrupt, EOFError):
        print("\nUpload cancelled.")
        return 1

    # Step 7: Upload packages
    print(f"\n{'='*60}")
    print(f"Uploading packages...")
    print(f"{'='*60}")

    uploaded_count = 0
    failed_packages = []
    total_to_upload = len(missing_packages)

    for idx, (pkg_ref, pkg_id) in enumerate(missing_packages, 1):
        print(f"\n📦 [{idx}/{total_to_upload}] Uploading {pkg_ref} ({pkg_id[:8]}...)...")
        result = upload_single_package(server_url, pkg_ref, profile, package_id=pkg_id)
        if result == 0:
            uploaded_count += 1
            print(f"  ✓ Success! ({uploaded_count}/{total_to_upload} completed)")
        else:
            failed_packages.append((pkg_ref, pkg_id))
            print(f"  ✗ Failed!")

    # Step 8: Summary
    print(f"\n{'='*60}")
    print(f"Upload Summary:")
    print(f"{'='*60}")
    print(f"  Total binaries: {len(packages_to_upload)}")
    print(f"  Already existed: {len(existing_packages)}")
    print(f"  Uploaded: {uploaded_count}")
    print(f"  Failed: {len(failed_packages)}")

    if failed_packages:
        print(f"\n✗ Failed packages:")
        for pkg_ref, pkg_id in failed_packages:
            print(f"  - {pkg_ref} ({pkg_id[:8]}...)")
        return 1
    else:
        print(f"\n✓ All packages uploaded successfully!")

        # Generate Rust crate (unless --no-rust specified)
        no_rust = getattr(args, 'no_rust', False)
        if not no_rust:
            print(f"\n{'='*60}")
            print(f"Generating Rust Crate...")
            print(f"{'='*60}\n")

            # Create a mock args object for rust crate generation
            class RustArgs:
                pass

            rust_args = RustArgs()
            rust_args.package_ref = package_ref
            rust_args.profile = profile
            rust_args.output = './rust_crates'

            rust_result = cmd_generate_rust_crate(rust_args)
            if isinstance(rust_result, tuple):
                exit_code, crate_path = rust_result
                if exit_code == 0:
                    # TODO: Upload the .crate file to the server
                    # This would require an API endpoint to accept rust crate uploads
                    print(f"\n✓ Rust crate available at: {crate_path}")
                else:
                    print(f"\n⚠ Warning: Rust crate generation failed, but upload was successful")
            elif rust_result != 0:
                print(f"\n⚠ Warning: Rust crate generation failed, but upload was successful")
        else:
            print(f"\nℹ Skipped Rust crate generation (--no-rust specified)")

        return 0


def check_package_in_cache(package_ref, package_id):
    """
    Check if a specific package binary exists in local Conan cache.

    Args:
        package_ref: Package reference like "boost/1.81.0"
        package_id: Specific package ID hash

    Returns:
        True if binary exists in cache, False otherwise
    """
    try:
        binary_path = get_binary_package_path(package_ref, package_id)
        return binary_path is not None and binary_path.exists()
    except Exception:
        return False


def parse_conan_profile(profile_name):
    """
    Parse a Conan profile to extract settings.

    Args:
        profile_name: Name of the profile (e.g., "default") or path to profile file

    Returns:
        Dict with settings: {'os': ..., 'arch': ..., 'compiler': ..., 'compiler_version': ..., 'build_type': ...}
        Returns None if profile cannot be parsed
    """
    import configparser
    import os

    # First, try to resolve the profile using Conan
    # This will handle both profile names (like "default") and absolute paths
    try:
        result = subprocess.run(
            [get_conan_executable(), 'profile', 'show', '-pr', profile_name],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"Warning: Could not resolve profile '{profile_name}'")
            print(f"  {result.stderr.strip()}")
            return None

        # Parse the output from 'conan profile show'
        # Output shows "Host profile:" and "Build profile:" sections
        # We want the Host profile settings for downloading binaries
        # Format is like:
        # Host profile:
        # [settings]
        # os=Linux
        # arch=x86_64
        # compiler=gcc
        # compiler.version=11
        # build_type=Release

        settings = {}
        in_host_profile = False
        in_settings_section = False
        found_first_settings = False

        for line in result.stdout.split('\n'):
            line = line.strip()

            # Track when we enter Host profile section
            if line.startswith('Host profile:'):
                in_host_profile = True
                continue
            # Stop when we hit Build profile section
            elif line.startswith('Build profile:'):
                in_host_profile = False
                break

            # Only parse settings in Host profile section
            if in_host_profile:
                if line == '[settings]':
                    in_settings_section = True
                    found_first_settings = True
                    continue
                elif line.startswith('['):
                    in_settings_section = False
                    continue

                if in_settings_section and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    if key == 'os':
                        settings['os'] = value
                    elif key == 'arch':
                        settings['arch'] = value
                    elif key == 'compiler':
                        settings['compiler'] = value
                    elif key == 'compiler.version':
                        settings['compiler_version'] = value
                    elif key == 'build_type':
                        settings['build_type'] = value

        # Validate we got the required settings
        required = ['os', 'arch', 'compiler', 'compiler_version', 'build_type']
        missing = [k for k in required if k not in settings]

        if missing:
            print(f"Warning: Profile '{profile_name}' is missing settings: {', '.join(missing)}")
            return None

        return settings

    except Exception as e:
        print(f"Error parsing profile '{profile_name}': {e}")
        return None


def cmd_download(args):
    """
    Download package and dependencies from ConanCrates and restore to local Conan cache.
    Acts like 'conan install' - checks cache and only downloads missing packages.
    """
    import zipfile
    import tarfile
    import platform

    package_ref = args.package_ref
    server_url = args.server or "http://localhost:8000"

    print(f"ConanCrates Download")
    print(f"{'='*60}")
    print(f"Package: {package_ref}")
    print(f"Server: {server_url}")
    print(f"{'='*60}")

    # Parse package reference
    if '/' not in package_ref:
        print(f"Error: Invalid package reference. Expected format: package/version")
        return 1

    package_name, version = package_ref.split('/', 1)

    # Get platform settings from profile or auto-detect
    profile_name = getattr(args, 'profile', None)

    if profile_name:
        # Use settings from Conan profile
        print(f"\nUsing Conan profile: {profile_name}")
        settings = parse_conan_profile(profile_name)
        if not settings:
            print(f"Error: Could not parse profile '{profile_name}'")
            return 1

        os_name = settings['os']
        arch = settings['arch']
        compiler = settings['compiler']
        compiler_version = settings['compiler_version']
        build_type = settings['build_type']
    else:
        # Auto-detect platform settings (use defaults that match most common builds)
        print(f"\nNo profile specified, auto-detecting platform...")
        system = platform.system()
        if system == "Windows":
            os_name = "Windows"
            # Default to gcc for now (MinGW/MSYS2 is common for Conan on Windows)
            compiler = "gcc"
            compiler_version = "11"
        elif system == "Linux":
            os_name = "Linux"
            compiler = "gcc"
            compiler_version = "11"
        elif system == "Darwin":
            os_name = "Macos"
            compiler = "apple-clang"
            compiler_version = "14"
        else:
            os_name = "Linux"
            compiler = "gcc"
            compiler_version = "11"

        arch = platform.machine().lower()
        if arch in ("amd64", "x86_64"):
            arch = "x86_64"
        elif arch in ("arm64", "aarch64"):
            arch = "armv8"

        build_type = "Release"

    print(f"Target platform: {os_name}/{arch}/{compiler} {compiler_version}/{build_type}")

    # Step 1: Download bundle info to see what we need
    print(f"\n1. Fetching package information...")
    bundle_url = f"{server_url}/packages/{package_name}/{version}/bundle/?os={os_name}&arch={arch}&compiler={compiler}&compiler_version={compiler_version}&build_type={build_type}"

    try:
        response = requests.get(bundle_url, stream=True)
        if response.status_code != 200:
            print(f"\nError: No binaries found matching your profile settings")
            print(f"  Requested: {os_name}/{arch}/{compiler} {compiler_version}/{build_type}")
            print(f"  Status: {response.status_code}")

            # Try to get list of available binaries
            print(f"\nFetching available binaries for {package_name}/{version}...")
            try:
                binaries_url = f"{server_url}/packages/{package_name}/{version}/binaries/"
                binaries_response = requests.get(binaries_url)

                if binaries_response.status_code == 200:
                    binaries_data = binaries_response.json()
                    binaries = binaries_data.get('binaries', [])

                    if binaries:
                        print(f"\nAvailable binaries ({len(binaries)}):")
                        print(f"{'='*80}")
                        print(f"{'OS':<12} {'Arch':<12} {'Compiler':<15} {'Version':<10} {'Build Type':<12}")
                        print(f"{'-'*80}")
                        for binary in binaries:
                            # Mark fields that differ from requested profile with *
                            os_str = binary['os'] + ('*' if binary['os'] != os_name else '')
                            arch_str = binary['arch'] + ('*' if binary['arch'] != arch else '')
                            compiler_str = binary['compiler'] + ('*' if binary['compiler'] != compiler else '')
                            compiler_ver_str = binary['compiler_version'] + ('*' if binary['compiler_version'] != compiler_version else '')
                            build_type_str = binary['build_type'] + ('*' if binary['build_type'] != build_type else '')

                            print(f"{os_str:<12} {arch_str:<12} {compiler_str:<15} "
                                  f"{compiler_ver_str:<10} {build_type_str:<12}")
                        print(f"{'='*80}")
                        print(f"* = differs from requested profile")
                        print(f"\nTo download one of these, create a Conan profile with matching settings,")
                        print(f"or update your existing profile to match one of the available configurations.")
                    else:
                        print(f"  No binaries available for this package version")
                else:
                    print(f"  Could not retrieve list of available binaries (status {binaries_response.status_code})")
            except Exception as e:
                print(f"  Error querying available binaries: {e}")

            return 1

        # Save bundle ZIP to temp location
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            bundle_zip = tmpdir_path / 'bundle.zip'

            with open(bundle_zip, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Extract bundle to analyze what's included
            print(f"\n2. Analyzing bundle contents...")
            extract_dir = tmpdir_path / 'extracted'
            extract_dir.mkdir()

            with zipfile.ZipFile(bundle_zip, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            # Read bundle_info.json to get package list with package_ids
            bundle_info_path = extract_dir / 'bundle_info.json'
            if not bundle_info_path.exists():
                print(f"Error: Bundle info not found in download")
                return 1

            with open(bundle_info_path, 'r') as f:
                bundle_info = json.load(f)

            # Get packages from 'contents' (new format) or 'packages' (old format)
            packages = bundle_info.get('contents', bundle_info.get('packages', []))
            if not packages:
                print(f"Error: No packages found in bundle")
                print(f"Bundle info: {json.dumps(bundle_info, indent=2)}")
                return 1

            print(f"  Found {len(packages)} package(s) in bundle")

            # Step 3: Check which packages are already in cache
            print(f"\n3. Checking local Conan cache...")
            packages_to_install = []
            packages_in_cache = []

            for pkg_info in packages:
                # Support both old and new format
                if 'ref' in pkg_info:
                    # Old format: {'ref': 'package/version', 'package_id': '...'}
                    pkg_ref = pkg_info['ref']
                else:
                    # New format: {'package': 'name', 'version': 'x.y.z', 'package_id': '...'}
                    pkg_ref = f"{pkg_info['package']}/{pkg_info['version']}"

                pkg_id = pkg_info['package_id']

                print(f"  Checking {pkg_ref} ({pkg_id[:8]}...)...", end=' ')
                if check_package_in_cache(pkg_ref, pkg_id):
                    print("IN CACHE")
                    packages_in_cache.append((pkg_ref, pkg_id))
                else:
                    print("MISSING")
                    packages_to_install.append((pkg_ref, pkg_id, pkg_info))

            # Step 4: Show install plan
            print(f"\n{'='*60}")
            print(f"Install Plan:")
            print(f"{'='*60}")

            if packages_in_cache:
                print(f"\n✓ Already in cache ({len(packages_in_cache)} binaries):")
                for pkg_ref, pkg_id in packages_in_cache:
                    print(f"  - {pkg_ref} ({pkg_id[:8]}...)")

            if packages_to_install:
                print(f"\n↓ Will install to cache ({len(packages_to_install)} binaries):")
                for pkg_ref, pkg_id, _ in packages_to_install:
                    print(f"  - {pkg_ref} ({pkg_id[:8]}...)")
            else:
                print(f"\n✓ All packages already in cache. Nothing to install!")
                return 0

            print(f"\n{'='*60}")

            # Step 5: Install packages to Conan cache using `conan cache restore`
            print(f"\n5. Installing packages to Conan cache...")

            conan_exe = get_conan_executable()
            installed_count = 0
            failed_packages = []

            for pkg_ref, pkg_id, pkg_info in packages_to_install:
                pkg_name = pkg_ref.split('/')[0]
                pkg_version = pkg_ref.split('/')[1]
                print(f"\n📦 Installing {pkg_ref} ({pkg_id[:8]}...)...")

                try:
                    # Find package directory in extracted bundle
                    # New format: {package}-{version}/
                    # Old format: uses 'directory' field
                    pkg_dir_name = pkg_info.get('directory', f"{pkg_name}-{pkg_version}")
                    pkg_dir = extract_dir / pkg_dir_name

                    if not pkg_dir.exists():
                        print(f"  ✗ Error: Package directory not found: {pkg_dir}")
                        failed_packages.append(pkg_ref)
                        continue

                    # Find binary .tar.gz
                    # New format: {package}-{version}-{package_id}.tar.gz
                    # Old format: any .tgz file
                    binary_tarball = None
                    expected_filename = f"{pkg_name}-{pkg_version}-{pkg_id}.tar.gz"

                    # First try the expected filename
                    expected_path = pkg_dir / expected_filename
                    if expected_path.exists():
                        binary_tarball = expected_path
                    else:
                        # Fall back to searching for any .tar.gz file
                        for file in pkg_dir.iterdir():
                            if file.suffix == '.tgz' or file.name.endswith('.tar.gz'):
                                binary_tarball = file
                                break

                    if not binary_tarball:
                        print(f"  ✗ Error: Binary tarball not found in {pkg_dir}")
                        failed_packages.append(pkg_ref)
                        continue

                    # Use `conan cache restore` to install the .tgz to cache
                    print(f"  Restoring to Conan cache using 'conan cache restore'...")
                    import subprocess
                    result = subprocess.run(
                        [conan_exe, 'cache', 'restore', str(binary_tarball)],
                        capture_output=True,
                        text=True
                    )

                    if result.returncode == 0:
                        print(f"  ✓ Successfully restored to cache")
                        installed_count += 1
                    else:
                        print(f"  ✗ Error: conan cache restore failed")
                        if result.stderr:
                            print(f"    {result.stderr.strip()}")
                        failed_packages.append(pkg_ref)

                except Exception as e:
                    print(f"  ✗ Error: {e}")
                    failed_packages.append(pkg_ref)

            # Summary
            print(f"\n{'='*60}")
            print(f"Download Summary:")
            print(f"{'='*60}")
            print(f"  Total packages: {len(packages)}")
            print(f"  Already in cache: {len(packages_in_cache)}")
            print(f"  Downloaded: {installed_count}")
            print(f"  Failed: {len(failed_packages)}")

            if failed_packages:
                print(f"\n✗ Failed packages:")
                for pkg_ref in failed_packages:
                    print(f"  - {pkg_ref}")
                return 1
            else:
                print(f"\n✓ All packages restored successfully!")
                return 0

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_generate_rust_crate(args):
    """Generate a Rust crate from a Conan package in the cache."""
    package_ref = args.package_ref
    profile = args.profile
    output_dir = args.output or './rust_crates'

    print(f"ConanCrates Rust Crate Generator")
    print(f"{'='*60}")
    print(f"Package: {package_ref}")
    print(f"Profile: {profile}")
    print(f"Output: {output_dir}")
    print(f"{'='*60}\n")

    # Get package cache path
    cache_path = get_package_cache_path(package_ref)
    if not cache_path:
        print(f"✗ Error: Package {package_ref} not found in Conan cache")
        print(f"  Run: conan create <path> or download it first")
        return 1

    # Get binary package path
    package_ids = get_package_binaries(package_ref, profile)
    if not package_ids:
        print(f"✗ Error: No binary package found for profile {profile}")
        return 1

    package_id = package_ids[0]
    binary_path = get_binary_package_path(package_ref, package_id)
    if not binary_path:
        print(f"✗ Error: Binary package path not found for package_id {package_id}")
        return 1

    print(f"Found binary package: {binary_path}\n")

    # Parse package name and version
    if '/' not in package_ref:
        print(f"✗ Error: Invalid package reference format. Expected: name/version")
        return 1

    pkg_name, pkg_version = package_ref.split('/', 1)
    crate_name = f"{pkg_name.replace('_', '-')}-sys"

    # Create output directory
    crate_dir = Path(output_dir) / crate_name
    crate_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating Rust crate: {crate_name}")
    print(f"{'='*60}\n")

    # Scan binary package for libraries and headers
    binary_path = Path(binary_path)
    lib_dir = binary_path / 'lib'
    include_dir = binary_path / 'include'

    # Find libraries
    libraries = []
    if lib_dir.exists():
        for lib_file in lib_dir.iterdir():
            if lib_file.suffix in ['.a', '.lib', '.so', '.dylib']:
                # Extract library name (remove lib prefix and extension)
                lib_name = lib_file.stem
                if lib_name.startswith('lib'):
                    lib_name = lib_name[3:]
                libraries.append((lib_name, lib_file))

    if not libraries:
        print(f"⚠ Warning: No libraries found in {lib_dir}")
    else:
        print(f"Found {len(libraries)} librar{'y' if len(libraries) == 1 else 'ies'}:")
        for lib_name, lib_file in libraries:
            print(f"  - {lib_name} ({lib_file.name})")
    print()

    # Find headers
    headers = []
    if include_dir.exists():
        for header_file in include_dir.rglob('*.h'):
            headers.append(header_file)
        for header_file in include_dir.rglob('*.hpp'):
            headers.append(header_file)

    if not headers:
        print(f"⚠ Warning: No headers found in {include_dir}")
    else:
        print(f"Found {len(headers)} header file{'s' if len(headers) != 1 else ''}:")
        for header in headers[:5]:  # Show first 5
            print(f"  - {header.relative_to(include_dir)}")
        if len(headers) > 5:
            print(f"  ... and {len(headers) - 5} more")
    print()

    # Copy libraries
    native_dir = crate_dir / 'native' / 'current'
    native_dir.mkdir(parents=True, exist_ok=True)

    for lib_name, lib_file in libraries:
        import shutil
        shutil.copy2(lib_file, native_dir / lib_file.name)

    # Copy headers
    if headers:
        crate_include_dir = crate_dir / 'include'
        crate_include_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copytree(include_dir, crate_include_dir, dirs_exist_ok=True)

    # Generate Cargo.toml
    cargo_toml_content = f'''[package]
name = "{crate_name}"
version = "{pkg_version}"
edition = "2021"
links = "{pkg_name}"

# Include the binaries and headers in the published crate
include = [
    "src/**/*",
    "native/**/*",
    "include/**/*",
    "build.rs",
    "Cargo.toml",
]

[lib]
name = "{crate_name.replace('-', '_')}"
path = "src/lib.rs"

# Optional: Add description, license, etc. from conanfile.py if available
# description = "Rust bindings for {pkg_name}"
# license = "MIT"
# repository = "https://github.com/..."
'''

    with open(crate_dir / 'Cargo.toml', 'w') as f:
        f.write(cargo_toml_content)

    # Generate build.rs
    lib_links = '\n    '.join([f'println!("cargo:rustc-link-lib=static={lib_name}");' for lib_name, _ in libraries])

    build_rs_content = f'''fn main() {{
    // Tell cargo where to find the pre-compiled libraries
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").unwrap();
    let lib_path = std::path::Path::new(&manifest_dir).join("native/current");

    println!("cargo:rustc-link-search=native={{}}", lib_path.display());

    // Link the libraries
    {lib_links}

    // Re-run if libraries change
    println!("cargo:rerun-if-changed=native/");
}}
'''

    with open(crate_dir / 'build.rs', 'w') as f:
        f.write(build_rs_content)

    # Generate src/lib.rs
    src_dir = crate_dir / 'src'
    src_dir.mkdir(parents=True, exist_ok=True)

    lib_rs_content = f'''//! Rust FFI bindings for {pkg_name}
//!
//! This crate provides pre-compiled binaries for {pkg_name}.
//! The binaries are linked statically.

#![allow(non_upper_case_globals)]
#![allow(non_camel_case_types)]
#![allow(non_snake_case)]

// TODO: Add your FFI declarations here
// You can use bindgen to auto-generate bindings from the C headers in include/
//
// Example:
// extern "C" {{
//     pub fn my_function() -> i32;
// }}

#[cfg(test)]
mod tests {{
    use super::*;

    #[test]
    fn test_link() {{
        // Add a test that uses your FFI functions
    }}
}}
'''

    with open(src_dir / 'lib.rs', 'w') as f:
        f.write(lib_rs_content)

    # Generate README
    readme_content = f'''# {crate_name}

Rust FFI bindings for {pkg_name} {pkg_version}.

This crate contains pre-compiled binaries from the Conan package.

## Libraries included:

{chr(10).join([f"- {lib_name}" for lib_name, _ in libraries])}

## Usage

Add this to your `Cargo.toml`:

```toml
[dependencies]
{crate_name} = "{pkg_version}"
```

Then use it in your code:

```rust
extern crate {crate_name.replace('-', '_')};

// Your code here
```

## Building

This crate includes pre-compiled static libraries and does not require compilation
of the C/C++ source code. The libraries are linked during the Rust build process.

## Source

Generated from Conan package: {package_ref}
'''

    with open(crate_dir / 'README.md', 'w') as f:
        f.write(readme_content)

    print(f"✓ Rust crate generated successfully!")
    print(f"\nCrate structure:")
    print(f"  {crate_dir}/")
    print(f"  ├── Cargo.toml")
    print(f"  ├── build.rs")
    print(f"  ├── README.md")
    print(f"  ├── src/")
    print(f"  │   └── lib.rs")
    print(f"  ├── native/")
    print(f"  │   └── current/       ({len(libraries)} librar{'y' if len(libraries) == 1 else 'ies'})")
    if headers:
        print(f"  └── include/           ({len(headers)} header file{'s' if len(headers) != 1 else ''})")

    # Package as a .crate file (tar.gz)
    print(f"\nPackaging as .crate archive...")
    import tarfile
    crate_archive_name = f"{crate_name}-{pkg_version}.crate"
    crate_archive_path = Path(output_dir) / crate_archive_name

    with tarfile.open(crate_archive_path, "w:gz") as tar:
        tar.add(crate_dir, arcname=crate_name)

    print(f"✓ Created: {crate_archive_path}")

    print(f"\nNext steps:")
    print(f"  1. cd {crate_dir}")
    print(f"  2. Edit src/lib.rs to add FFI declarations")
    print(f"  3. Run: cargo build")
    print(f"  4. Run: cargo test")
    print(f"  5. Optional: cargo publish (if you want to publish to crates.io)")

    # Return path to the .crate archive for upload
    return (0, str(crate_archive_path))


def main():
    parser = argparse.ArgumentParser(
        description='ConanCrates CLI - Upload and download Conan packages to/from ConanCrates registry'
    )
    parser.add_argument(
        '--server',
        default='http://localhost:8000',
        help='ConanCrates server URL (default: http://localhost:8000)'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Upload command
    upload_parser = subparsers.add_parser('upload', help='Upload a package')
    upload_parser.add_argument(
        'package_ref',
        help='Package reference (e.g., boost/1.81.0)'
    )
    upload_parser.add_argument(
        '-pr', '--profile',
        required=True,
        help='Conan profile to use (required, e.g., default, or path to profile file)'
    )
    upload_parser.add_argument(
        '--with-dependencies',
        action='store_true',
        help='Also upload all dependencies (will check server and ask for confirmation)'
    )
    upload_parser.add_argument(
        '--no-rust',
        action='store_true',
        help='Skip Rust crate generation (by default, a Rust crate is generated)'
    )

    # Download command
    download_parser = subparsers.add_parser('download', help='Download a package and its dependencies')
    download_parser.add_argument(
        'package_ref',
        help='Package reference (e.g., boost/1.81.0)'
    )
    download_parser.add_argument(
        '-pr', '--profile',
        help='Conan profile to use (e.g., default, or path to profile file)'
    )
    download_parser.add_argument(
        '-o', '--output',
        help='Output directory (default: ./conan_packages)'
    )
    download_parser.add_argument(
        '--keep-zip',
        action='store_true',
        help='Keep the downloaded ZIP file after extraction'
    )

    # Generate Rust crate command
    rust_parser = subparsers.add_parser('generate-rust-crate', help='Generate a Rust crate from a Conan package')
    rust_parser.add_argument(
        'package_ref',
        help='Package reference (e.g., mylib/1.0.0)'
    )
    rust_parser.add_argument(
        '-pr', '--profile',
        required=True,
        help='Conan profile to use (required)'
    )
    rust_parser.add_argument(
        '-o', '--output',
        help='Output directory (default: ./rust_crates)'
    )

    args = parser.parse_args()

    if args.command == 'upload':
        return cmd_upload(args)
    elif args.command == 'download':
        return cmd_download(args)
    elif args.command == 'generate-rust-crate':
        return cmd_generate_rust_crate(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
