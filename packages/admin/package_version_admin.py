from django.contrib import admin
from packages.models import PackageVersion, Dependency, BinaryPackage


class DependencyInline(admin.TabularInline):
    """Inline display of dependencies"""
    model = Dependency
    extra = 1
    fk_name = 'package_version'
    fields = ['requires_package', 'version_requirement', 'dependency_type']


class BinaryPackageInline(admin.TabularInline):
    """Inline display of binary packages"""
    model = BinaryPackage
    extra = 0
    fields = ['package_id', 'os', 'arch', 'compiler', 'build_type', 'file_size', 'download_count']
    readonly_fields = ['download_count']
    show_change_link = True


@admin.register(PackageVersion)
class PackageVersionAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'version', 'recipe_revision_short', 'binary_count', 'uploaded_by', 'created_at']
    list_filter = ['created_at', 'package']
    search_fields = ['package__name', 'version', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [DependencyInline, BinaryPackageInline]

    fieldsets = [
        ('Package Information', {
            'fields': ['package', 'version', 'description']
        }),
        ('Recipe', {
            'fields': ['recipe_revision', 'recipe_file']
        }),
        ('Upload Information', {
            'fields': ['uploaded_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def recipe_revision_short(self, obj):
        if obj.recipe_revision:
            return obj.recipe_revision[:8]
        return '-'
    recipe_revision_short.short_description = 'Recipe Rev'

    def binary_count(self, obj):
        return obj.binaries.count()
    binary_count.short_description = 'Binaries'
