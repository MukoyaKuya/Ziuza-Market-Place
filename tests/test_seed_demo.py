import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.marketplace.listings.models import Listing, ListingStatus
from apps.marketplace.orders.models import Order, PaymentStatus
from apps.marketplace.shops.models import Shop

User = get_user_model()


@pytest.mark.django_db
def test_seed_demo_creates_walkable_accounts():
    call_command('seed_demo', with_order=True)
    seller = User.objects.get(email='seller@demo.ziuza.co.ke')
    buyer = User.objects.get(email='buyer@demo.ziuza.co.ke')
    assert seller.check_password('DemoPassword123!')
    assert buyer.check_password('DemoPassword123!')
    assert Shop.objects.filter(owner=seller).exists()
    assert Listing.objects.filter(shop__owner=seller, status=ListingStatus.ACTIVE).count() >= 4
    assert Order.objects.filter(buyer=buyer, payment_status=PaymentStatus.PAID).exists()

    # Idempotent
    call_command('seed_demo')
    assert User.objects.filter(email='seller@demo.ziuza.co.ke').count() == 1
