import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class SavedSearch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_searches')
    name = models.CharField(max_length=120)
    query = models.CharField(max_length=100, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    fingerprint = models.CharField(max_length=64)
    alerts_enabled = models.BooleanField(default=True)
    last_checked_at = models.DateTimeField(default=timezone.now)
    last_notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'fingerprint'], name='uniq_user_saved_search'),
        ]

    def __str__(self):
        return f'{self.name} — {self.user}'


class RecentlyViewedListing(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='recently_viewed_listings')
    listing = models.ForeignKey('listings.Listing', on_delete=models.CASCADE, related_name='recent_views')
    view_count = models.PositiveIntegerField(default=1)
    last_viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_viewed_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'listing'], name='uniq_user_recent_listing'),
        ]
        indexes = [models.Index(fields=['user', 'last_viewed_at'])]

    def __str__(self):
        return f'{self.user} viewed {self.listing}'
