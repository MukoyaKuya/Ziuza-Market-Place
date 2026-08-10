from django.core.exceptions import ValidationError
from django.db import transaction

from apps.marketplace.shops.models import ShopSection, ShopSectionItem
from apps.marketplace.shops.permissions import MANAGE_STOREFRONT, ensure_shop_permission


@transaction.atomic
def update_shop_marketing(*, actor, shop, **fields):
    ensure_shop_permission(actor=actor, shop=shop, permission=MANAGE_STOREFRONT)
    allowed = {'announcement', 'logo', 'banner', 'seo_title', 'seo_description'}
    for key, value in fields.items():
        if key in allowed:
            setattr(shop, key, value)
    shop.save()
    from apps.marketplace.shops.team_services import audit_shop_action
    audit_shop_action(shop=shop, actor=actor, action='storefront.updated', target=shop, description='Updated storefront marketing settings.')
    return shop


@transaction.atomic
def save_shop_section(*, actor, shop, name, listings, position=0, is_visible=True, section=None):
    ensure_shop_permission(actor=actor, shop=shop, permission=MANAGE_STOREFRONT)
    if section is not None and section.shop_id != shop.id:
        raise ValidationError('Section does not belong to this shop.')
    if section is None and shop.sections.count() >= 12:
        raise ValidationError('A shop can have up to 12 sections.')
    listings = list(listings)
    if any(listing.shop_id != shop.id for listing in listings):
        raise ValidationError('Every section listing must belong to this shop.')
    if section is None:
        section = ShopSection(shop=shop)
    section.name = (name or '').strip()
    if not section.name:
        raise ValidationError('Section name is required.')
    section.position = max(0, int(position))
    section.is_visible = bool(is_visible)
    section.save()
    section.items.all().delete()
    ShopSectionItem.objects.bulk_create([
        ShopSectionItem(section=section, listing=listing, position=index)
        for index, listing in enumerate(listings)
    ])
    from apps.marketplace.shops.team_services import audit_shop_action
    audit_shop_action(shop=shop, actor=actor, action='storefront.section_saved', target=section, description=f'Saved storefront section “{section.name}”.')
    return section


@transaction.atomic
def delete_shop_section(*, actor, shop, section):
    ensure_shop_permission(actor=actor, shop=shop, permission=MANAGE_STOREFRONT)
    if section.shop_id != shop.id:
        raise ValidationError('Section does not belong to this shop.')
    name = section.name
    section.delete()
    from apps.marketplace.shops.team_services import audit_shop_action
    audit_shop_action(shop=shop, actor=actor, action='storefront.section_deleted', description=f'Deleted storefront section “{name}”.')
