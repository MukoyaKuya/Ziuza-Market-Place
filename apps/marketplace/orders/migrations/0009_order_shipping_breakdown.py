from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('orders', '0008_digital_download_grants'), ('listings', '0008_listing_shipping_profile')]
    operations = [
        migrations.AddField(model_name='order', name='shipping_breakdown', field=models.JSONField(blank=True, default=list)),
    ]
