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
    script_dir = Path(__file__).parent.parent.parent  # Go up to ConanCrates root
    venv_conan = script_dir / 'venv' / 'Scripts' / 'conan.exe'
    if venv_conan.exists():
        return str(venv_conan)

    # Fall back to system conan
    return 'conan'


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


def get_package_binaries(package_ref):
    """
    Get list of binary package IDs for a package.

    Args:
        package_ref: Package reference like "boost/1.81.0"

    Returns:
        List of package IDs
    """
    output = run_conan_command(['conan', 'list', f'{package_ref}:*', '--format=json'])
    if not output:
        return []

    try:
        data = json.loads(output)
        # Navigate JSON structure to find package IDs
        # Structure: {"Local Cache": {"package/version": {"revisions": {"hash": {"packages": {"package_id": {...}}}}}}}
        for cache_name, cache_data in data.items():
            for pkg_name, pkg_data in cache_data.items():
                if 'revisions' in pkg_data:
                    for rev_hash, rev_data in pkg_data['revisions'].items():
                        if 'packages' in rev_data:
                            return list(rev_data['packages'].keys())
        return []
    except Exception as e:
        print(f"Warning: Could not parse package list: {e}")
        return []


def get_binary_package_path(package_ref, package_id):
    """
    Get the cache path for a specific binary package.

    Args:
        package_ref: Package reference like "boost/1.81.0"
        package_id: Package ID hash

    Returns:
        Path to the binary package directory
    """
    full_ref = f"{package_ref}:{package_id}"
    output = run_conan_command(['conan', 'cache', 'path', full_ref])
    if output:
        return output.strip()
    return None


def get_dependency_graph(package_ref, package_id, cache_path):
    """
    Get the full dependency graph for a package using conan graph info.

    Args:
        package_ref: Package reference like "boost/1.81.0"
        package_id: Package ID hash
        cache_path: Path to the recipe in cache

    Returns:
        Dict with graph data, or None if failed
    """
    # Run graph info from the cache directory where conanfile.py is located
    output = run_conan_command(['conan', 'graph', 'info', cache_path, '--format=json'])
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


def upload_package(server_url, recipe_path, binary_path, package_id=None, dependency_graph=None):
    """
    Upload package to ConanCrates server.

    Args:
        server_url: ConanCrates server URL (e.g., http://localhost:8000)
        recipe_path: Path to conanfile.py
        binary_path: Path to .tar.gz binary
        package_id: Real Conan package_id (optional, recommended)
        dependency_graph: Dependency graph dict from conan graph info (optional, recommended)

    Returns:
        True if successful, False otherwise
    """
    upload_url = f"{server_url}/api/package/upload"

    try:
        with open(recipe_path, 'rb') as recipe_file, open(binary_path, 'rb') as binary_file:
            files = {
                'recipe': ('conanfile.py', recipe_file, 'text/plain'),
                'binary': (binary_path.name, binary_file, 'application/gzip')
            }

            data = {}
            if package_id:
                data['package_id'] = package_id
            if dependency_graph:
                data['dependency_graph'] = json.dumps(dependency_graph)

            print(f"Uploading to {upload_url}...")
            print(f"  Recipe: {recipe_path}")
            print(f"  Binary: {binary_path}")
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


