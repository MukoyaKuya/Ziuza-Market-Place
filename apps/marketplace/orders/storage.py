from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class CaseEvidenceStorage:
    """Private case files are only served through an authorized download view.

    Callable so FileField resolves it lazily: local deployments keep
    FileSystemStorage under PRIVATE_MEDIA_ROOT, while object storage
    (PRIVATE_MEDIA_STORAGE_BACKEND) lets multiple app servers share files.
    Deconstructs with no arguments so migrations stay environment-stable.
    """

    def __call__(self):
        if settings.PRIVATE_MEDIA_STORAGE_BACKEND:
            return _object_storage(location='case_evidence')
        return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT / 'case_evidence', base_url=None)


def _object_storage(*, location: str):
    try:
        from storages.backends.s3 import S3Storage
    except ImportError as exc:
        raise ImproperlyConfigured(
            'PRIVATE_MEDIA_STORAGE_BACKEND requires the [prod] extra django-storages[s3].'
        ) from exc
    options = dict(settings.PRIVATE_MEDIA_STORAGE_OPTIONS)
    prefix = options.pop('location', '')
    options['location'] = '/'.join(part for part in (prefix, location) if part).strip('/')
    return S3Storage(**options)
