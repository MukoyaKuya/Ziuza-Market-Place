import uuid

from django.db import migrations, models


def seed_methods(apps, schema_editor):
    ShippingMethod = apps.get_model('shipping', 'ShippingMethod')
    ShippingMethod.objects.update_or_create(
        code='standard',
        defaults={'name': 'Standard delivery', 'base_fee': '300.00', 'estimated_days_min': 2, 'estimated_days_max': 5},
    )
    ShippingMethod.objects.update_or_create(
        code='pickup',
        defaults={'name': 'Local pickup', 'base_fee': '0.00', 'estimated_days_min': 1, 'estimated_days_max': 2, 'is_pickup': True},
    )


class Migration(migrations.Migration):
    dependencies = [('shipping', '0001_initial')]

    operations = [
        migrations.AddField(model_name='shippingmethod', name='counties', field=models.JSONField(blank=True, default=list, help_text='Empty means all counties.')),
        migrations.AddField(model_name='shippingmethod', name='estimated_days_max', field=models.PositiveSmallIntegerField(default=5)),
        migrations.AddField(model_name='shippingmethod', name='estimated_days_min', field=models.PositiveSmallIntegerField(default=1)),
        migrations.AddField(model_name='shippingmethod', name='is_pickup', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='shipment', name='delivered_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='shipment', name='estimated_delivery_date', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='shipment', name='shipped_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.CreateModel(
            name='ShipmentEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('status', models.CharField(choices=[('unfulfilled', 'Unfulfilled'), ('processing', 'Processing'), ('ready', 'Ready'), ('shipped', 'Shipped'), ('partially_shipped', 'Partially shipped'), ('delivered', 'Delivered'), ('cancelled', 'Cancelled')], max_length=32)),
                ('note', models.CharField(blank=True, max_length=300)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('shipment', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='events', to='shipping.shipment')),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.RunPython(seed_methods, migrations.RunPython.noop),
    ]
