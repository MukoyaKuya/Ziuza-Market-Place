from django.contrib.sitemaps import Sitemap
from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.marketplace.categories.models import Category
from apps.marketplace.listings.models import Listing, ListingStatus
from apps.marketplace.shops.models import Shop, ShopVerificationStatus


class ListingSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.8

    def items(self):
        return (
            Listing.objects.filter(
                status=ListingStatus.ACTIVE,
                shop__is_active=True,
                shop__vacation_mode=False,
            )
            .exclude(shop__verification_status=ShopVerificationStatus.SUSPENDED)
            .order_by('-published_at')[:5000]
        )

    def location(self, obj):
        return reverse('listings:detail', kwargs={'slug': obj.slug})

    def lastmod(self, obj):
        return obj.updated_at


class CategorySitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return Category.objects.filter(is_visible=True)

    def location(self, obj):
        return reverse('listings:category_detail', kwargs={'slug': obj.slug})


class ShopSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.5

    def items(self):
        return Shop.objects.filter(is_active=True, vacation_mode=False).exclude(
            verification_status=ShopVerificationStatus.SUSPENDED
        )

    def location(self, obj):
        return reverse('shops:public_shop', kwargs={'slug': obj.slug})


@require_GET
def robots_txt(request):
    from django.conf import settings

    sitemap_path = reverse("sitemap")
    public_base = (getattr(settings, "PUBLIC_SITE_URL", "") or "").rstrip("/")
    if public_base:
        sitemap_url = f"{public_base}{sitemap_path}"
    else:
        sitemap_url = request.build_absolute_uri(sitemap_path)
        if sitemap_url.startswith("http://"):
            sitemap_url = "https://" + sitemap_url[len("http://"):]

    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /account/',
        'Disallow: /seller/',
        'Disallow: /checkout/',
        'Disallow: /admin/',
        f'Sitemap: {sitemap_url}',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')
