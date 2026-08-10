import apps.marketplace.listings.storage
import django.db.models.deletion
import uuid
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('listings', '0004_structured_variants_personalization')]
    operations = [
        migrations.AddField(model_name='listing', name='product_type', field=models.CharField(choices=[('physical', 'Physical item'), ('digital', 'Digital download'), ('made_to_order', 'Made to order')], db_index=True, default='physical', max_length=20)),
        migrations.CreateModel(name='DigitalAsset', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('title', models.CharField(max_length=160)),
            ('file', models.FileField(storage=apps.marketplace.listings.storage.private_digital_storage, upload_to='digital_assets/%Y/%m/')),
            ('version', models.CharField(blank=True, max_length=40)), ('is_active', models.BooleanField(default=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('listing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='digital_assets', to='listings.listing')),
        ], options={'ordering': ['title']}),
    ]
