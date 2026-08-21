import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class DiscountType(models.TextChoices):
    PERCENTAGE = 'percentage', 'Percentage'
    FIXED = 'fixed', 'Fixed amount'


class Promotion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='promotions')
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=32, unique=True, db_index=True)
    discount_type = models.CharField(max_length=16, choices=DiscountType.choices)
    value = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    minimum_spend = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    per_user_limit = models.PositiveIntegerField(default=1)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)


class RedemptionStatus(models.TextChoices):
    RESERVED = 'reserved', 'Reserved'
    REDEEMED = 'redeemed', 'Redeemed'
    RELEASED = 'released', 'Released'


class PromotionRedemption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promotion = models.ForeignKey(Promotion, on_delete=models.PROTECT, related_name='redemptions')
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='promotion_redemption')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='promotion_redemptions')
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=16, choices=RedemptionStatus.choices, default=RedemptionStatus.RESERVED, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
