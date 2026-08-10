import uuid

from django.conf import settings
from django.db import models


class ShopTeamRole(models.TextChoices):
    MANAGER = 'manager', 'Shop manager'
    CATALOG = 'catalog', 'Catalogue manager'
    ORDERS = 'orders', 'Order manager'
    SUPPORT = 'support', 'Customer support'


class ShopMembershipStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    REVOKED = 'revoked', 'Revoked'


class ShopMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shop_memberships')
    role = models.CharField(max_length=20, choices=ShopTeamRole.choices)
    status = models.CharField(max_length=16, choices=ShopMembershipStatus.choices, default=ShopMembershipStatus.ACTIVE, db_index=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='created_shop_memberships')
    joined_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['user__email']
        constraints = [models.UniqueConstraint(fields=['shop', 'user'], name='uniq_shop_team_member')]

    def __str__(self):
        return f'{self.user} · {self.shop} ({self.get_role_display()})'


class ShopInvitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='team_invitations')
    email = models.EmailField(max_length=255)
    role = models.CharField(max_length=20, choices=ShopTeamRole.choices)
    token_digest = models.CharField(max_length=64, unique=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='shop_invitations_sent')
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='shop_invitations_accepted')
    expires_at = models.DateTimeField(db_index=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_pending(self):
        from django.utils import timezone
        return not self.accepted_at and not self.revoked_at and self.expires_at > timezone.now()


class ShopAuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='audit_events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='shop_audit_events')
    action = models.CharField(max_length=80, db_index=True)
    target_type = models.CharField(max_length=40, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    description = models.CharField(max_length=300)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['shop', 'created_at'])]

    def __str__(self):
        return f'{self.shop}: {self.action}'
