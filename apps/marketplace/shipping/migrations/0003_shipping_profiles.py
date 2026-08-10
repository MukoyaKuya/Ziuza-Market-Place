import django.db.models.deletion
import django.core.validators
import uuid
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('shipping', '0002_shipping_logistics'), ('shops', '0005_storefront_marketing')]
    operations = [
        migrations.CreateModel(
            name='ShippingProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=120)),
                ('base_fee', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('additional_item_fee', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('free_shipping_threshold', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('processing_days_min', models.PositiveSmallIntegerField(default=1)),
                ('processing_days_max', models.PositiveSmallIntegerField(default=3)),
                ('delivery_days_min', models.PositiveSmallIntegerField(default=1)),
                ('delivery_days_max', models.PositiveSmallIntegerField(default=5)),
                ('counties', models.JSONField(blank=True, default=list, help_text='Empty means delivery to all counties.')),
                ('offers_delivery', models.BooleanField(default=True)),
                ('allows_local_pickup', models.BooleanField(default=False)),
                ('pickup_fee', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('pickup_instructions', models.CharField(blank=True, max_length=300)),
                ('is_default', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shipping_profiles', to='shops.shop')),
            ],
            options={'ordering': ['name']},
        ),
        migrations.AddConstraint(model_name='shippingprofile', constraint=models.UniqueConstraint(fields=('shop', 'name'), name='uniq_shop_shipping_profile_name')),
        migrations.AddConstraint(model_name='shippingprofile', constraint=models.UniqueConstraint(condition=models.Q(('is_default', True)), fields=('shop',), name='uniq_default_shipping_profile_per_shop')),
    ]
