"""
Django admin configuration for ConanCrates
"""
from .package_admin import PackageAdmin
from .package_version_admin import PackageVersionAdmin
from .binary_package_admin import BinaryPackageAdmin
from .dependency_admin import DependencyAdmin
from .topic_admin import TopicAdmin

__all__ = [
    'PackageAdmin',
    'PackageVersionAdmin',
    'BinaryPackageAdmin',
    'DependencyAdmin',
    'TopicAdmin',
]
