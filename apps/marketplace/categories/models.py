import uuid

from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class Category(models.Model):
    """Hierarchical, data-driven marketplace category."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        related_name='children',
        on_delete=models.CASCADE,
    )
    name = models.CharField(_('name'), max_length=120)
    slug = models.SlugField(_('slug'), max_length=140, unique=True)
    description = models.TextField(_('description'), blank=True)
    icon = models.CharField(_('icon'), max_length=64, blank=True)
    image = models.ImageField(_('image'), upload_to='categories/', blank=True)
    position = models.PositiveIntegerField(_('position'), default=0)
    is_visible = models.BooleanField(_('visible'), default=True)
    seo_title = models.CharField(_('SEO title'), max_length=160, blank=True)
    seo_description = models.CharField(_('SEO description'), max_length=320, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('category')
        verbose_name_plural = _('categories')
        ordering = ['position', 'name']

    def __str__(self) -> str:
        return self.name

    @property
    def get_icon_url(self) -> str:
        if self.image:
            return self.image.url

        static_icons = {
            'home-living': 'images/category_icons/homeliving.png',
            'fashion': 'images/category_icons/fashion.png',
            'art-collectibles': 'images/category_icons/art_collectibles.png',
            'jewelry': 'images/category_icons/jewelry.png',
            'craft-supplies': 'images/category_icons/craft_supplies.png',
            'vintage': 'images/category_icons/vintage.png',
        }
        if self.slug in static_icons:
            from django.templatetags.static import static
            return static(static_icons[self.slug])
        return ''

    @property
    def get_icon_name(self) -> str:
        if self.icon:
            return self.icon

        icon_map = {
            'home-living': 'chair',
            'fashion': 'dress',
            'art-collectibles': 'palette',
            'jewelry': 'necklace',
            'craft-supplies': 'scissors',
            'vintage': 'clock',
            'gifts': 'gift',
            'accessories': 'cart',
            'bags-purses': 'cart',
            'wedding': 'gift',
            'back-to-school': 'book',
        }
        return icon_map.get(self.slug, 'grid')


    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:120] or 'category'
            slug = base
            n = 2
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)
