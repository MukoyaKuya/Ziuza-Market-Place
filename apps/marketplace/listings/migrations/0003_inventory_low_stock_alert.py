from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('listings', '0002_listing_county_of_origin_listing_is_personalizable_and_more')]
    operations = [migrations.AddField(model_name='inventory', name='low_stock_alert_sent', field=models.BooleanField(default=False))]
