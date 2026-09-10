from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.marketplace.orders.models import ProtectionCaseEvidence


@receiver(post_delete, sender=ProtectionCaseEvidence)
def delete_case_evidence_file(*, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)
