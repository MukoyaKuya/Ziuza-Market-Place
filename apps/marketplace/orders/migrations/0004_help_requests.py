import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('orders', '0003_order_reservation_lifecycle'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name='HelpRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('reason', models.CharField(choices=[('not_received', 'Item not received'), ('late', 'Delivery is late'), ('damaged', 'Item arrived damaged'), ('not_as_described', 'Item not as described'), ('wrong_item', 'Wrong item received'), ('other', 'Other problem')], max_length=32)),
                ('status', models.CharField(choices=[('open', 'Open'), ('seller_responded', 'Seller responded'), ('escalated', 'Escalated to Ziuza'), ('resolved', 'Resolved'), ('closed', 'Closed')], db_index=True, default='open', max_length=32)),
                ('description', models.TextField()),
                ('desired_resolution', models.CharField(blank=True, max_length=200)),
                ('seller_response', models.TextField(blank=True)),
                ('resolution_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('buyer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='help_requests', to=settings.AUTH_USER_MODEL)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='help_requests', to='orders.order')),
                ('seller_order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='help_requests', to='orders.sellerorder')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(model_name='helprequest', index=models.Index(fields=['seller_order', 'status'], name='orders_help_seller__65a8ac_idx')),
    ]
