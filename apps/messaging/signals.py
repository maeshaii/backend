import logging

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from apps.shared.models import User
from .user_updates_broadcaster import broadcast_user_update

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def handle_user_saved(sender, instance, created, **kwargs):
    try:
        action = 'created' if created else 'updated'
        broadcast_user_update(action, instance)
    except Exception as exc:
        logger.warning("Failed to broadcast user save event: %s", exc)


@receiver(post_delete, sender=User)
def handle_user_deleted(sender, instance, **kwargs):
    try:
        broadcast_user_update('deleted', instance)
    except Exception as exc:
        logger.warning("Failed to broadcast user delete event: %s", exc)

