from django.contrib import admin
from packages.models import Dependency


@admin.register(Dependency)
class DependencyAdmin(admin.ModelAdmin):
    list_display = ['package_version', 'requires_package', 'version_requirement', 'dependency_type']
    list_filter = ['dependency_type']
    search_fields = ['package_version__package__name', 'requires_package__name']

    fieldsets = [
        ('Dependency Information', {
            'fields': ['package_version', 'requires_package', 'version_requirement', 'dependency_type']
        }),
    ]
