from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateDigitalStorage:
    """Purchased digital files are only served through authorized download views.

    Callable so FileField resolves it lazily: local deployments keep
    FileSystemStorage under PRIVATE_MEDIA_ROOT, while object storage
    (PRIVATE_MEDIA_STORAGE_BACKEND) lets multiple app servers share files.
    """

    def __call__(self):
        if settings.PRIVATE_MEDIA_STORAGE_BACKEND:
            from apps.marketplace.orders.storage import _object_storage

            return _object_storage(location='digital_assets')
        return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)


private_digital_storage = PrivateDigitalStorage()
