from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0002_orderitem_personalization_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='reservation_expires_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='reservation_released_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
