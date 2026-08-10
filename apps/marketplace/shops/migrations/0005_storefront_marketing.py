import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('shops', '0004_trust_and_safety'),
        ('listings', '0007_listing_seo'),
    ]
    operations = [
        migrations.AddField(model_name='shop', name='announcement', field=models.CharField(blank=True, max_length=300, verbose_name='shop announcement')),
        migrations.AddField(model_name='shop', name='seo_description', field=models.CharField(blank=True, max_length=160, verbose_name='search description')),
        migrations.AddField(model_name='shop', name='seo_title', field=models.CharField(blank=True, max_length=70, verbose_name='search title')),
        migrations.CreateModel(
            name='ShopSection',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=80)),
                ('slug', models.SlugField(max_length=90)),
                ('position', models.PositiveSmallIntegerField(default=0)),
                ('is_visible', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='shops.shop')),
            ],
            options={'ordering': ['position', 'name']},
        ),
        migrations.AddConstraint(model_name='shopsection', constraint=models.UniqueConstraint(fields=('shop', 'slug'), name='uniq_shop_section_slug')),
        migrations.CreateModel(
            name='ShopSectionItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('position', models.PositiveSmallIntegerField(default=0)),
                ('listing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='section_items', to='listings.listing')),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='shops.shopsection')),
            ],
            options={'ordering': ['position', 'listing__title']},
        ),
        migrations.AddConstraint(model_name='shopsectionitem', constraint=models.UniqueConstraint(fields=('section', 'listing'), name='uniq_section_listing')),
        migrations.AddField(
            model_name='shopsection',
            name='listings',
            field=models.ManyToManyField(related_name='shop_sections', through='shops.ShopSectionItem', to='listings.listing'),
        ),
    ]
