from django.db import migrations, models


def rename_existing_promo_copy(apps, schema_editor):
    HeroPromoCard = apps.get_model('content', 'HeroPromoCard')
    HeroPromoCard.objects.filter(title='Ziuza Picks').update(title='Ziuza Maridadis')
    HeroPromoCard.objects.filter(button_label='Explore Picks').update(button_label='Explore Maridadis')


def restore_existing_promo_copy(apps, schema_editor):
    HeroPromoCard = apps.get_model('content', 'HeroPromoCard')
    HeroPromoCard.objects.filter(title='Ziuza Maridadis').update(title='Ziuza Picks')
    HeroPromoCard.objects.filter(button_label='Explore Maridadis').update(button_label='Explore Picks')


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0002_heropromocard'),
    ]

    operations = [
        migrations.AlterField(
            model_name='heropromocard',
            name='title',
            field=models.CharField(default='Ziuza Maridadis', max_length=160, verbose_name='title'),
        ),
        migrations.AlterField(
            model_name='heropromocard',
            name='button_label',
            field=models.CharField(default='Explore Maridadis', max_length=80, verbose_name='button label'),
        ),
        migrations.RunPython(rename_existing_promo_copy, restore_existing_promo_copy),
    ]
