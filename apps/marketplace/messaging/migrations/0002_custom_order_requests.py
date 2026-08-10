import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('messaging', '0001_initial'), ('listings', '0005_digital_products'), ('shops', '0004_trust_and_safety'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name='CustomOrderRequest', fields=[
        ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
        ('description', models.TextField()), ('budget', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
        ('needed_by', models.DateField(blank=True, null=True)),
        ('status', models.CharField(choices=[('open', 'Open'), ('discussing', 'Discussing'), ('accepted', 'Accepted'), ('declined', 'Declined'), ('closed', 'Closed')], db_index=True, default='open', max_length=20)),
        ('seller_response', models.TextField(blank=True)), ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
        ('buyer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='custom_order_requests', to=settings.AUTH_USER_MODEL)),
        ('listing', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='custom_order_requests', to='listings.listing')),
        ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='custom_order_requests', to='shops.shop')),
    ], options={'ordering': ['-created_at']})]
