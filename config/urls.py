from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.core.api import api
from apps.core.sitemaps import CategorySitemap, ListingSitemap, ShopSitemap, robots_txt

sitemaps = {
    'listings': ListingSitemap,
    'categories': CategorySitemap,
    'shops': ShopSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api.urls),
    path('', include('apps.core.urls')),
    path('account/', include('apps.accounts.urls')),
    path('', include('apps.marketplace.content.urls')),
    path('', include('apps.marketplace.listings.urls')),
    path('', include('apps.marketplace.search.urls')),
    path('', include('apps.marketplace.favorites.urls')),
    path('', include('apps.marketplace.cart.urls')),
    path('', include('apps.marketplace.orders.urls')),
    path('', include('apps.marketplace.payments.urls')),
    path('', include('apps.marketplace.shipping.urls')),
    path('', include('apps.marketplace.reviews.urls')),
    path('', include('apps.marketplace.notifications.urls')),
    path('', include('apps.marketplace.messaging.urls')),
    path('', include('apps.marketplace.analytics.urls')),
    path('', include('apps.marketplace.promotions.urls')),
    path('', include('apps.marketplace.shops.urls')),
    path('health/', include('apps.core.urls_health')),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
]

handler400 = 'apps.core.views.errors.bad_request'
handler403 = 'apps.core.views.errors.permission_denied'
handler404 = 'apps.core.views.errors.page_not_found'
handler500 = 'apps.core.views.errors.server_error'

# In DEBUG, django.contrib.staticfiles serves STATICFILES_DIRS via runserver.
# Only mount media here; do not point STATIC_URL at empty STATIC_ROOT.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
