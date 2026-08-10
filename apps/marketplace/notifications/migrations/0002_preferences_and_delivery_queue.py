import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('notifications', '0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='NotificationPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email_enabled', models.BooleanField(default=True)),
                ('digest_frequency', models.CharField(choices=[('immediate', 'Immediately'), ('daily', 'Daily digest'), ('weekly', 'Weekly digest'), ('never', 'Never email me')], default='immediate', max_length=16)),
                ('order_updates', models.BooleanField(default=True)),
                ('messages', models.BooleanField(default=True)),
                ('shipping_updates', models.BooleanField(default=True)),
                ('marketplace_updates', models.BooleanField(default=True)),
                ('saved_searches', models.BooleanField(default=True)),
                ('inventory_updates', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='notification_preference', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='NotificationDelivery',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('channel', models.CharField(default='email', max_length=16)),
                ('mode', models.CharField(choices=[('immediate', 'Immediately'), ('daily', 'Daily digest'), ('weekly', 'Weekly digest'), ('never', 'Never email me')], default='immediate', max_length=16)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('sent', 'Sent'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], db_index=True, default='pending', max_length=16)),
                ('available_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('last_error', models.CharField(blank=True, max_length=500)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('notification', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deliveries', to='notifications.notification')),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notification_deliveries', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['available_at', 'created_at']},
        ),
        migrations.AddConstraint(model_name='notificationdelivery', constraint=models.UniqueConstraint(fields=('notification', 'channel'), name='uniq_notification_delivery_channel')),
        migrations.AddIndex(model_name='notificationdelivery', index=models.Index(fields=['status', 'available_at'], name='notificatio_status_0ec174_idx')),
    ]
