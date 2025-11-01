from django.contrib import admin
from packages.models import Package, PackageVersion


class PackageVersionInline(admin.TabularInline):
    """Inline display of versions for a package"""
    model = PackageVersion
    extra = 0
    fields = ['version', 'recipe_revision', 'created_at', 'uploaded_by']
    readonly_fields = ['created_at']
    show_change_link = True


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'author', 'license', 'version_count', 'download_count', 'created_at']
    list_filter = ['license', 'created_at']
    search_fields = ['name', 'description', 'author']
    readonly_fields = ['created_at', 'updated_at', 'download_count']
    inlines = [PackageVersionInline]

    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'description', 'author']
        }),
        ('Links & Metadata', {
            'fields': ['homepage', 'license', 'topics']
        }),
        ('Statistics', {
            'fields': ['download_count', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def version_count(self, obj):
        return obj.versions.count()
    version_count.short_description = 'Versions'
