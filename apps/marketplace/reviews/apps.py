from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.marketplace.reviews'
    label = 'reviews'

    def ready(self):
        from apps.marketplace.reviews import signals  # noqa: F401
