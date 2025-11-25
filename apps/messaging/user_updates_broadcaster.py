import logging
from typing import Literal, Dict, Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

logger = logging.getLogger(__name__)

UserAction = Literal['created', 'updated', 'deleted']


def serialize_user(instance) -> Dict[str, Any]:
    """
    Serialize a subset of user fields that are useful for the admin UI.
    This keeps the payload lightweight while still allowing optimistic UI updates.
    """
    account_type = getattr(instance, 'account_type', None)
    return {
        'user_id': getattr(instance, 'user_id', None),
        'ctu_id': getattr(instance, 'ctu_id', None),
        'full_name': getattr(instance, 'full_name', '')
        or f"{getattr(instance, 'f_name', '')} {getattr(instance, 'l_name', '')}".strip(),
        'email': getattr(instance, 'email', None),
        'user_status': getattr(instance, 'user_status', 'active'),
        'account_type': {
            'admin': bool(getattr(account_type, 'admin', False)),
            'peso': bool(getattr(account_type, 'peso', False)),
            'coordinator': bool(getattr(account_type, 'coordinator', False)),
            'ojt': bool(getattr(account_type, 'ojt', False)),
            'user': bool(getattr(account_type, 'user', False)),
        } if account_type else None,
    }


def broadcast_user_update(action: UserAction, instance):
    """
    Broadcast a user update to all connected admin clients.
    """
    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.warning("Channel layer unavailable; skipping user management broadcast")
        return

    try:
        payload = {
            'action': action,
            'user': serialize_user(instance),
            'timestamp': timezone.now().isoformat(),
        }

        async_to_sync(channel_layer.group_send)(
            'user_management_updates',
            {
                'type': 'user_management_update',
                'payload': payload,
            }
        )
        logger.info(
            "Broadcasted user management update: action=%s user_id=%s",
            action,
            payload['user']['user_id'],
        )
    except Exception as exc:
        logger.error("Failed to broadcast user management update: %s", exc)

