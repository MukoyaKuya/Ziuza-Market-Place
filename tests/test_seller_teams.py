from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.marketplace.shops.models import (
    ShopAuditEvent, ShopMembership, ShopMembershipStatus, ShopTeamRole,
)
from apps.marketplace.shops.permissions import (
    MANAGE_LISTINGS, MANAGE_MESSAGES, MANAGE_ORDERS, MANAGE_SHIPPING,
    MANAGE_STOREFRONT, VIEW_ANALYTICS, VIEW_ORDERS, user_has_shop_permission,
)
from apps.marketplace.shops.services import create_shop
from apps.marketplace.shops.team_services import (
    accept_team_invitation, invite_team_member, revoke_team_member,
)


User = get_user_model()
PASSWORD = 'SecurePassword123!'


@pytest.fixture
def owner(db):
    return User.objects.create_user(email='owner@ziuza.co.ke', password=PASSWORD, display_name='Owner')


@pytest.fixture
def member(db):
    return User.objects.create_user(email='member@ziuza.co.ke', password=PASSWORD, display_name='Member')


@pytest.fixture
def stranger(db):
    return User.objects.create_user(email='stranger@ziuza.co.ke', password=PASSWORD, display_name='Stranger')


@pytest.fixture
def shop(owner):
    return create_shop(actor=owner, name='Team Craft Studio', description='Made together', county='Nairobi')


def add_member(*, shop, owner, member, role):
    return ShopMembership.objects.create(shop=shop, user=member, role=role, invited_by=owner)


@pytest.mark.django_db
def test_invitation_token_is_hashed_bound_to_email_and_single_use(owner, member, stranger, shop):
    invitation, token = invite_team_member(actor=owner, shop=shop, email=member.email, role=ShopTeamRole.CATALOG)
    assert invitation.token_digest != token
    assert len(invitation.token_digest) == 64
    assert member.notifications.filter(type='team_invitation', target_url__endswith=f'/{token}/').exists()

    with pytest.raises(ValidationError):
        accept_team_invitation(actor=stranger, token=token)
    assert invitation.accepted_at is None

    membership = accept_team_invitation(actor=member, token=token)
    invitation.refresh_from_db()
    assert membership.role == ShopTeamRole.CATALOG
    assert invitation.accepted_by == member
    assert invitation.accepted_at is not None
    with pytest.raises(ValidationError):
        accept_team_invitation(actor=member, token=token)


@pytest.mark.django_db
def test_expired_invitation_cannot_be_accepted(owner, member, shop):
    invitation, token = invite_team_member(actor=owner, shop=shop, email=member.email, role=ShopTeamRole.SUPPORT)
    invitation.expires_at = timezone.now() - timedelta(seconds=1)
    invitation.save(update_fields=['expires_at'])
    with pytest.raises(ValidationError):
        accept_team_invitation(actor=member, token=token)


@pytest.mark.django_db
def test_invitation_requires_existing_account_and_one_managed_shop(owner, member, stranger, shop):
    with pytest.raises(ValidationError, match='active Ziuza account'):
        invite_team_member(actor=owner, shop=shop, email='missing@ziuza.co.ke', role=ShopTeamRole.MANAGER)

    other_shop = create_shop(actor=stranger, name='Other Studio', county='Mombasa')
    add_member(shop=other_shop, owner=stranger, member=member, role=ShopTeamRole.SUPPORT)
    with pytest.raises(ValidationError, match='another shop'):
        invite_team_member(actor=owner, shop=shop, email=member.email, role=ShopTeamRole.MANAGER)


@pytest.mark.django_db
def test_role_permission_matrix(owner, member, shop):
    membership = add_member(shop=shop, owner=owner, member=member, role=ShopTeamRole.CATALOG)
    for permission in (MANAGE_LISTINGS, MANAGE_SHIPPING, MANAGE_STOREFRONT, VIEW_ANALYTICS):
        assert user_has_shop_permission(actor=member, shop=shop, permission=permission)
    for permission in (VIEW_ORDERS, MANAGE_ORDERS, MANAGE_MESSAGES):
        assert not user_has_shop_permission(actor=member, shop=shop, permission=permission)

    membership.role = ShopTeamRole.ORDERS
    membership.save(update_fields=['role'])
    assert user_has_shop_permission(actor=member, shop=shop, permission=VIEW_ORDERS)
    assert user_has_shop_permission(actor=member, shop=shop, permission=MANAGE_ORDERS)
    assert not user_has_shop_permission(actor=member, shop=shop, permission=MANAGE_LISTINGS)


@pytest.mark.django_db
def test_team_member_dashboard_respects_role_and_owner_only_controls(client, owner, member, shop):
    add_member(shop=shop, owner=owner, member=member, role=ShopTeamRole.SUPPORT)
    client.force_login(member)
    dashboard = client.get(reverse('shops:dashboard'))
    assert dashboard.status_code == 200
    navigation_keys = {item['key'] for item in dashboard.context['dashboard_nav']}
    assert {'orders', 'messages', 'team'} <= navigation_keys
    assert {'listings', 'shop', 'verification', 'shipping'}.isdisjoint(navigation_keys)
    assert client.get(reverse('shops:team')).status_code == 200
    assert client.get(reverse('orders:seller_list')).status_code == 200
    assert client.get(reverse('listings:seller_list')).status_code == 403
    assert client.get(reverse('shops:dashboard_shop')).status_code == 403
    assert client.get(reverse('shops:verification')).status_code == 403
    assert client.post(reverse('shops:team'), {'action': 'invite', 'email': 'nobody@example.com', 'role': ShopTeamRole.MANAGER}).status_code == 404


@pytest.mark.django_db
def test_revocation_removes_access_immediately(client, owner, member, shop):
    membership = add_member(shop=shop, owner=owner, member=member, role=ShopTeamRole.MANAGER)
    client.force_login(member)
    assert client.get(reverse('shops:dashboard')).status_code == 200
    revoke_team_member(actor=owner, shop=shop, membership=membership)
    membership.refresh_from_db()
    assert membership.status == ShopMembershipStatus.REVOKED
    response = client.get(reverse('shops:dashboard'))
    assert response.status_code == 302
    assert response.url == reverse('shops:onboarding')


@pytest.mark.django_db
def test_owner_team_page_shows_activity_and_hides_it_from_members(client, owner, member, shop):
    add_member(shop=shop, owner=owner, member=member, role=ShopTeamRole.MANAGER)
    ShopAuditEvent.objects.create(shop=shop, actor=member, action='listing.updated', description='Updated a private draft.')

    client.force_login(owner)
    owner_page = client.get(reverse('shops:team'))
    assert owner_page.status_code == 200
    assert b'Updated a private draft.' in owner_page.content

    client.force_login(member)
    member_page = client.get(reverse('shops:team'))
    assert member_page.status_code == 200
    assert b'Updated a private draft.' not in member_page.content


@pytest.mark.django_db
def test_team_acceptance_view_confirms_then_joins(client, owner, member, shop):
    _, token = invite_team_member(actor=owner, shop=shop, email=member.email, role=ShopTeamRole.ORDERS)
    client.force_login(member)
    url = reverse('shops:accept_team', kwargs={'token': token})
    assert client.get(url).status_code == 200
    response = client.post(url)
    assert response.status_code == 302
    assert response.url == reverse('shops:dashboard')
    assert ShopMembership.objects.filter(shop=shop, user=member, status=ShopMembershipStatus.ACTIVE).exists()
