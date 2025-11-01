from django.db import models
from django.contrib.auth.models import User


class PackageVersion(models.Model):
    """
    Represents a specific version of a package (e.g., 'boost/1.81.0').
    Contains the recipe and metadata.
    """
    package = models.ForeignKey('Package', on_delete=models.CASCADE, related_name='versions')
    version = models.CharField(max_length=100, db_index=True)

    # Recipe information
    recipe_revision = models.CharField(max_length=64, blank=True, help_text="Git/hash of recipe")
    recipe_file = models.FileField(upload_to='recipes/', blank=True, null=True)
    recipe_content = models.TextField(blank=True, help_text="Content of conanfile.py")

    # Settings that affect this version
    description = models.TextField(blank=True)

    # User who uploaded
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['package', 'version']

    def __str__(self):
        return f"{self.package.name}/{self.version}"

    def full_name(self):
        return f"{self.package.name}/{self.version}"
