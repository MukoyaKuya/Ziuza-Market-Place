from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('cart', '0002_cartitem_personalization_text'), ('listings', '0004_structured_variants_personalization')]
    operations = [
        migrations.AlterUniqueTogether(name='cartitem', unique_together=set()),
        migrations.AddField(model_name='cartitem', name='personalization_data', field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name='cartitem', name='personalization_signature', field=models.CharField(blank=True, default='', max_length=64)),
        migrations.AlterUniqueTogether(name='cartitem', unique_together={('cart', 'listing', 'variant', 'personalization_signature')}),
    ]
