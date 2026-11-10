"""Attempt external notification delivery after its database transaction commits."""
from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Notification


def deliver_notification(notification_id):
    if settings.EMAIL_NOTIFICATIONS_ENABLED:
        from .email_delivery import deliver_pending
        deliver_pending(limit=1, notification_ids=[notification_id])
    if settings.WEB_PUSH_ENABLED:
        from .push_delivery import deliver_push
        deliver_push(notification_ids=[notification_id])


@receiver(post_save, sender=Notification, dispatch_uid='foodloop.deliver_notification')
def notification_created(sender, instance, created, raw=False, **kwargs):
    if created and not raw and (settings.EMAIL_NOTIFICATIONS_ENABLED or settings.WEB_PUSH_ENABLED):
        transaction.on_commit(lambda: deliver_notification(instance.pk), robust=True)
