import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('shops', '0003_shop_operational_policies'),
        ('listings', '0003_inventory_low_stock_alert'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(name='MarketplaceReport', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('reason', models.CharField(choices=[('prohibited', 'Prohibited or unsafe item'), ('counterfeit', 'Counterfeit or intellectual-property concern'), ('misleading', 'Misleading listing or shop'), ('fraud', 'Suspected fraud or scam'), ('harassment', 'Harassment or abusive conduct'), ('other', 'Other concern')], max_length=24)),
            ('details', models.TextField()), ('status', models.CharField(choices=[('open', 'Open'), ('reviewing', 'Under review'), ('actioned', 'Action taken'), ('dismissed', 'Dismissed')], db_index=True, default='open', max_length=20)),
            ('moderator_notes', models.TextField(blank=True)), ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
            ('listing', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='listings.listing')),
            ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='marketplace_reports', to=settings.AUTH_USER_MODEL)),
            ('shop', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='shops.shop')),
        ], options={'ordering': ['-created_at']}),
        migrations.CreateModel(name='VerificationApplication', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('legal_name', models.CharField(max_length=160)), ('identity_type', models.CharField(choices=[('national_id', 'Kenyan national ID'), ('passport', 'Passport'), ('business', 'Business registration')], max_length=24)),
            ('identity_last4', models.CharField(max_length=4)), ('business_registration_number', models.CharField(blank=True, max_length=80)), ('contact_phone', models.CharField(max_length=20)), ('consent_confirmed', models.BooleanField(default=False)),
            ('status', models.CharField(choices=[('pending', 'Pending review'), ('approved', 'Approved'), ('rejected', 'Rejected')], db_index=True, default='pending', max_length=20)),
            ('reviewer_notes', models.TextField(blank=True)), ('submitted_at', models.DateTimeField(auto_now_add=True)), ('reviewed_at', models.DateTimeField(blank=True, null=True)),
            ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_verification_applications', to=settings.AUTH_USER_MODEL)),
            ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='verification_applications', to='shops.shop')),
        ], options={'ordering': ['-submitted_at']}),
        migrations.CreateModel(name='ModerationAction', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('action', models.CharField(choices=[('verify_shop', 'Verify shop'), ('reject_verification', 'Reject verification'), ('suspend_shop', 'Suspend shop'), ('restore_shop', 'Restore shop'), ('hide_listing', 'Hide listing'), ('dismiss_report', 'Dismiss report')], max_length=32)),
            ('notes', models.TextField(blank=True)), ('created_at', models.DateTimeField(auto_now_add=True)),
            ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='moderation_actions', to=settings.AUTH_USER_MODEL)),
            ('listing', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='moderation_actions', to='listings.listing')),
            ('report', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='actions', to='shops.marketplacereport')),
            ('shop', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='moderation_actions', to='shops.shop')),
        ], options={'ordering': ['-created_at']}),
        migrations.AddConstraint(model_name='marketplacereport', constraint=models.CheckConstraint(condition=models.Q(models.Q(('listing__isnull', True), ('shop__isnull', False)), models.Q(('listing__isnull', False), ('shop__isnull', True)), _connector='OR'), name='report_exactly_one_target')),
    ]
