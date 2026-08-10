import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Address(models.Model):
    """User Address model for shipping and billing in Kenya and internationally."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='addresses'
    )
    recipient_name = models.CharField(_('recipient name'), max_length=100)
    phone = models.CharField(_('phone number'), max_length=20)
    address_line_1 = models.CharField(_('address line 1'), max_length=255)
    address_line_2 = models.CharField(_('address line 2'), max_length=255, blank=True)
    city_or_town = models.CharField(_('city or town'), max_length=100)
    county = models.CharField(_('county'), max_length=100, default='Nairobi')
    sub_county = models.CharField(_('sub county'), max_length=100, blank=True)
    ward = models.CharField(_('ward'), max_length=100, blank=True)
    village = models.CharField(_('village / landmark'), max_length=150, blank=True)
    postal_code = models.CharField(_('postal code'), max_length=20, blank=True)
    country = models.CharField(_('country'), max_length=100, default='Kenya')

    is_default_shipping = models.BooleanField(_('default shipping address'), default=False)
    is_default_billing = models.BooleanField(_('default billing address'), default=False)

    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('address')
        verbose_name_plural = _('addresses')
        ordering = ['-is_default_shipping', '-created_at']

    def __str__(self):
        return f"{self.recipient_name} - {self.address_line_1}, {self.city_or_town}"
