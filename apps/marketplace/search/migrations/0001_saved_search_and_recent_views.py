import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('listings', '0006_bulkoperation'),
    ]
    operations = [
        migrations.CreateModel(
            name='SavedSearch',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=120)),
                ('query', models.CharField(blank=True, max_length=100)),
                ('filters', models.JSONField(blank=True, default=dict)),
                ('fingerprint', models.CharField(max_length=64)),
                ('alerts_enabled', models.BooleanField(default=True)),
                ('last_checked_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_notified_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='saved_searches', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-updated_at']},
        ),
        migrations.AddConstraint(
            model_name='savedsearch',
            constraint=models.UniqueConstraint(fields=('user', 'fingerprint'), name='uniq_user_saved_search'),
        ),
        migrations.CreateModel(
            name='RecentlyViewedListing',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('view_count', models.PositiveIntegerField(default=1)),
                ('last_viewed_at', models.DateTimeField(auto_now=True)),
                ('listing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recent_views', to='listings.listing')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recently_viewed_listings', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-last_viewed_at']},
        ),
        migrations.AddConstraint(
            model_name='recentlyviewedlisting',
            constraint=models.UniqueConstraint(fields=('user', 'listing'), name='uniq_user_recent_listing'),
        ),
        migrations.AddIndex(
            model_name='recentlyviewedlisting',
            index=models.Index(fields=['user', 'last_viewed_at'], name='search_rece_user_id_d9f9de_idx'),
        ),
    ]
