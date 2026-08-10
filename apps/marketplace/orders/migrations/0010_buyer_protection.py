import apps.marketplace.orders.storage
import django.db.models.deletion
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('orders', '0009_order_shipping_breakdown'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name='helprequest', name='case_type', field=models.CharField(choices=[('support', 'Order support'), ('return', 'Return request'), ('exchange', 'Exchange request'), ('buyer_protection', 'Buyer protection case')], db_index=True, default='support', max_length=32)),
        migrations.AddField(model_name='helprequest', name='requested_outcome', field=models.CharField(blank=True, choices=[('replacement', 'Replacement'), ('return_refund', 'Return and refund'), ('exchange', 'Exchange'), ('partial_refund', 'Partial refund'), ('other', 'Other resolution')], max_length=32)),
        migrations.AddField(model_name='helprequest', name='resolution_outcome', field=models.CharField(blank=True, choices=[('buyer', 'Resolved for buyer'), ('seller', 'Resolved for seller'), ('agreement', 'Buyer and seller agreement'), ('no_action', 'Closed without action')], max_length=32)),
        migrations.AddField(model_name='helprequest', name='refund_recommendation', field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
        migrations.AddField(model_name='helprequest', name='moderator', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='moderated_protection_cases', to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name='helprequest', name='response_due_at', field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name='helprequest', name='first_seller_response_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='helprequest', name='escalated_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='helprequest', name='closed_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.CreateModel(name='ProtectionCaseMessage', fields=[('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('body', models.TextField()), ('is_internal', models.BooleanField(default=False)), ('created_at', models.DateTimeField(auto_now_add=True)), ('author', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='protection_case_messages', to=settings.AUTH_USER_MODEL)), ('case', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='orders.helprequest'))], options={'ordering': ['created_at']}),
        migrations.CreateModel(name='ProtectionCaseEvidence', fields=[('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('file', models.FileField(storage=apps.marketplace.orders.storage.CaseEvidenceStorage(), upload_to='%Y/%m/%d')), ('original_name', models.CharField(max_length=255)), ('content_type', models.CharField(max_length=100)), ('size', models.PositiveIntegerField()), ('description', models.CharField(blank=True, max_length=300)), ('created_at', models.DateTimeField(auto_now_add=True)), ('case', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evidence', to='orders.helprequest')), ('uploaded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='protection_case_evidence', to=settings.AUTH_USER_MODEL))], options={'ordering': ['created_at']}),
        migrations.CreateModel(name='ProtectionCaseEvent', fields=[('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('action', models.CharField(db_index=True, max_length=64)), ('note', models.CharField(blank=True, max_length=300)), ('is_internal', models.BooleanField(default=False)), ('metadata', models.JSONField(blank=True, default=dict)), ('created_at', models.DateTimeField(auto_now_add=True)), ('actor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='protection_case_events', to=settings.AUTH_USER_MODEL)), ('case', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='orders.helprequest'))], options={'ordering': ['created_at']}),
    ]
