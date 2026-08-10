import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('shops', '0005_storefront_marketing'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='ShopMembership',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('role', models.CharField(choices=[('manager', 'Shop manager'), ('catalog', 'Catalogue manager'), ('orders', 'Order manager'), ('support', 'Customer support')], max_length=20)),
                ('status', models.CharField(choices=[('active', 'Active'), ('revoked', 'Revoked')], db_index=True, default='active', max_length=16)),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('invited_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_shop_memberships', to=settings.AUTH_USER_MODEL)),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='shops.shop')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shop_memberships', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['user__email']},
        ),
        migrations.AddConstraint(model_name='shopmembership', constraint=models.UniqueConstraint(fields=('shop', 'user'), name='uniq_shop_team_member')),
        migrations.CreateModel(
            name='ShopInvitation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(max_length=255)),
                ('role', models.CharField(choices=[('manager', 'Shop manager'), ('catalog', 'Catalogue manager'), ('orders', 'Order manager'), ('support', 'Customer support')], max_length=20)),
                ('token_digest', models.CharField(max_length=64, unique=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('accepted_at', models.DateTimeField(blank=True, null=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('accepted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='shop_invitations_accepted', to=settings.AUTH_USER_MODEL)),
                ('invited_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='shop_invitations_sent', to=settings.AUTH_USER_MODEL)),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='team_invitations', to='shops.shop')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='ShopAuditEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('action', models.CharField(db_index=True, max_length=80)),
                ('target_type', models.CharField(blank=True, max_length=40)),
                ('target_id', models.CharField(blank=True, max_length=64)),
                ('description', models.CharField(max_length=300)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='shop_audit_events', to=settings.AUTH_USER_MODEL)),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_events', to='shops.shop')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(model_name='shopauditevent', index=models.Index(fields=['shop', 'created_at'], name='shops_shopa_shop_id_4de0ca_idx')),
    ]
