import django.db.models.deletion
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('listings', '0003_inventory_low_stock_alert')]
    operations = [
        migrations.CreateModel(name='ListingOption', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('name', models.CharField(max_length=80)), ('position', models.PositiveSmallIntegerField(default=0)),
            ('listing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='option_groups', to='listings.listing')),
        ], options={'ordering': ['position', 'name'], 'unique_together': {('listing', 'name')}}),
        migrations.CreateModel(name='ListingOptionValue', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('value', models.CharField(max_length=80)), ('position', models.PositiveSmallIntegerField(default=0)),
            ('option', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='values', to='listings.listingoption')),
        ], options={'ordering': ['position', 'value'], 'unique_together': {('option', 'value')}}),
        migrations.CreateModel(name='PersonalizationField', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('label', models.CharField(max_length=120)), ('instructions', models.CharField(blank=True, max_length=300)),
            ('field_type', models.CharField(choices=[('text', 'Text'), ('select', 'Choice list')], default='text', max_length=12)),
            ('options', models.JSONField(blank=True, default=list)), ('is_required', models.BooleanField(default=False)),
            ('max_length', models.PositiveSmallIntegerField(default=120)), ('position', models.PositiveSmallIntegerField(default=0)),
            ('listing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='personalization_fields', to='listings.listing')),
        ], options={'ordering': ['position', 'label'], 'unique_together': {('listing', 'label')}}),
        migrations.AddField(model_name='listingvariant', name='cover_image', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='variants', to='listings.listingimage')),
        migrations.AddField(model_name='listingvariant', name='option_summary', field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name='listingvariant', name='selected_values', field=models.ManyToManyField(blank=True, related_name='variants', to='listings.listingoptionvalue')),
    ]
