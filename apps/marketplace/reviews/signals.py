from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.marketplace.reviews.models import ReviewMedia


@receiver(post_delete, sender=ReviewMedia)
def delete_review_media_file(*, instance, **kwargs):
    if instance.image:
        instance.image.delete(save=False)
