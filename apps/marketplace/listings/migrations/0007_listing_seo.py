from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('listings', '0006_bulkoperation')]
    operations = [
        migrations.AddField(
            model_name='listing',
            name='seo_title',
            field=models.CharField(blank=True, help_text='Optional title for search engines and social sharing.', max_length=70, verbose_name='search title'),
        ),
        migrations.AddField(
            model_name='listing',
            name='seo_description',
            field=models.CharField(blank=True, help_text='Optional summary for search engines and social sharing.', max_length=160, verbose_name='search description'),
        ),
    ]
