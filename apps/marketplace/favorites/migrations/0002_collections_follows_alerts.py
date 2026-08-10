import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('favorites', '0001_initial'), ('shops', '0006_seller_teams'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='ListingCollection', fields=[('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('name', models.CharField(max_length=80)), ('description', models.CharField(blank=True, max_length=240)), ('is_public', models.BooleanField(default=False)), ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)), ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='listing_collections', to=settings.AUTH_USER_MODEL))], options={'ordering': ['name']}),
        migrations.AddConstraint(model_name='listingcollection', constraint=models.UniqueConstraint(fields=('user', 'name'), name='uniq_user_collection_name')),
        migrations.CreateModel(name='CollectionItem', fields=[('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('added_at', models.DateTimeField(auto_now_add=True)), ('collection', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='favorites.listingcollection')), ('listing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='collection_items', to='listings.listing'))], options={'ordering': ['-added_at']}),
        migrations.AddConstraint(model_name='collectionitem', constraint=models.UniqueConstraint(fields=('collection', 'listing'), name='uniq_collection_listing')),
        migrations.CreateModel(name='ShopFollow', fields=[('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('alerts_enabled', models.BooleanField(default=True)), ('last_checked_at', models.DateTimeField(default=django.utils.timezone.now)), ('created_at', models.DateTimeField(auto_now_add=True)), ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='followers', to='shops.shop')), ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='followed_shops', to=settings.AUTH_USER_MODEL))], options={'ordering': ['-created_at']}),
        migrations.AddConstraint(model_name='shopfollow', constraint=models.UniqueConstraint(fields=('user', 'shop'), name='uniq_user_shop_follow')),
        migrations.CreateModel(name='ListingAlert', fields=[('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('price_change_enabled', models.BooleanField(default=True)), ('back_in_stock_enabled', models.BooleanField(default=True)), ('last_price', models.DecimalField(decimal_places=2, max_digits=12)), ('was_in_stock', models.BooleanField(default=False)), ('last_checked_at', models.DateTimeField(default=django.utils.timezone.now)), ('created_at', models.DateTimeField(auto_now_add=True)), ('listing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alerts', to='listings.listing')), ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='listing_alerts', to=settings.AUTH_USER_MODEL))], options={'ordering': ['-created_at']}),
        migrations.AddConstraint(model_name='listingalert', constraint=models.UniqueConstraint(fields=('user', 'listing'), name='uniq_user_listing_alert')),
    ]
