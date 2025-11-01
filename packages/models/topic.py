from django.db import models


class Topic(models.Model):
    """
    Tags/topics for categorizing packages.
    """
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    packages = models.ManyToManyField('Package', related_name='topic_tags', blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def package_count(self):
        return self.packages.count()
