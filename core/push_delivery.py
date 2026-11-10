import json
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
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
    for subscription in subscriptions:
        notes=Notification.objects.filter(user=subscription.user,created__gte=cutoff).order_by('created','pk')
        if notification_ids is not None:
            notes = notes.filter(pk__in=notification_ids)
        for note in notes.iterator():
            if result['sent']+result['failed']>=limit:
                return result
            delivery,created=PushDelivery.objects.get_or_create(notification=note,subscription=subscription)
            if delivery.sent_at or (delivery.next_attempt_at and delivery.next_attempt_at>timezone.now()) or delivery.attempts>=5:
                continue
            payload={'title':'FoodLoop Zambia','body':note.message,'url':f'/listings/{note.listing_id}/' if note.listing_id else '/notifications/'}
            delivery.attempts+=1
            try:
                webpush(subscription_info={'endpoint':subscription.endpoint,'keys':{'p256dh':subscription.p256dh,'auth':subscription.auth}},data=json.dumps(payload),vapid_private_key=settings.WEB_PUSH_PRIVATE_KEY,vapid_claims={'sub':settings.WEB_PUSH_SUBJECT},ttl=86400,timeout=10)
            except WebPushException as exc:
                status=getattr(getattr(exc,'response',None),'status_code',None)
                if status in (404,410):
                    subscription.delete()
                    delivery.delete()
                    continue
                delivery.last_error='Push delivery failed.'
                delivery.next_attempt_at=timezone.now()+timedelta(minutes=min(2**delivery.attempts,60))
                delivery.save(update_fields=['attempts','last_error','next_attempt_at'])
                result['failed']+=1
            except Exception:
                delivery.last_error='Push delivery failed.'
                delivery.next_attempt_at=timezone.now()+timedelta(minutes=min(2**delivery.attempts,60))
                delivery.save(update_fields=['attempts','last_error','next_attempt_at'])
                result['failed']+=1
            else:
                delivery.sent_at=timezone.now();delivery.last_error='';delivery.next_attempt_at=None
                delivery.save(update_fields=['attempts','sent_at','last_error','next_attempt_at'])
                result['sent']+=1
    return result
