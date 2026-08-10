import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('listings', '0005_digital_products'),
        ('shops', '0004_trust_and_safety'),
    ]

    operations = [
        migrations.CreateModel(
            name='BulkOperation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('operation', models.CharField(choices=[('catalog_import', 'Catalogue import'), ('catalog_export', 'Catalogue export')], max_length=24)),
                ('status', models.CharField(choices=[('validated', 'Validated'), ('completed', 'Completed'), ('failed', 'Failed')], max_length=16)),
                ('file_name', models.CharField(blank=True, max_length=255)),
                ('dry_run', models.BooleanField(default=False)),
                ('total_rows', models.PositiveIntegerField(default=0)),
                ('created_rows', models.PositiveIntegerField(default=0)),
                ('updated_rows', models.PositiveIntegerField(default=0)),
                ('error_count', models.PositiveIntegerField(default=0)),
                ('summary', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='listing_bulk_operations', to=settings.AUTH_USER_MODEL)),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bulk_operations', to='shops.shop')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='bulkoperation',
            index=models.Index(fields=['shop', 'created_at'], name='listings_bu_shop_id_f7432c_idx'),
        ),
    ]
