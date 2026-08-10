from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('orders', '0005_order_promotion_code')]
    operations = [migrations.AddField(model_name='orderitem', name='personalization_data', field=models.JSONField(blank=True, default=dict))]
