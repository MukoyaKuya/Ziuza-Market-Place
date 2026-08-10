import django.core.validators
import django.db.models.deletion
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [('orders', '0004_help_requests'), ('shops', '0004_trust_and_safety'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='Promotion', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('name', models.CharField(max_length=120)), ('code', models.CharField(db_index=True, max_length=32, unique=True)),
            ('discount_type', models.CharField(choices=[('percentage', 'Percentage'), ('fixed', 'Fixed amount')], max_length=16)),
            ('value', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))])),
            ('minimum_spend', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
            ('usage_limit', models.PositiveIntegerField(blank=True, null=True)), ('per_user_limit', models.PositiveIntegerField(default=1)),
            ('starts_at', models.DateTimeField()), ('ends_at', models.DateTimeField()), ('is_active', models.BooleanField(default=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
            ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='promotions', to='shops.shop')),
        ], options={'ordering': ['-created_at']}),
        migrations.CreateModel(name='PromotionRedemption', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('discount_amount', models.DecimalField(decimal_places=2, max_digits=12)),
            ('status', models.CharField(choices=[('reserved', 'Reserved'), ('redeemed', 'Redeemed'), ('released', 'Released')], db_index=True, default='reserved', max_length=16)),
            ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
            ('order', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='promotion_redemption', to='orders.order')),
            ('promotion', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='redemptions', to='promotions.promotion')),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='promotion_redemptions', to=settings.AUTH_USER_MODEL)),
        ]),
    ]
