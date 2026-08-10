from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('orders', '0006_orderitem_personalization_data')]
    operations = [migrations.AddField(model_name='orderitem', name='variant_snapshot', field=models.JSONField(blank=True, default=dict))]
