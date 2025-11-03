"""
Tests for CLI tool helper functions.

These tests verify the utility functions in conancrates/conancrates.py
that don't require a full Conan installation or server.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys
import os

# Add parent directory to path so we can import the CLI tool module
cli_module_path = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, cli_module_path)

# Import from conancrates.conancrates module
import conancrates.conancrates as cli

# Create references to functions for easier testing
check_package_in_cache = cli.check_package_in_cache
get_binary_package_path = cli.get_binary_package_path
is_release_version = cli.is_release_version
parse_conan_profile = cli.parse_conan_profile


class TestGetBinaryPackagePath(unittest.TestCase):
    """Test get_binary_package_path returns Path objects correctly."""

    @patch('conancrates.conancrates.run_conan_command')
    def test_returns_path_object_when_found(self, mock_run):
        """Should return Path object when conan cache path command succeeds."""
        # Mock conan cache path returning a string path
        mock_run.return_value = "/home/user/.conan2/p/boost123/p\n"

        result = get_binary_package_path("boost/1.81.0", "abc123")

        # Should return Path object, not string
        self.assertIsInstance(result, Path)
        # Use Path for comparison to be platform-agnostic
        self.assertEqual(result, Path("/home/user/.conan2/p/boost123/p"))
        mock_run.assert_called_once()

    @patch('conancrates.conancrates.run_conan_command')
    def test_returns_none_when_not_found(self, mock_run):
        """Should return None when package not found in cache."""
        mock_run.return_value = None

        result = get_binary_package_path("notfound/1.0.0", "xyz789")

        self.assertIsNone(result)

    @patch('conancrates.conancrates.run_conan_command')
    def test_strips_whitespace_from_path(self, mock_run):
        """Should strip whitespace from conan command output."""
        mock_run.return_value = "  /path/with/spaces  \n"

        result = get_binary_package_path("pkg/1.0", "abc")

        # Use Path for comparison to be platform-agnostic
        self.assertEqual(result, Path("/path/with/spaces"))


class TestCheckPackageInCache(unittest.TestCase):
    """Test check_package_in_cache correctly detects cached packages."""

    @patch('conancrates.conancrates.get_binary_package_path')
    def test_returns_true_when_package_exists(self, mock_get_path):
        """Should return True when package path exists in cache."""
        # Create a mock Path that exists
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_get_path.return_value = mock_path

        result = check_package_in_cache("boost/1.81.0", "abc123")

        self.assertTrue(result)
        mock_path.exists.assert_called_once()

    @patch('conancrates.conancrates.get_binary_package_path')
    def test_returns_false_when_package_not_exists(self, mock_get_path):
        """Should return False when package path doesn't exist."""
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = False
        mock_get_path.return_value = mock_path

        result = check_package_in_cache("boost/1.81.0", "abc123")

        self.assertFalse(result)

    @patch('conancrates.conancrates.get_binary_package_path')
    def test_returns_false_when_path_is_none(self, mock_get_path):
        """Should return False when get_binary_package_path returns None."""
        mock_get_path.return_value = None

        result = check_package_in_cache("notfound/1.0.0", "xyz789")

        self.assertFalse(result)

    @patch('conancrates.conancrates.get_binary_package_path')
    def test_handles_exception_gracefully(self, mock_get_path):
        """Should return False if any exception occurs."""
        mock_get_path.side_effect = Exception("Unexpected error")

        result = check_package_in_cache("pkg/1.0", "abc")

        self.assertFalse(result)


class TestIsReleaseVersion(unittest.TestCase):
    """Test is_release_version correctly identifies pre-release versions."""

    def test_release_versions(self):
        """Should return True for release versions."""
        release_versions = [
            "1.0.0",
            "2.3.4",
            "10.20.30",
            "1.0",
            "3.2.1.5",
        ]
        for version in release_versions:
            with self.subTest(version=version):
                self.assertTrue(is_release_version(version),
                              f"{version} should be recognized as release version")

    def test_prerelease_versions(self):
        """Should return False for pre-release versions."""
        prerelease_versions = [
            "1.0.0-rc1",
            "2.3.4-beta",
            "1.0-alpha",
            "3.0-dev",
            "2.1-pre",
            "1.0-snapshot",
            "1.0.0-RC1",  # Test case insensitivity
            "2.0-BETA",
        ]
        for version in prerelease_versions:
            with self.subTest(version=version):
                self.assertFalse(is_release_version(version),
                               f"{version} should be recognized as pre-release")


class TestParseConanProfile(unittest.TestCase):
    """Test parse_conan_profile extracts settings correctly."""

    @patch('conancrates.conancrates.subprocess.run')
    @patch('conancrates.conancrates.get_conan_executable')
    def test_parses_profile_successfully(self, mock_get_exe, mock_run):
        """Should parse profile and extract settings."""
        mock_get_exe.return_value = 'conan'
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
Host profile:
[settings]
os=Linux
arch=x86_64
compiler=gcc
compiler.version=11
build_type=Release

Build profile:
Same as host
"""
        mock_run.return_value = mock_result

        settings = parse_conan_profile("default")

        self.assertIsNotNone(settings)
        self.assertEqual(settings['os'], 'Linux')
        self.assertEqual(settings['arch'], 'x86_64')
        self.assertEqual(settings['compiler'], 'gcc')
        self.assertEqual(settings['compiler_version'], '11')
        self.assertEqual(settings['build_type'], 'Release')

    @patch('conancrates.conancrates.subprocess.run')
    @patch('conancrates.conancrates.get_conan_executable')
    def test_returns_none_when_profile_not_found(self, mock_get_exe, mock_run):
        """Should return None when profile doesn't exist."""
        mock_get_exe.return_value = 'conan'
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Profile 'notfound' not found"
        mock_run.return_value = mock_result

        settings = parse_conan_profile("notfound")

        self.assertIsNone(settings)

    @patch('conancrates.conancrates.subprocess.run')
    @patch('conancrates.conancrates.get_conan_executable')
    def test_returns_none_when_missing_required_settings(self, mock_get_exe, mock_run):
        """Should return None when profile is missing required settings."""
        mock_get_exe.return_value = 'conan'
        mock_result = Mock()
        mock_result.returncode = 0
        # Missing compiler.version
        mock_result.stdout = """
Host profile:
[settings]
os=Linux
arch=x86_64
compiler=gcc
build_type=Release
"""
        mock_run.return_value = mock_result

        settings = parse_conan_profile("incomplete")

        self.assertIsNone(settings)


if __name__ == '__main__':
    unittest.main()
