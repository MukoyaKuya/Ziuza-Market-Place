from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('shops', '0002_shop_sub_county_shop_village_shop_ward')]
    operations = [
        migrations.AddField(model_name='shop', name='processing_days_max', field=models.PositiveSmallIntegerField(default=3, verbose_name='maximum processing days')),
        migrations.AddField(model_name='shop', name='processing_days_min', field=models.PositiveSmallIntegerField(default=1, verbose_name='minimum processing days')),
        migrations.AddField(model_name='shop', name='return_policy', field=models.TextField(blank=True, verbose_name='returns and exchanges policy')),
        migrations.AddField(model_name='shop', name='shipping_policy', field=models.TextField(blank=True, verbose_name='shipping policy')),
    ]
