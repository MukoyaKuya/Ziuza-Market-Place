from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Address
from apps.marketplace.cart.models import Cart
from apps.marketplace.cart.services import add_to_cart
from apps.marketplace.categories.models import Category
from apps.marketplace.listings.models import Listing, ListingStatus
from apps.marketplace.listings.services import create_listing, publish_listing
from apps.marketplace.orders.models import FulfillmentStatus
from apps.marketplace.orders.services import create_checkout_order, mark_order_paid
from apps.marketplace.shops.models import Shop, ShopVerificationStatus
from apps.marketplace.shops.services import create_shop

User = get_user_model()

DEMO_PASSWORD = "DemoPassword123!"
SELLER_EMAIL = "seller@demo.ziuza.co.ke"
BUYER_EMAIL = "buyer@demo.ziuza.co.ke"

LISTINGS = [
    {
        "title": "Handwoven Kikoy Wrap",
        "category": "fashion",
        "price": Decimal("1650.00"),
        "qty": 8,
        "short": "Coastal cotton wrap",
        "description": "Soft kikoy wrap woven on the Kenyan coast.",
        "sku": "DEMO-KIKOY-1",
        "featured": True,
    },
    {
        "title": "Sisal Market Kiondo",
        "category": "home-living",
        "price": Decimal("2800.00"),
        "qty": 5,
        "short": "Durable market basket",
        "description": "Handwoven sisal kiondo with leather handles.",
        "sku": "DEMO-KIONDO-1",
        "featured": True,
    },
    {
        "title": "Maasai Bead Necklace",
        "category": "jewelry",
        "price": Decimal("1200.00"),
        "qty": 12,
        "short": "Bright beadwork",
        "description": "Traditional bead necklace finished by artisans in Kajiado.",
        "sku": "DEMO-BEAD-1",
        "featured": False,
    },
    {
        "title": "Soapstone Elephant",
        "category": "art-collectibles",
        "price": Decimal("950.00"),
        "qty": 6,
        "short": "Kisii soapstone carving",
        "description": "Hand-carved soapstone elephant from Kisii.",
        "sku": "DEMO-STONE-1",
        "featured": True,
    },
]


class Command(BaseCommand):
    help = "Seed categories, CMS, shipping, and a walkable demo seller/buyer with listings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--with-order",
            action="store_true",
            help="Also create a paid sample order for the demo buyer.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("seed_categories")
        call_command("seed_homepage")
        call_command("seed_shipping")

        seller, _ = User.objects.get_or_create(
            email=SELLER_EMAIL,
            defaults={"display_name": "Demo Maker", "phone": "0711000001"},
        )
        seller.set_password(DEMO_PASSWORD)
        seller.email_verified = True
        seller.save()

        shop = Shop.objects.filter(owner=seller).first()
        if shop is None:
            shop = create_shop(
                actor=seller,
                name="Coastal Craft Collective",
                description="Handmade Kenyan goods for the demo walkthrough.",
                county="Mombasa",
                location_text="Old Town",
            )
        shop.verification_status = ShopVerificationStatus.VERIFIED
        shop.is_active = True
        shop.vacation_mode = False
        shop.save(update_fields=["verification_status", "is_active", "vacation_mode", "updated_at"])

        created_listings = 0
        for spec in LISTINGS:
            category = Category.objects.filter(slug=spec["category"]).first()
            if category is None:
                self.stdout.write(self.style.WARNING(f"Missing category {spec['category']}, skipping {spec['title']}"))
                continue
            listing = Listing.objects.filter(shop=shop, sku=spec["sku"]).first()
            if listing is None:
                listing = create_listing(
                    actor=seller,
                    shop=shop,
                    category=category,
                    title=spec["title"],
                    base_price=spec["price"],
                    short_description=spec["short"],
                    description=spec["description"],
                    sku=spec["sku"],
                    quantity_available=spec["qty"],
                )
                created_listings += 1
            if listing.status != ListingStatus.ACTIVE:
                publish_listing(actor=seller, listing=listing)
            if listing.is_featured != spec["featured"]:
                listing.is_featured = spec["featured"]
                listing.save(update_fields=["is_featured", "updated_at"])

        buyer, _ = User.objects.get_or_create(
            email=BUYER_EMAIL,
            defaults={"display_name": "Demo Buyer", "phone": "0711000002"},
        )
        buyer.set_password(DEMO_PASSWORD)
        buyer.email_verified = True
        buyer.save()

        address, _ = Address.objects.get_or_create(
            user=buyer,
            address_line_1="12 Ngong Road",
            defaults={
                "recipient_name": "Demo Buyer",
                "phone": "0711000002",
                "city_or_town": "Nairobi",
                "county": "Nairobi",
                "country": "Kenya",
                "is_default_shipping": True,
                "is_default_billing": True,
            },
        )

        order_note = ""
        if options["with_order"]:
            from django.contrib.sessions.backends.db import SessionStore
            from django.test import RequestFactory

            listing = Listing.objects.filter(shop=shop, status=ListingStatus.ACTIVE).first()
            if listing:
                rf = RequestFactory()
                req = rf.get("/")
                req.user = buyer
                req.session = SessionStore()
                req.session.create()
                Cart.objects.filter(user=buyer).delete()
                add_to_cart(request=req, listing=listing, quantity=1)
                cart = Cart.objects.get(user=buyer)
                order = create_checkout_order(
                    actor=buyer,
                    cart=cart,
                    shipping_address=address,
                    shipping_method_code="standard",
                    shipping_fee=Decimal("300.00"),
                )
                mark_order_paid(order=order)
                seller_order = order.seller_orders.get()
                seller_order.fulfillment_status = FulfillmentStatus.PROCESSING
                seller_order.save(update_fields=["fulfillment_status", "updated_at"])
                order_note = f"\nSample paid order: {order.public_number}"

        self.stdout.write(self.style.SUCCESS("Demo seed complete."))
        self.stdout.write(
            f"Seller: {SELLER_EMAIL} / {DEMO_PASSWORD}\n"
            f"Buyer:  {BUYER_EMAIL} / {DEMO_PASSWORD}\n"
            f"Shop:   /shop/{shop.slug}/\n"
            f"Listings created this run: {created_listings}"
            f"{order_note}"
        )
