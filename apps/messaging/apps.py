import logging
from django.apps import AppConfig


class MessagingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.messaging'

    def ready(self):
        try:
            import apps.messaging.signals  # noqa: F401
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Failed to import messaging signals: %s", exc
            )
