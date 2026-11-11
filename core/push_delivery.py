import json
import uuid
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from .models import Notification, PushDelivery, PushSubscription


def deliver_push(limit=200, notification_ids=None):
    result={'sent':0,'failed':0,'disabled':not settings.WEB_PUSH_ENABLED}
    if result['disabled']:
        return result
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        result['disabled']=True
        return result
    cutoff=timezone.now()-timedelta(hours=24)
    subscriptions=PushSubscription.objects.select_related('user').all()
    if notification_ids is not None:
        subscriptions = subscriptions.filter(user_id__in=Notification.objects.filter(pk__in=notification_ids).values('user_id'))
    for subscription in subscriptions:
        notes=Notification.objects.filter(user=subscription.user,created__gte=cutoff).order_by('created','pk')
        if notification_ids is not None:
            notes = notes.filter(pk__in=notification_ids)
        for note in notes.iterator():
            if result['sent']+result['failed']>=limit:
                return result
            with transaction.atomic():
                delivery,created=PushDelivery.objects.get_or_create(notification=note,subscription=subscription)
                delivery = PushDelivery.objects.select_for_update().get(pk=delivery.pk)
                now = timezone.now()
                if (delivery.sent_at or (delivery.next_attempt_at and delivery.next_attempt_at > now)
                        or delivery.attempts >= 5 or (delivery.claim_expires_at and delivery.claim_expires_at > now)):
                    continue
                delivery.claim_token = uuid.uuid4().hex
                delivery.claim_expires_at = now + timedelta(minutes=2)
                delivery.attempts += 1
                delivery.save(update_fields=['claim_token', 'claim_expires_at', 'attempts'])
            payload={'title':'FoodLoop Zambia','body':note.message,'url':f'/listings/{note.listing_id}/' if note.listing_id else '/notifications/'}
            try:
                webpush(subscription_info={'endpoint':subscription.endpoint,'keys':{'p256dh':subscription.p256dh,'auth':subscription.auth}},data=json.dumps(payload),vapid_private_key=settings.WEB_PUSH_PRIVATE_KEY,vapid_claims={'sub':settings.WEB_PUSH_SUBJECT},ttl=86400,timeout=10)
            except WebPushException as exc:
                status=getattr(getattr(exc,'response',None),'status_code',None)
                if status in (404,410):
                    subscription.delete()
                    delivery.delete()
                    break
                delivery.last_error='Push delivery failed.'
                delivery.next_attempt_at=timezone.now()+timedelta(minutes=min(2**delivery.attempts,60))
                PushDelivery.objects.filter(pk=delivery.pk, claim_token=delivery.claim_token).update(
                    claim_token='', claim_expires_at=None, last_error=delivery.last_error, next_attempt_at=delivery.next_attempt_at)
                result['failed']+=1
            except Exception:
                delivery.last_error='Push delivery failed.'
                delivery.next_attempt_at=timezone.now()+timedelta(minutes=min(2**delivery.attempts,60))
                PushDelivery.objects.filter(pk=delivery.pk, claim_token=delivery.claim_token).update(
                    claim_token='', claim_expires_at=None, last_error=delivery.last_error, next_attempt_at=delivery.next_attempt_at)
                result['failed']+=1
            else:
                delivery.sent_at=timezone.now();delivery.last_error='';delivery.next_attempt_at=None
                PushDelivery.objects.filter(pk=delivery.pk, claim_token=delivery.claim_token).update(
                    claim_token='', claim_expires_at=None, sent_at=delivery.sent_at, last_error='', next_attempt_at=None)
                result['sent']+=1
    return result
