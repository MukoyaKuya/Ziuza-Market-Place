import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from apps.marketplace.listings.storage import private_digital_storage


class ProductType(models.TextChoices):
    PHYSICAL = 'physical', _('Physical item')
    DIGITAL = 'digital', _('Digital download')
    MADE_TO_ORDER = 'made_to_order', _('Made to order')


class ListingStatus(models.TextChoices):
    DRAFT = 'draft', _('Draft')
    PENDING_REVIEW = 'pending_review', _('Pending review')
    ACTIVE = 'active', _('Active')
    PAUSED = 'paused', _('Paused')
    SOLD_OUT = 'sold_out', _('Sold out')
    REJECTED = 'rejected', _('Rejected')
    ARCHIVED = 'archived', _('Archived')


class BulkOperationType(models.TextChoices):
    CATALOG_IMPORT = 'catalog_import', _('Catalogue import')
    CATALOG_EXPORT = 'catalog_export', _('Catalogue export')


class BulkOperationStatus(models.TextChoices):
    VALIDATED = 'validated', _('Validated')
    COMPLETED = 'completed', _('Completed')
    FAILED = 'failed', _('Failed')


class Listing(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.CASCADE,
        related_name='listings',
    )
    category = models.ForeignKey(
        'categories.Category',
        on_delete=models.PROTECT,
        related_name='listings',
    )
    title = models.CharField(_('title'), max_length=200)
    slug = models.SlugField(_('slug'), max_length=220, unique=True)
    short_description = models.CharField(_('short description'), max_length=300, blank=True)
    description = models.TextField(_('description'), blank=True)
    status = models.CharField(
        max_length=20,
        choices=ListingStatus.choices,
        default=ListingStatus.DRAFT,
        db_index=True,
    )
    base_price = models.DecimalField(
        _('base price'),
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    currency = models.CharField(_('currency'), max_length=3, default='KES')
    sku = models.CharField(_('SKU'), max_length=64, blank=True)
    is_featured = models.BooleanField(_('featured'), default=False)
    product_type = models.CharField(max_length=20, choices=ProductType.choices, default=ProductType.PHYSICAL, db_index=True)
    is_personalizable = models.BooleanField(_('is personalizable'), default=False)
    personalization_instructions = models.TextField(
        _('personalization instructions'),
        blank=True,
        help_text=_('Instructions for buyer custom text, e.g. Enter name to engrave'),
    )
    county_of_origin = models.CharField(_('county of origin'), max_length=100, blank=True)
    seo_title = models.CharField(
        _('search title'),
        max_length=70,
        blank=True,
        help_text=_('Optional title for search engines and social sharing.'),
    )
    seo_description = models.CharField(
        _('search description'),
        max_length=160,
        blank=True,
        help_text=_('Optional summary for search engines and social sharing.'),
    )
    shipping_profile = models.ForeignKey(
        'shipping.ShippingProfile',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='listings',
    )
    published_at = models.DateTimeField(_('published at'), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('listing')
        verbose_name_plural = _('listings')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'category']),
            models.Index(fields=['shop', 'status']),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug(self.title)
        super().save(*args, **kwargs)

    @classmethod
    def _unique_slug(cls, title: str) -> str:
        base = slugify(title)[:200] or 'listing'
        slug = base
        n = 2
        while cls.objects.filter(slug=slug).exists():
            slug = f'{base}-{n}'
            n += 1
        return slug

    @property
    def is_publicly_visible(self) -> bool:
        return self.status == ListingStatus.ACTIVE and self.shop.is_publicly_visible

    def mark_published(self):
        self.status = ListingStatus.ACTIVE
        self.published_at = timezone.now()


class ListingImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(_('image'), upload_to='listings/')
    alt_text = models.CharField(_('alt text'), max_length=200, blank=True)
    position = models.PositiveIntegerField(_('position'), default=0)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'created_at']
        verbose_name = _('listing image')
        verbose_name_plural = _('listing images')

    def __str__(self) -> str:
        return f'{self.listing_id} image {self.position}'


