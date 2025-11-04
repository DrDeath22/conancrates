"""
Signal handlers for cleaning up MinIO files when database objects are deleted.
"""
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver
from .models import Package, PackageVersion, BinaryPackage


@receiver(pre_delete, sender=BinaryPackage)
def delete_binary_files(sender, instance, **kwargs):
    """
    Delete binary_file and rust_crate_file from MinIO when BinaryPackage is deleted.
    """
    # Delete binary file if it exists
    if instance.binary_file:
        filename = instance.binary_file.name
        try:
            instance.binary_file.delete(save=False)
            print(f"✓ Deleted binary file from MinIO: {filename}")
        except Exception as e:
            print(f"✗ Error deleting binary file {filename}: {e}")

    # Delete rust crate file if it exists
    if instance.rust_crate_file:
        filename = instance.rust_crate_file.name
        try:
            instance.rust_crate_file.delete(save=False)
            print(f"✓ Deleted rust crate file from MinIO: {filename}")
        except Exception as e:
            print(f"✗ Error deleting rust crate file {filename}: {e}")


@receiver(pre_delete, sender=PackageVersion)
def delete_package_version_files(sender, instance, **kwargs):
    """
    Delete recipe_file from MinIO when PackageVersion is deleted.
    """
    if instance.recipe_file:
        filename = instance.recipe_file.name
        try:
            instance.recipe_file.delete(save=False)
            print(f"✓ Deleted recipe file from MinIO: {filename}")
        except Exception as e:
            print(f"✗ Error deleting recipe file {filename}: {e}")
