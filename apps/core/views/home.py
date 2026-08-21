from django.views.generic import TemplateView

from apps.marketplace.content.selectors import (
    featured_listings,
    featured_shops,
    homepage_discovery,
    live_collections,
    live_hero_promo_card,
    live_hero_slides,
    live_homepage_sections,
    live_promo_banner_ad,
)
from apps.marketplace.listings.selectors import visible_root_categories


class HomeView(TemplateView):
    """Homepage composed from CMS sections + discovery selectors."""

    template_name = 'pages/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sections = live_homepage_sections()
        discovery_position = self.request.session.get('home_discovery_position', 0)
        discovery_category, discovery_listings, discovery_is_mixed = homepage_discovery(
            position=discovery_position,
            limit=4,
        )
        self.request.session['home_discovery_position'] = discovery_position + 1
        hero_slides = live_hero_slides()
        show_section_types = {s.section_type for s in sections} or {
            'hero',
            'promo_banner',
            'trust',
            'categories',
            'featured_listings',
            'collections',
        }
        show_promo_banner = ('promo_banner' in show_section_types or 'trust' in show_section_types) if sections else True
        context.update(
            {
                'page_title': 'Ziuza Marketplace | Celebrating Kenyan Crafts & Creators',
                'homepage_sections': sections,
                'show_section_types': show_section_types,
                'show_promo_banner': show_promo_banner,
                'hero_slides': hero_slides,
                'active_hero_slide': hero_slides[0] if hero_slides else None,
                'active_hero_promo_card': live_hero_promo_card(),
                'promo_banner_ad': live_promo_banner_ad(),
                'featured_listings': discovery_listings or featured_listings(limit=4),
                'featured_category': discovery_category,
                'discovery_is_mixed': discovery_is_mixed,
                'featured_shops': featured_shops(),
                'collections': live_collections(),
                'categories': list(visible_root_categories()[:6]),
            }
        )
        if self.request.user.is_authenticated:
            from apps.marketplace.search.saved import recent_listings_for_user, recommendations_for_user
            context['personalized_listings'] = recommendations_for_user(user=self.request.user, limit=8)
            context['recent_listings'] = recent_listings_for_user(user=self.request.user, limit=8)
        return context
