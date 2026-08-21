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
    PROMO_BANNER = 'promo_banner', _('Promotional banner')
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


class HeroPromoCard(models.Model):
    """Right side hero promo card (e.g. Ziuza Maridadis / Holiday Specials)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(_('title'), max_length=160, default='Ziuza Maridadis')
    badge_text = models.CharField(_('badge text'), max_length=80, default='Curated Selection')
    subtitle = models.CharField(_('subtitle'), max_length=255, default='Handpicked collections just for you.')
    button_label = models.CharField(_('button label'), max_length=80, default='Explore Maridadis')
    button_url = models.CharField(_('button URL'), max_length=255, default='/picks/')
    background_color = models.CharField(_('background color'), max_length=30, default='#00482B')
    accent_color = models.CharField(_('accent bar color'), max_length=30, default='#C8102E')
    image = models.ImageField(_('custom promo image'), upload_to='cms/promo/', blank=True)
    priority = models.PositiveIntegerField(_('priority'), default=0)
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=VisibilityStatus.choices,
        default=VisibilityStatus.PUBLISHED,
    )
    starts_at = models.DateTimeField(_('starts at'), null=True, blank=True)
    ends_at = models.DateTimeField(_('ends at'), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('hero promo card')
        verbose_name_plural = _('hero promo cards')
        ordering = ['priority', '-updated_at']

    def __str__(self):
        return self.title

    def is_live(self, *, now=None) -> bool:
        now = now or timezone.now()
        if self.status == VisibilityStatus.UNPUBLISHED or self.status == VisibilityStatus.DRAFT:
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


class PromoBannerAd(models.Model):
    """Admin-managed promotional GIF/banner ads (e.g. homepage strip ad)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(_('banner title / campaign'), max_length=160)
    image = models.ImageField(_('banner image / GIF'), upload_to='cms/banners/', blank=True,
                              help_text=_('Upload animated GIF, PNG, or WebP banner (e.g. 1200x120px)'))
    target_url = models.CharField(_('target URL'), max_length=255, default='/local/', help_text=_('Destination URL when banner is clicked'))
    alt_text = models.CharField(_('alt text'), max_length=200, blank=True, help_text=_('Accessibility description for the banner'))
    is_active = models.BooleanField(_('is active'), default=True)
    priority = models.PositiveIntegerField(_('priority'), default=0)
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=VisibilityStatus.choices,
        default=VisibilityStatus.PUBLISHED,
    )
    starts_at = models.DateTimeField(_('starts at'), null=True, blank=True)
    ends_at = models.DateTimeField(_('ends at'), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('promotional banner ad')
        verbose_name_plural = _('promotional banner ads')
        ordering = ['priority', '-updated_at']

    def __str__(self):
        return self.title

    def is_live(self, *, now=None) -> bool:
        if not self.is_active:
            return False
        now = now or timezone.now()
        if self.status in {VisibilityStatus.UNPUBLISHED, VisibilityStatus.DRAFT}:
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
