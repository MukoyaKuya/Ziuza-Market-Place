from django.core.management.base import BaseCommand

from apps.marketplace.categories.models import Category

SEED = [
    ('Accessories', 'accessories', 'Belts, hats, scarves & accessories', []),
    ('Art & Collectibles', 'art-collectibles', 'Paintings, prints, sculptures & more', []),
    ('Bags & Purses', 'bags-purses', 'Handbags, totes, kiondos & wallets', []),
    ('Bath & Beauty', 'bath-beauty', 'Soaps, skincare, body & wellness', []),
    ('Books, Films & Music', 'books-media', 'Literature, prints, audio & art books', []),
    ('Clothing', 'fashion', 'Clothing, bags, shoes & accessories', [
        ('Women', 'fashion-women'),
        ('Men', 'fashion-men'),
        ('Kids', 'fashion-kids'),
    ]),
    ('Craft Supplies & Tools', 'craft-supplies', 'Tools, materials, beads & essentials', []),
    ('Electronics & Accessories', 'electronics-accessories', 'Phone cases, straps & tech accessories', []),
    ('Gifts', 'gifts', 'Unique handmade & personalized gifts', []),
    ('Home & Living', 'home-living', 'Decor, kitchen, furniture & more', [
        ('Furniture', 'furniture'),
        ('Kitchen', 'kitchen'),
        ('Lighting', 'lighting'),
    ]),
    ('Jewelry', 'jewelry', 'Beads, metals, handmade jewelry', []),
    ('Kids & Baby', 'kids-baby', 'Baby clothing, decor & accessories', []),
    ('Paper & Party Supplies', 'paper-party', 'Cards, stationery, party & event decor', []),
    ('Pet Supplies', 'pet-supplies', 'Collars, leashes, beds & pet accessories', []),
    ('Shoes', 'shoes', 'Leather sandals, boots & handmade shoes', []),
    ('Toys & Games', 'toys-games', 'Handmade toys, puzzles & games', []),
    ('Vintage', 'vintage', 'Retro, antique, classic finds', []),
    ('Weddings', 'wedding', 'Bridal wear, wedding decor & favors', []),
]


class Command(BaseCommand):
    help = 'Seed default Kenyan marketplace categories (idempotent by slug).'

    def handle(self, *args, **options):
        created = 0
        for position, (name, slug, description, children) in enumerate(SEED):
            parent, was_created = Category.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'description': description,
                    'position': position,
                    'is_visible': True,
                },
            )
            if was_created:
                created += 1
            for child_pos, (child_name, child_slug) in enumerate(children):
                _, child_created = Category.objects.get_or_create(
                    slug=child_slug,
                    defaults={
                        'name': child_name,
                        'parent': parent,
                        'position': child_pos,
                        'is_visible': True,
                    },
                )
                if child_created:
                    created += 1
        self.stdout.write(self.style.SUCCESS(f'Seed complete. Created {created} categories.'))
