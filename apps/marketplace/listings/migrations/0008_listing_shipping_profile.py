import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('listings', '0007_listing_seo'), ('shipping', '0003_shipping_profiles')]
    operations = [
        migrations.AddField(
            model_name='listing',
            name='shipping_profile',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='listings', to='shipping.shippingprofile'),
        ),
    ]
