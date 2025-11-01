"""
Test suite for ConanCrates packages app
"""
from .test_models import *
from .test_views import *
from .test_admin import *

__all__ = [
    'PackageModelTests',
    'PackageVersionModelTests',
    'BinaryPackageModelTests',
    'DependencyModelTests',
    'TopicModelTests',
    'PackageViewTests',
    'TopicViewTests',
    'AdminTests',
]
