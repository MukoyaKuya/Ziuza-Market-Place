from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.marketplace.content.models import (
    HeroSlide,
    HomepageSection,
    HomepageSectionType,
    VisibilityStatus,
)


class Command(BaseCommand):
    help = 'Seed default homepage sections and a published hero slide.'

    def handle(self, *args, **options):
        defaults = [
            (HomepageSectionType.HERO, 'Hero', 0),
            (HomepageSectionType.TRUST, 'Trust', 10),
            (HomepageSectionType.CATEGORIES, 'Shop by category', 20),
            (HomepageSectionType.FEATURED_LISTINGS, 'Featured listings', 30),
            (HomepageSectionType.COLLECTIONS, 'Collections', 40),
            (HomepageSectionType.FEATURED_SHOPS, 'Seller spotlight', 50),
        ]
        for section_type, title, position in defaults:
            HomepageSection.objects.get_or_create(
                section_type=section_type,
                defaults={
                    'title': title,
                    'position': position,
                    'is_visible': True,
                },
            )
        HeroSlide.objects.get_or_create(
            title='Made in Kenya. Loved Everywhere.',
            defaults={
                'subtitle': 'Discover unique, handmade, and vintage treasures from talented Kenyan creators.',
                'primary_cta_label': 'Shop Now',
                'primary_cta_url': '/categories/',
                'secondary_cta_label': 'Shop Kenyan Makers',
                'secondary_cta_url': '/categories/',
                'priority': 0,
                'status': VisibilityStatus.PUBLISHED,
                'starts_at': timezone.now(),
            },
        )
        self.stdout.write(self.style.SUCCESS('Homepage CMS seed complete.'))
