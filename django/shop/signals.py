from __future__ import annotations

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Order, Channel


@receiver(post_save, sender=Order)
def order_post_save(sender, instance: Order, created: bool, **kwargs) -> None:
    if created:
        return
    if not instance.tracker.has_changed("status"):
        return

    payload = json.dumps(
        {"order_id": instance.id, "status": instance.status},
        cls=DjangoJSONEncoder,
    )
    with connection.cursor() as cursor:
        cursor.execute("NOTIFY order_status_changed, %s", [payload])


@receiver([post_save, post_delete], sender=Channel)
def channel_changed(sender, instance: Channel, **kwargs):
    """
    Отправляет NOTIFY при любом изменении каналов.
    Бот сбросит кэш при получении этого уведомления.
    """
    payload = json.dumps({"action": "refresh"})
    with connection.cursor() as cursor:
        cursor.execute("NOTIFY channel_changed, %s", [payload])