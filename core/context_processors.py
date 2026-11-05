from .models import Notification

def workspace(request):
    if not request.user.is_authenticated:
        return {}
    return {'unread_count': Notification.objects.filter(user=request.user, read=False).count()}
