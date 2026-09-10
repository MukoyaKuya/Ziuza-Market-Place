from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.marketplace.orders'
    label = 'orders'

    def ready(self):
        from apps.marketplace.orders import signals  # noqa: F401
