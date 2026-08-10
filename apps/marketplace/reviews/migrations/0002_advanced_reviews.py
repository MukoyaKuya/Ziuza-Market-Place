import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('reviews', '0001_initial'), ('orders', '0010_buyer_protection'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name='review', name='quality_rating', field=models.PositiveSmallIntegerField(default=5)),
        migrations.AddField(model_name='review', name='shipping_rating', field=models.PositiveSmallIntegerField(default=5)),
        migrations.AddField(model_name='review', name='service_rating', field=models.PositiveSmallIntegerField(default=5)),
        migrations.AddField(model_name='review', name='is_verified_purchase', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='review', name='moderation_status', field=models.CharField(choices=[('published', 'Published'), ('reported', 'Reported'), ('hidden', 'Hidden')], db_index=True, default='published', max_length=20)),
        migrations.AddField(model_name='review', name='seller_response', field=models.TextField(blank=True)),
        migrations.AddField(model_name='review', name='seller_responded_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='review', name='seller_responded_by', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='review_responses', to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name='review', name='helpful_count', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='review', name='edited_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.CreateModel(name='ReviewMedia', fields=[('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('image', models.ImageField(upload_to='reviews/%Y/%m/%d')), ('original_name', models.CharField(max_length=255)), ('content_type', models.CharField(max_length=80)), ('size', models.PositiveIntegerField()), ('created_at', models.DateTimeField(auto_now_add=True)), ('review', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='media', to='reviews.review'))], options={'ordering': ['created_at']}),
        migrations.CreateModel(name='ReviewHelpfulVote', fields=[('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('created_at', models.DateTimeField(auto_now_add=True)), ('review', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='helpful_votes', to='reviews.review')), ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='review_helpful_votes', to=settings.AUTH_USER_MODEL))]),
        migrations.AddConstraint(model_name='reviewhelpfulvote', constraint=models.UniqueConstraint(fields=('review', 'user'), name='uniq_review_helpful_user')),
        migrations.CreateModel(name='ReviewReport', fields=[('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('reason', models.CharField(choices=[('spam', 'Spam or advertising'), ('abuse', 'Abusive or hateful content'), ('privacy', 'Personal or private information'), ('irrelevant', 'Not about this purchase'), ('manipulation', 'Suspicious or manipulated review'), ('other', 'Other concern')], max_length=24)), ('details', models.TextField(blank=True)), ('status', models.CharField(choices=[('open', 'Open'), ('dismissed', 'Dismissed'), ('actioned', 'Actioned')], db_index=True, default='open', max_length=20)), ('moderator_notes', models.TextField(blank=True)), ('created_at', models.DateTimeField(auto_now_add=True)), ('reviewed_at', models.DateTimeField(blank=True, null=True)), ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='review_reports', to=settings.AUTH_USER_MODEL)), ('review', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='reviews.review')), ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='moderated_review_reports', to=settings.AUTH_USER_MODEL))], options={'ordering': ['-created_at']}),
        migrations.AddConstraint(model_name='reviewreport', constraint=models.UniqueConstraint(fields=('review', 'reporter'), name='uniq_review_reporter')),
        migrations.CreateModel(name='ReviewReminder', fields=[('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('sent_at', models.DateTimeField(auto_now_add=True)), ('order_item', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='review_reminder', to='orders.orderitem'))]),
    ]
