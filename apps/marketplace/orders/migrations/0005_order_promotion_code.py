from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('orders', '0004_help_requests')]
    operations = [migrations.AddField(model_name='order', name='promotion_code', field=models.CharField(blank=True, max_length=32))]