def cmd_upload(args):
    """Handle the 'upload' command."""
    package_ref = args.package_ref
    server_url = args.server or "http://localhost:8000"

    print(f"Uploading {package_ref} to ConanCrates...")

    # Step 1: Get package cache path (recipe)
    print("\n1. Finding package recipe in Conan cache...")
    cache_path = get_package_cache_path(package_ref)
    if not cache_path:
        print(f"Error: Package {package_ref} not found in Conan cache")
        print(f"  Make sure you've built the package with 'conan create' first")
        return 1

    print(f"  Found: {cache_path}")

    # Step 2: Find recipe
    print("\n2. Finding conanfile.py...")
    recipe_path = find_recipe_file(cache_path)
    if not recipe_path:
        print(f"Error: Could not find conanfile.py in {cache_path}")
        return 1

    print(f"  Found: {recipe_path}")

    # Step 3: Find binary packages
    print("\n3. Finding binary packages...")
    package_ids = get_package_binaries(package_ref)
    if not package_ids:
        print(f"Error: No binary packages found for {package_ref}")
        print(f"  Make sure you've built the package with 'conan create' first")
        return 1

    print(f"  Found {len(package_ids)} binary package(s)")

    # For now, just upload the first binary
    # TODO: Allow user to select which binary to upload
    package_id = package_ids[0]
    print(f"  Using package ID: {package_id}")

    # Step 4: Get binary package path
    print("\n4. Getting binary package path...")
    binary_cache_path = get_binary_package_path(package_ref, package_id)
    if not binary_cache_path:
        print(f"Error: Could not find binary package path")
        return 1

    print(f"  Found: {binary_cache_path}")

    # Step 5: Get dependency graph
    print("\n5. Getting dependency graph...")
    dependency_graph = get_dependency_graph(package_ref, package_id, cache_path)
    if dependency_graph:
        dep_count = len(dependency_graph.get('graph', {}).get('nodes', {})) - 1
        print(f"  Found dependency graph with {dep_count} package(s)")
    else:
        print(f"  Warning: Could not get dependency graph")

    # Step 6: Create tarball
    print("\n6. Creating binary tarball...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tarball_path = Path(tmpdir) / f"{package_ref.replace('/', '-')}-{package_id}.tgz"
        create_binary_tarball(package_ref, package_id, tarball_path)
        print(f"  Created: {tarball_path}")

        # Step 7: Upload
        print("\n7. Uploading to ConanCrates...")
        if upload_package(server_url, recipe_path, tarball_path, package_id=package_id, dependency_graph=dependency_graph):
            return 0
        else:
            return 1


def cmd_download(args):
    """Handle the 'download' command using bundle endpoint."""
    import zipfile

    package_ref = args.package_ref
    server_url = args.server or "http://localhost:8000"
    output_dir = Path(args.output) if args.output else Path.cwd() / 'conan_packages'

    print(f"ConanCrates Download")
    print(f"{'='*60}")
    print(f"Package: {package_ref}")
    print(f"Server: {server_url}")
    print(f"Output: {output_dir}")
    print(f"{'='*60}")

    # Parse package reference
    if '/' not in package_ref:
        print(f"Error: Invalid package reference. Expected format: package/version")
        return 1

    package_name, version = package_ref.split('/', 1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Download bundle ZIP (includes package + all dependencies resolved by Conan)
    print(f"\n1. Downloading bundle (with dependencies resolved by Conan)...")
    bundle_url = f"{server_url}/packages/{package_name}/{version}/bundle/"

    try:
        response = requests.get(bundle_url, stream=True)
        if response.status_code != 200:
            print(f"Error: Could not download bundle (status {response.status_code})")
            if response.status_code == 503:
                print(f"  Server error - Conan dependency resolution failed")
                print(f"  Make sure Conan is installed on the server")
            return 1

        # Save ZIP file
        zip_path = output_dir / f"{package_name}-{version}-bundle.zip"
        print(f"  Downloading to {zip_path}...")

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"\r  Progress: {percent:.1f}% ({downloaded}/{total_size} bytes)", end='')

        print(f"\n  Downloaded: {zip_path} ({downloaded} bytes)")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Step 2: Extract ZIP
    print(f"\n2. Extracting bundle...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(output_dir)
            file_list = zip_ref.namelist()
            print(f"  Extracted {len(file_list)} file(s)")

            # Show what was extracted
            packages = set()
            for file_name in file_list:
                # Files are in format: package-version/...
                if '/' in file_name:
                    pkg = file_name.split('/')[0]
                    packages.add(pkg)

            if packages:
                print(f"\n  Packages extracted:")
                for pkg in sorted(packages):
                    print(f"    - {pkg}")

    except Exception as e:
        print(f"Error extracting bundle: {e}")
        return 1

    # Step 3: Clean up ZIP if desired
    if not args.keep_zip:
        zip_path.unlink()
        print(f"\n  Removed ZIP file: {zip_path}")

    print(f"\n{'='*60}")
    print(f"Download complete!")
    print(f"{'='*60}")
    print(f"All packages extracted to: {output_dir}")

    return 0


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

    # Download command
    download_parser = subparsers.add_parser('download', help='Download a package and its dependencies')
    download_parser.add_argument(
        'package_ref',
        help='Package reference (e.g., boost/1.81.0)'
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

    args = parser.parse_args()

    if args.command == 'upload':
        return cmd_upload(args)
    elif args.command == 'download':
        return cmd_download(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
