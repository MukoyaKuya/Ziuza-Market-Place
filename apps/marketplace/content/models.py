import uuid

from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class VisibilityStatus(models.TextChoices):
    DRAFT = 'draft', _('Draft')
    SCHEDULED = 'scheduled', _('Scheduled')
    PUBLISHED = 'published', _('Published')
    UNPUBLISHED = 'unpublished', _('Unpublished')


class HomepageSectionType(models.TextChoices):
    HERO = 'hero', _('Hero')
    FEATURED_LISTINGS = 'featured_listings', _('Featured listings')
    FEATURED_SHOPS = 'featured_shops', _('Featured shops')
    CATEGORIES = 'categories', _('Categories')
    COLLECTIONS = 'collections', _('Collections')
    TRUST = 'trust', _('Trust')
    CUSTOM = 'custom', _('Custom')


class HomepageSection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section_type = models.CharField(max_length=40, choices=HomepageSectionType.choices)
    title = models.CharField(max_length=160, blank=True)
    subtitle = models.CharField(max_length=255, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    configuration = models.JSONField(default=dict, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'title']

    def __str__(self):
        return self.title or self.section_type

    def is_live(self, *, now=None) -> bool:
        if not self.is_visible:
            return False
        now = now or timezone.now()
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now >= self.ends_at:
            return False
        return True


class HeroSlide(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True)
    desktop_image = models.ImageField(upload_to='cms/hero/', blank=True)
    mobile_image = models.ImageField(upload_to='cms/hero/', blank=True)
    primary_cta_label = models.CharField(max_length=80, blank=True)
    primary_cta_url = models.CharField(max_length=255, blank=True)
    secondary_cta_label = models.CharField(max_length=80, blank=True)
    secondary_cta_url = models.CharField(max_length=255, blank=True)
    background_configuration = models.JSONField(default=dict, blank=True)
    priority = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=VisibilityStatus.choices,
        default=VisibilityStatus.DRAFT,
    )
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['priority', '-updated_at']

    def __str__(self):
        return self.title

    def is_live(self, *, now=None) -> bool:
        now = now or timezone.now()
        if self.status == VisibilityStatus.UNPUBLISHED:
            return False
        if self.status == VisibilityStatus.DRAFT:
            return False
        if self.status == VisibilityStatus.PUBLISHED:
            if self.ends_at and now >= self.ends_at:
                return False
            if self.starts_at and now < self.starts_at:
                return False
            return True
        if self.status == VisibilityStatus.SCHEDULED:
            if self.starts_at and now < self.starts_at:
                return False
            if self.ends_at and now >= self.ends_at:
                return False
            return self.starts_at is not None and now >= self.starts_at
        return False


class Collection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='cms/collections/', blank=True)
    visibility = models.CharField(
        max_length=20,
        choices=VisibilityStatus.choices,
        default=VisibilityStatus.DRAFT,
    )
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    listings = models.ManyToManyField(
        'listings.Listing',
        through='CollectionListing',
        related_name='collections',
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:160] or 'collection'
            slug = base
            n = 2
            while Collection.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def is_live(self, *, now=None) -> bool:
        now = now or timezone.now()
        if self.visibility in {VisibilityStatus.DRAFT, VisibilityStatus.UNPUBLISHED}:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now >= self.ends_at:
            return False
        return self.visibility in {VisibilityStatus.PUBLISHED, VisibilityStatus.SCHEDULED}


class CollectionListing(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    listing = models.ForeignKey('listings.Listing', on_delete=models.CASCADE)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position']
        unique_together = [('collection', 'listing')]
