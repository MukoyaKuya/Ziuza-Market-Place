from decimal import Decimal, ROUND_DOWN

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.marketplace.promotions.models import DiscountType, Promotion, PromotionRedemption, RedemptionStatus
from apps.marketplace.shops.permissions import MANAGE_PROMOTIONS, ensure_shop_permission


ACTIVE_REDEMPTIONS = [RedemptionStatus.RESERVED, RedemptionStatus.REDEEMED]


def _eligible_subtotal(*, promotion, lines):
    return sum((line['line_total'] for line in lines if line['item'].listing.shop_id == promotion.shop_id), Decimal('0.00'))


def calculate_discount(*, promotion, eligible_subtotal):
    if promotion.discount_type == DiscountType.PERCENTAGE:
        if promotion.value > 100:
            raise ValidationError('Percentage discount cannot exceed 100%.')
        discount = (eligible_subtotal * promotion.value / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    else:
        discount = promotion.value
    return min(discount, eligible_subtotal)


def validate_promotion(*, actor, code: str, lines, lock=False):
    now = timezone.now()
    queryset = Promotion.objects.select_for_update() if lock else Promotion.objects
    try:
        promotion = queryset.select_related('shop').get(code=code.strip().upper(), is_active=True)
    except Promotion.DoesNotExist as exc:
        raise ValidationError('Coupon code is invalid.') from exc
    if promotion.starts_at > now or promotion.ends_at <= now:
        raise ValidationError('Coupon code is not currently active.')
    eligible = _eligible_subtotal(promotion=promotion, lines=lines)
    if eligible <= 0:
        raise ValidationError('This coupon does not apply to items in your cart.')
    if eligible < promotion.minimum_spend:
        raise ValidationError(f'Spend at least KES {promotion.minimum_spend} at {promotion.shop.name} to use this coupon.')
    active = promotion.redemptions.filter(status__in=ACTIVE_REDEMPTIONS)
    if promotion.usage_limit is not None and active.count() >= promotion.usage_limit:
        raise ValidationError('This coupon has reached its usage limit.')
    if active.filter(user=actor).count() >= promotion.per_user_limit:
        raise ValidationError('You have already used this coupon.')
    return promotion, calculate_discount(promotion=promotion, eligible_subtotal=eligible)


def reserve_redemption(*, promotion, order, user, discount_amount):
    return PromotionRedemption.objects.create(promotion=promotion, order=order, user=user, discount_amount=discount_amount)


def update_redemption_status(*, order, status):
    PromotionRedemption.objects.filter(order=order, status=RedemptionStatus.RESERVED).update(status=status, updated_at=timezone.now())


def create_promotion(*, actor, shop, name, code, discount_type, value, minimum_spend, usage_limit, per_user_limit, starts_at, ends_at):
    ensure_shop_permission(actor=actor, shop=shop, permission=MANAGE_PROMOTIONS)
    if starts_at >= ends_at:
        raise ValidationError('Promotion end time must be after its start time.')
    if discount_type == DiscountType.PERCENTAGE and value > 100:
        raise ValidationError('Percentage discount cannot exceed 100%.')
    try:
        return Promotion.objects.create(
            shop=shop, name=name.strip(), code=code.strip().upper(), discount_type=discount_type,
            value=value, minimum_spend=minimum_spend, usage_limit=usage_limit,
            per_user_limit=max(1, per_user_limit), starts_at=starts_at, ends_at=ends_at,
        )
    except Exception as exc:
        raise ValidationError('Coupon code must be unique and all values must be valid.') from exc


def set_promotion_active(*, actor, promotion, active):
    ensure_shop_permission(actor=actor, shop=promotion.shop, permission=MANAGE_PROMOTIONS)
    promotion.is_active = bool(active)
    promotion.save(update_fields=['is_active', 'updated_at'])
    return promotion
