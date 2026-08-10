import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class ShopVerificationStatus(models.TextChoices):
    UNVERIFIED = 'unverified', _('Unverified')
    PENDING = 'pending', _('Pending')
    VERIFIED = 'verified', _('Verified')
    REJECTED = 'rejected', _('Rejected')
    SUSPENDED = 'suspended', _('Suspended')


class Shop(models.Model):
    """Seller shop — marketplace presence for a creator/merchant."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shop',
    )
    name = models.CharField(_('shop name'), max_length=120)
    slug = models.SlugField(_('slug'), max_length=140, unique=True)
    logo = models.ImageField(_('logo'), upload_to='shops/logos/', blank=True)
    banner = models.ImageField(_('banner'), upload_to='shops/banners/', blank=True)
    description = models.TextField(_('description'), blank=True)
    announcement = models.CharField(_('shop announcement'), max_length=300, blank=True)
    seo_title = models.CharField(_('search title'), max_length=70, blank=True)
    seo_description = models.CharField(_('search description'), max_length=160, blank=True)
    county = models.CharField(_('county'), max_length=100, default='Nairobi')
    sub_county = models.CharField(_('sub county'), max_length=100, blank=True)
    ward = models.CharField(_('ward'), max_length=100, blank=True)
    village = models.CharField(_('village / street'), max_length=150, blank=True)
    location_text = models.CharField(_('location'), max_length=255, blank=True)
    verification_status = models.CharField(
        max_length=20,
        choices=ShopVerificationStatus.choices,
        default=ShopVerificationStatus.UNVERIFIED,
    )
    rating_average = models.DecimalField(
        _('rating average'),
        max_digits=3,
        decimal_places=2,
        default=0,
    )
    rating_count = models.PositiveIntegerField(_('rating count'), default=0)
    policies = models.TextField(_('shop policies'), blank=True)
    shipping_policy = models.TextField(_('shipping policy'), blank=True)
    return_policy = models.TextField(_('returns and exchanges policy'), blank=True)
    processing_days_min = models.PositiveSmallIntegerField(_('minimum processing days'), default=1)
    processing_days_max = models.PositiveSmallIntegerField(_('maximum processing days'), default=3)
    vacation_mode = models.BooleanField(_('vacation mode'), default=False)
    is_active = models.BooleanField(_('active'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('shop')
        verbose_name_plural = _('shops')
        ordering = ['name']

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug(self.name)
        super().save(*args, **kwargs)

    @staticmethod
    def _unique_slug(name: str) -> str:
        base = slugify(name)[:120] or 'shop'
        slug = base
        counter = 2
        while Shop.objects.filter(slug=slug).exists():
            slug = f'{base}-{counter}'
            counter += 1
        return slug

    @property
    def is_verified(self) -> bool:
        return self.verification_status == ShopVerificationStatus.VERIFIED

    @property
    def is_publicly_visible(self) -> bool:
        return (
            self.is_active
            and not self.vacation_mode
            and self.verification_status != ShopVerificationStatus.SUSPENDED
        )
