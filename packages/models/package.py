from django.db import models


class Package(models.Model):
    """
    Represents a Conan package (e.g., 'boost', 'zlib').
    This is the top-level entity that contains multiple versions.
    """
    name = models.CharField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True)
    homepage = models.URLField(blank=True, max_length=500)
    license = models.CharField(max_length=255, blank=True)
    author = models.CharField(max_length=255, blank=True)
    topics = models.CharField(max_length=500, blank=True, help_text="Comma-separated topics")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Stats
    download_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_topics_list(self):
        """Return topics as a list"""
        if self.topics:
            return [t.strip() for t in self.topics.split(',')]
        return []

    def latest_version(self):
        """Get the most recent version"""
        return self.versions.order_by('-created_at').first()
