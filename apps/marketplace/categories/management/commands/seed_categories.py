from django.core.management.base import BaseCommand

from apps.marketplace.categories.models import Category

SEED = [
    ('Accessories', 'accessories', 'Belts, hats, scarves & accessories', 'cart', []),
    ('Art & Collectibles', 'art-collectibles', 'Paintings, prints, sculptures & more', 'palette', []),
    ('Back to School', 'back-to-school', 'Uniforms, school supplies, university paraphernalia, books & boarding essentials', 'book', [
        ('School Uniforms & Sportswear', 'school-uniforms'),
        ('School Supplies & Stationery', 'school-supplies'),
        ('University & College Paraphernalia', 'university-paraphernalia'),
        ('Textbooks & Revision Materials', 'school-books'),
        ('Boarding & Hostel Essentials', 'boarding-essentials'),
        ('Art, Music & Sports Gear', 'school-art-sports'),
    ]),
    ('Bags & Purses', 'bags-purses', 'Handbags, totes, kiondos & wallets', 'cart', []),
    ('Bath & Beauty', 'bath-beauty', 'Soaps, skincare, body & wellness', 'grid', []),
    ('Books, Films & Music', 'books-media', 'Literature, prints, audio & art books', 'grid', []),
    ('Clothing', 'fashion', 'Clothing, bags, shoes & accessories', 'dress', [
        ('Women', 'fashion-women'),
        ('Men', 'fashion-men'),
        ('Kids', 'fashion-kids'),
    ]),
    ('Craft Supplies & Tools', 'craft-supplies', 'Tools, materials, beads & essentials', 'scissors', []),
    ('Electronics & Accessories', 'electronics-accessories', 'Phone cases, straps & tech accessories', 'grid', []),
    ('Gifts', 'gifts', 'Unique handmade & personalized gifts', 'gift', [
        ('Kids Gifts', 'kids-gifts'),
        ('Men Gifts', 'men-gifts'),
        ('Mother Gifts', 'mother-gifts'),
        ('Father Gifts', 'father-gifts'),
        ('Boss Gifts', 'boss-gifts'),
        ('Wedding Gifts', 'wedding-gifts'),
        ('Valentines Gifts', 'valentines-gifts'),
        ('Madaraka Specials', 'madaraka-specials'),
        ('Jamhuri Day', 'jamhuri-day'),
        ('Liberation Day', 'liberation-day'),
    ]),
    ('Home & Living', 'home-living', 'Decor, kitchen, furniture & more', 'chair', [
        ('Furniture', 'furniture'),
        ('Kitchen', 'kitchen'),
        ('Lighting', 'lighting'),
    ]),
    ('Jewelry', 'jewelry', 'Beads, metals, handmade jewelry', 'necklace', []),
    ('Kids & Baby', 'kids-baby', 'Baby clothing, decor & accessories', 'grid', []),
    ('Paper & Party Supplies', 'paper-party', 'Cards, stationery, party & event decor', 'grid', []),
    ('Pet Supplies', 'pet-supplies', 'Collars, leashes, beds & pet accessories', 'grid', []),
    ('Shoes', 'shoes', 'Leather sandals, boots & handmade shoes', 'grid', []),
    ('Toys & Games', 'toys-games', 'Handmade toys, puzzles & games', 'grid', []),
    ('Vintage', 'vintage', 'Retro, antique, classic finds', 'clock', []),
    ('Weddings', 'wedding', 'Bridal wear, wedding decor & favors', 'gift', []),
]


class Command(BaseCommand):
    help = 'Seed default Kenyan marketplace categories (idempotent by slug).'

    def handle(self, *args, **options):
        created = 0
        for position, item in enumerate(SEED):
            name, slug, description, icon, children = item
            parent, was_created = Category.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'description': description,
                    'icon': icon,
                    'position': position,
                    'is_visible': True,
                },
            )
            if was_created:
                created += 1
            elif not parent.icon:
                parent.icon = icon
                parent.save(update_fields=['icon'])

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
