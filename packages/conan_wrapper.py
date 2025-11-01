"""
Wrapper for Conan CLI operations

This module provides functions to interact with the Conan package manager
for dependency resolution and package downloads. It wraps Conan CLI commands
to ensure 100% identical dependency resolution logic.
"""
import os
import sys
import json
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ConanError(Exception):
    """Exception raised when Conan operations fail"""
    pass


def get_conan_executable() -> str:
    """
    Get the path to the conan executable.

    For development, tries venv first. For production, uses system conan.

    Returns:
        str: Path to conan executable
    """
    # Try to find venv conan (development)
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        # We're in a virtual environment
        if sys.platform == 'win32':
            venv_conan = Path(sys.prefix) / 'Scripts' / 'conan.exe'
        else:
            venv_conan = Path(sys.prefix) / 'bin' / 'conan'

        if venv_conan.exists():
            return str(venv_conan)

    # Fall back to system conan (production)
    return 'conan'


def check_conan_available() -> bool:
    """
    Check if Conan is available in the system

    Returns:
        bool: True if Conan is available, False otherwise
    """
    try:
        conan_exe = get_conan_executable()
        result = subprocess.run(
            [conan_exe, '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def get_conan_version() -> Optional[str]:
    """
    Get the installed Conan version

    Returns:
        str: Version string or None if Conan is not available
    """
    try:
        conan_exe = get_conan_executable()
        result = subprocess.run(
            [conan_exe, '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            # Output format: "Conan version 2.x.x"
            return result.stdout.strip()
        return None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def create_conanfile(package_name: str, version: str, work_dir: Path) -> Path:
    """
    Create a conanfile.txt for the given package

    Args:
        package_name: Name of the package
        version: Version of the package
        work_dir: Working directory to create the file in

    Returns:
        Path: Path to the created conanfile.txt
    """
    conanfile_path = work_dir / "conanfile.txt"
    content = f"""[requires]
{package_name}/{version}

[generators]
"""
    conanfile_path.write_text(content)
    return conanfile_path


def create_profile(os_name: str, arch: str, compiler: str,
                   compiler_version: str, build_type: str,
                   work_dir: Path) -> Path:
    """
    Create a Conan profile with the specified settings

    Args:
        os_name: Operating system (Linux, Windows, macOS)
        arch: Architecture (x86_64, armv8, etc.)
        compiler: Compiler (gcc, msvc, apple-clang, clang)
        compiler_version: Compiler version
        build_type: Build type (Release, Debug)
        work_dir: Working directory to create the profile in

    Returns:
        Path: Path to the created profile
    """
    profile_path = work_dir / "profile"

    # Map our OS names to Conan's expected values
    os_map = {
        'Linux': 'Linux',
        'Windows': 'Windows',
        'macOS': 'Macos',
    }

    conan_os = os_map.get(os_name, os_name)

    content = f"""[settings]
os={conan_os}
arch={arch}
compiler={compiler}
compiler.version={compiler_version}
build_type={build_type}
"""
    profile_path.write_text(content)
    return profile_path


def resolve_dependencies(package_name: str, version: str,
                         os_name: str, arch: str, compiler: str,
                         compiler_version: str, build_type: str,
                         registry_url: Optional[str] = None) -> Dict:
    """
    Use Conan to resolve dependencies for a package

    This function creates a temporary directory, sets up a conanfile.txt
    and profile, then runs 'conan install' to resolve all dependencies.

    Args:
        package_name: Name of the package
        version: Version of the package
        os_name: Operating system
        arch: Architecture
        compiler: Compiler
        compiler_version: Compiler version
        build_type: Build type
        registry_url: Optional Conan remote URL

    Returns:
        dict: Information about resolved packages including:
            - 'packages': List of resolved package dicts with name, version, package_id
            - 'graph': Dependency graph information
            - 'error': Error message if resolution failed

    Raises:
        ConanError: If Conan is not available or resolution fails
    """
    if not check_conan_available():
        raise ConanError(
            "Conan is not available. Please install it: pip install conan"
        )

    # Create temporary working directory
    with tempfile.TemporaryDirectory() as temp_dir:
        work_dir = Path(temp_dir)

        # Create conanfile.txt
        conanfile_path = create_conanfile(package_name, version, work_dir)

        # Create profile
        profile_path = create_profile(
            os_name, arch, compiler, compiler_version, build_type, work_dir
        )

        # Build conan install command
        conan_exe = get_conan_executable()
        cmd = [
            conan_exe, 'install',
            str(conanfile_path.parent),
            '--profile', str(profile_path),
            '--format', 'json',
            '--build=never',  # Never build - only use what's in cache
            '--update=False',  # Don't check remotes for updates
        ]

        # Add remote if specified
        if registry_url:
            # TODO: Add remote configuration
            pass

        try:
            # Run conan install using only local cache (no remotes configured)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=work_dir
            )

            if result.returncode != 0:
                return {
                    'success': False,
                    'error': f"Conan install failed: {result.stderr}",
                    'packages': []
                }

            # Parse JSON output
            # Conan 2.x outputs JSON graph info
            output_lines = result.stdout.strip().split('\n')
            json_output = None

            for line in output_lines:
                if line.startswith('{'):
                    try:
                        json_output = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue

            if not json_output:
                # Fall back to parsing text output
                return parse_conan_install_output(result.stdout)

            # Extract package information from JSON
            packages = extract_packages_from_json(json_output)

            return {
                'success': True,
                'packages': packages,
                'graph': json_output
            }

        except subprocess.TimeoutExpired:
            raise ConanError("Conan install timed out after 5 minutes")
        except Exception as e:
            raise ConanError(f"Conan install failed: {str(e)}")


def parse_conan_install_output(output: str) -> Dict:
    """
    Parse Conan install text output to extract package information

    This is a fallback when JSON output is not available.

    Args:
        output: Text output from conan install command

    Returns:
        dict: Parsed package information
    """
    packages = []

    # Parse the output line by line
    lines = output.split('\n')
    current_package = None

    for line in lines:
        line = line.strip()

        # Look for package references like "package/version"
        if '/' in line and ':' not in line:
            parts = line.split('/')
            if len(parts) == 2:
                pkg_name, pkg_version = parts[0].strip(), parts[1].strip()
                current_package = {
                    'name': pkg_name,
                    'version': pkg_version,
                    'package_id': 'unknown'
                }
                packages.append(current_package)

    return {
        'success': True,
        'packages': packages,
        'graph': None
    }


def extract_packages_from_json(graph_json: Dict) -> List[Dict]:
    """
    Extract package list from Conan graph JSON

    Args:
        graph_json: JSON output from conan install

    Returns:
        list: List of package dicts with name, version, package_id
    """
    packages = []

    # Conan 2.x graph format
    if 'graph' in graph_json and 'nodes' in graph_json['graph']:
        nodes = graph_json['graph']['nodes']

        for node_id, node_data in nodes.items():
            # Skip the root node (consumer)
            if node_data.get('ref') == 'conanfile.txt':
                continue

            ref = node_data.get('ref', '')
            if '/' in ref:
                pkg_name, pkg_version = ref.split('/', 1)
                # Remove revision if present
                pkg_version = pkg_version.split('#')[0]

                package_id = node_data.get('package_id', 'unknown')

                packages.append({
                    'name': pkg_name,
                    'version': pkg_version,
                    'package_id': package_id,
                    'context': node_data.get('context', 'host')
                })

    return packages


def download_packages(package_list: List[Dict],
                      os_name: str, arch: str, compiler: str,
                      compiler_version: str, build_type: str,
                      output_dir: Path) -> Dict:
    """
    Download the resolved packages using Conan

    Args:
        package_list: List of packages from resolve_dependencies
        os_name: Operating system
        arch: Architecture
        compiler: Compiler
        compiler_version: Compiler version
        build_type: Build type
        output_dir: Directory to download packages to

    Returns:
        dict: Download results with paths to downloaded packages
    """
    if not check_conan_available():
        raise ConanError("Conan is not available")

    downloaded = []

    with tempfile.TemporaryDirectory() as temp_dir:
        work_dir = Path(temp_dir)

        # Create profile
        profile_path = create_profile(
            os_name, arch, compiler, compiler_version, build_type, work_dir
        )

        for pkg in package_list:
            pkg_name = pkg['name']
            pkg_version = pkg['version']
            pkg_id = pkg.get('package_id', 'unknown')

            # Use conan download command
            conan_exe = get_conan_executable()
            cmd = [
                conan_exe, 'download',
                f"{pkg_name}/{pkg_version}",
                '--profile', str(profile_path)
            ]

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    cwd=work_dir
                )

                if result.returncode == 0:
                    downloaded.append({
                        'name': pkg_name,
                        'version': pkg_version,
                        'package_id': pkg_id,
                        'success': True
                    })
                else:
                    downloaded.append({
                        'name': pkg_name,
                        'version': pkg_version,
                        'package_id': pkg_id,
                        'success': False,
                        'error': result.stderr
                    })

            except Exception as e:
                downloaded.append({
                    'name': pkg_name,
                    'version': pkg_version,
                    'package_id': pkg_id,
                    'success': False,
                    'error': str(e)
                })

    return {
        'success': True,
        'downloads': downloaded
    }
