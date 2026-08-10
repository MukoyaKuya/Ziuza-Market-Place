import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class ShopSection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='sections')
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90)
    position = models.PositiveSmallIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    listings = models.ManyToManyField('listings.Listing', through='ShopSectionItem', related_name='shop_sections')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'name']
        constraints = [
            models.UniqueConstraint(fields=['shop', 'slug'], name='uniq_shop_section_slug'),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:80] or 'section'
            candidate = base
            counter = 2
            while ShopSection.objects.filter(shop=self.shop, slug=candidate).exclude(pk=self.pk).exists():
                candidate = f'{base}-{counter}'
                counter += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.shop}: {self.name}'


class ShopSectionItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section = models.ForeignKey(ShopSection, on_delete=models.CASCADE, related_name='items')
    listing = models.ForeignKey('listings.Listing', on_delete=models.CASCADE, related_name='section_items')
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['position', 'listing__title']
        constraints = [
            models.UniqueConstraint(fields=['section', 'listing'], name='uniq_section_listing'),
        ]

    def __str__(self):
        return f'{self.section}: {self.listing}'

    def clean(self):
        if self.section_id and self.listing_id and self.section.shop_id != self.listing.shop_id:
            raise ValidationError('Section listings must belong to the same shop as the section.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