class ListingVariant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(_('name'), max_length=120)
    sku = models.CharField(_('SKU'), max_length=64, blank=True)
    price_override = models.DecimalField(
        _('price override'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    is_active = models.BooleanField(default=True)
    cover_image = models.ForeignKey(
        ListingImage, null=True, blank=True, on_delete=models.SET_NULL, related_name='variants'
    )
    option_summary = models.JSONField(default=dict, blank=True)
    selected_values = models.ManyToManyField('ListingOptionValue', blank=True, related_name='variants')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('listing variant')
        verbose_name_plural = _('listing variants')
        unique_together = [('listing', 'name')]

    def __str__(self) -> str:
        return f'{self.listing.title} — {self.name}'

    @property
    def effective_price(self) -> Decimal:
        return self.price_override if self.price_override is not None else self.listing.base_price


class Inventory(models.Model):
    """Authoritative stock. available_to_sell = quantity_available - quantity_reserved."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='inventory_rows')
    variant = models.OneToOneField(
        ListingVariant,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='inventory',
    )
    quantity_available = models.PositiveIntegerField(default=0)
    quantity_reserved = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=3)
    low_stock_alert_sent = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('inventory')
        verbose_name_plural = _('inventory')
        constraints = [
            models.UniqueConstraint(
                fields=['listing'],
                condition=models.Q(variant__isnull=True),
                name='uniq_listing_base_inventory',
            ),
        ]

    def __str__(self) -> str:
        target = self.variant.name if self.variant_id else 'base'
        return f'{self.listing_id} [{target}] {self.available_to_sell}'

    @property
    def available_to_sell(self) -> int:
        return max(0, self.quantity_available - self.quantity_reserved)


class ListingAttribute(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='attributes')
    name = models.CharField(_('name'), max_length=80)
    value = models.CharField(_('value'), max_length=255)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'name']
        verbose_name = _('listing attribute')
        verbose_name_plural = _('listing attributes')
        unique_together = [('listing', 'name')]

    def __str__(self) -> str:
        return f'{self.name}: {self.value}'


class PersonalizationFieldType(models.TextChoices):
    TEXT = 'text', _('Text')
    SELECT = 'select', _('Choice list')


class PersonalizationField(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='personalization_fields')
    label = models.CharField(max_length=120)
    instructions = models.CharField(max_length=300, blank=True)
    field_type = models.CharField(max_length=12, choices=PersonalizationFieldType.choices, default=PersonalizationFieldType.TEXT)
    options = models.JSONField(default=list, blank=True)
    is_required = models.BooleanField(default=False)
    max_length = models.PositiveSmallIntegerField(default=120)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['position', 'label']
        unique_together = [('listing', 'label')]


class ListingOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='option_groups')
    name = models.CharField(max_length=80)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['position', 'name']
        unique_together = [('listing', 'name')]


class DigitalAsset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='digital_assets')
    title = models.CharField(max_length=160)
    file = models.FileField(storage=private_digital_storage, upload_to='digital_assets/%Y/%m/')
    version = models.CharField(max_length=40, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']


class ListingOptionValue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    option = models.ForeignKey(ListingOption, on_delete=models.CASCADE, related_name='values')
    value = models.CharField(max_length=80)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['position', 'value']
        unique_together = [('option', 'value')]


class BulkOperation(models.Model):
    """Seller-visible audit record for catalogue imports and exports."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='bulk_operations')
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='listing_bulk_operations',
    )
    operation = models.CharField(max_length=24, choices=BulkOperationType.choices)
    status = models.CharField(max_length=16, choices=BulkOperationStatus.choices)
    file_name = models.CharField(max_length=255, blank=True)
    dry_run = models.BooleanField(default=False)
    total_rows = models.PositiveIntegerField(default=0)
    created_rows = models.PositiveIntegerField(default=0)
    updated_rows = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['shop', 'created_at'])]

    def __str__(self) -> str:
        return f'{self.get_operation_display()} — {self.shop}'
