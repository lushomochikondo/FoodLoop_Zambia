from .models import Notification

def workspace(request):
    if not request.user.is_authenticated:
        return {}
    return {'unread_count': Notification.objects.filter(user=request.user, read=False).count()}


def push(request):
    from django.conf import settings
    return {"web_push_public_key": settings.WEB_PUSH_PUBLIC_KEY}
