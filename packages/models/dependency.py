from django.db import models


class Dependency(models.Model):
    """
    Represents a dependency relationship between package versions.
    """
    package_version = models.ForeignKey('PackageVersion', on_delete=models.CASCADE,
                                        related_name='dependencies')
    requires_package = models.ForeignKey('Package', on_delete=models.CASCADE,
                                         related_name='required_by')
    version_requirement = models.CharField(max_length=100,
                                           help_text="e.g., '>=1.0.0', '[1.0.0-2.0.0]'")

    # Dependency type
    DEPENDENCY_TYPES = [
        ('requires', 'Requires'),
        ('build_requires', 'Build Requires'),
        ('test_requires', 'Test Requires'),
    ]
    dependency_type = models.CharField(max_length=20, choices=DEPENDENCY_TYPES, default='requires')

    class Meta:
        verbose_name_plural = 'Dependencies'
        unique_together = ['package_version', 'requires_package', 'dependency_type']

    def __str__(self):
        return f"{self.package_version} requires {self.requires_package.name} {self.version_requirement}"
