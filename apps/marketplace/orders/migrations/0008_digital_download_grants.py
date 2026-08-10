import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('orders', '0007_orderitem_variant_snapshot'), ('listings', '0005_digital_products'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name='orderitem', name='product_type_snapshot', field=models.CharField(default='physical', max_length=20)),
        migrations.CreateModel(name='DownloadGrant', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('granted_at', models.DateTimeField(auto_now_add=True)), ('download_count', models.PositiveIntegerField(default=0)),
            ('last_downloaded_at', models.DateTimeField(blank=True, null=True)), ('is_active', models.BooleanField(default=True)),
            ('buyer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='download_grants', to=settings.AUTH_USER_MODEL)),
            ('order_item', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='download_grant', to='orders.orderitem')),
        ]),
    ]
