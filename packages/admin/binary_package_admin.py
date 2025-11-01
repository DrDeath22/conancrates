from django.contrib import admin
from packages.models import BinaryPackage


@admin.register(BinaryPackage)
class BinaryPackageAdmin(admin.ModelAdmin):
    list_display = ['package_version', 'package_id_short', 'os', 'arch', 'compiler',
                    'build_type', 'file_size_mb', 'download_count', 'created_at']
    list_filter = ['os', 'arch', 'compiler', 'build_type', 'created_at']
    search_fields = ['package_version__package__name', 'package_id']
    readonly_fields = ['created_at', 'download_count', 'file_size']

    fieldsets = [
        ('Package Information', {
            'fields': ['package_version', 'package_id']
        }),
        ('Configuration', {
            'fields': ['os', 'arch', 'compiler', 'compiler_version', 'build_type', 'options']
        }),
        ('Binary File', {
            'fields': ['binary_file', 'file_size', 'sha256']
        }),
        ('Statistics', {
            'fields': ['download_count', 'created_at'],
            'classes': ['collapse']
        }),
    ]

    def package_id_short(self, obj):
        return obj.package_id[:8] if obj.package_id else '-'
    package_id_short.short_description = 'Package ID'

    def file_size_mb(self, obj):
        if obj.file_size:
            return f"{obj.file_size / (1024 * 1024):.2f} MB"
        return '-'
    file_size_mb.short_description = 'Size'
