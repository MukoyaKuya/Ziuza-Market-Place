from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class CaseEvidenceStorage(FileSystemStorage):
    """Private case files are only served through an authorized download view."""

    def __init__(self):
        super().__init__(location=settings.PRIVATE_MEDIA_ROOT / 'case_evidence', base_url=None)
