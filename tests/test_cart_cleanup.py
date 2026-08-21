from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import User
from apps.marketplace.cart.models import Cart
from apps.marketplace.cart.services import purge_inactive_anonymous_carts


@pytest.mark.django_db
def test_purge_inactive_anonymous_carts():
    now = timezone.now()
    user = User.objects.create_user(email='user-cart@ziuza.co.ke', password='Password123!')

    # Active anonymous cart (recent)
    recent_anon = Cart.objects.create(session_key='recent-session')

    # Stale anonymous cart (old)
    stale_anon = Cart.objects.create(session_key='stale-session')
    Cart.objects.filter(pk=stale_anon.pk).update(updated_at=now - timedelta(days=45))

    # User cart (even if old, should never be purged by anon cleanup)
    user_cart = Cart.objects.create(user=user)
    Cart.objects.filter(pk=user_cart.pk).update(updated_at=now - timedelta(days=60))

    deleted = purge_inactive_anonymous_carts(days=30)
    assert deleted == 1
    assert not Cart.objects.filter(pk=stale_anon.pk).exists()
    assert Cart.objects.filter(pk=recent_anon.pk).exists()
    assert Cart.objects.filter(pk=user_cart.pk).exists()


@pytest.mark.django_db
def test_purge_inactive_carts_management_command():
    now = timezone.now()
    stale_anon = Cart.objects.create(session_key='stale-cmd-session')
    Cart.objects.filter(pk=stale_anon.pk).update(updated_at=now - timedelta(days=40))

    call_command('purge_inactive_carts', days=30)
    assert not Cart.objects.filter(pk=stale_anon.pk).exists()
