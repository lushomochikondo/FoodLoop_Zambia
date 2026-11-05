from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import AuditLog, FlagReport, FoodRequest, Listing, Notification, Organisation, RequestEvent

ACTIVE = ['pending', 'accepted', 'ready']

def organisation(user):
    try: return user.membership.organisation
    except AttributeError: raise PermissionDenied('An organisation account is required.')

def notify(org, message, listing=None, key=None):
    for user in User.objects.filter(membership__organisation=org, is_active=True):
        if key:
            Notification.objects.get_or_create(user=user, event_key=key, defaults={'message': message[:240], 'listing': listing})
        else:
            Notification.objects.create(user=user, message=message[:240], listing=listing)

def record(req, actor, description):
    RequestEvent.objects.create(request=req, actor=actor, status=req.status, description=description)
    AuditLog.objects.create(actor=actor, action=f'Request {req.pk}: {description}; status {req.status}'[:240])

def end_request(req, listing, status, actor, reason):
    if req.status in ['accepted', 'ready']:
        listing.allocated -= req.quantity
        listing.save(update_fields=['allocated'])
    req.status = status
    req.save()
    record(req, actor, reason)
    notify(req.recipient, f'{listing.name}: {reason}', listing)
    notify(listing.provider, f'{listing.name}: {reason}', listing)

@transaction.atomic
def expire_requests():
    now = timezone.now()
    stale = now - timedelta(hours=settings.REQUEST_EXPIRY_HOURS)
    candidates = FoodRequest.objects.filter(Q(status='pending') & (Q(created__lte=stale) | Q(listing__deadline__lte=now)) | Q(status__in=['accepted', 'ready'], listing__deadline__lte=now)).values_list('pk', 'listing_id')
    count = 0
    for pk, listing_id in list(candidates):
        listing = Listing.objects.select_for_update().get(pk=listing_id)
        req = FoodRequest.objects.select_for_update().get(pk=pk)
        if req.status == 'pending' and (req.created <= stale or listing.deadline <= now):
            end_request(req, listing, 'expired', None, 'Request expired before a decision.')
            count += 1
        elif req.status in ['accepted', 'ready'] and listing.deadline <= now:
            end_request(req, listing, 'no_show', None, 'Collection deadline passed without dual confirmation.')
            count += 1
    for listing in Listing.objects.filter(status='available', deadline__gt=now, deadline__lte=now+timedelta(hours=6), provider__status='approved'):
        notify(listing.provider, f'{listing.name}: collection deadline is within 6 hours.', listing, f'expiry:{listing.pk}:{listing.deadline.isoformat()}')
        for req in listing.requests.filter(status__in=['accepted', 'ready']).select_related('recipient'):
            notify(req.recipient, f'{listing.name}: your collection deadline is within 6 hours.', listing, f'expiry:{listing.pk}:{listing.deadline.isoformat()}')
    return count

@transaction.atomic
def request_food(user, listing_id, quantity, acknowledged):
    org = organisation(user)
    listing = Listing.objects.select_for_update().get(pk=listing_id)
    if org.status != 'approved' or org.role not in ['recipient', 'recovery'] or org.pathway != listing.pathway: raise PermissionDenied
    if not acknowledged: raise ValidationError('Accept the safety acknowledgement.')
    if not listing.available or quantity <= 0 or quantity > listing.remaining: raise ValidationError('The requested quantity is unavailable.')
    if listing.condition == 'spoiled' and org.pathway == 'human': raise PermissionDenied
    obj = FoodRequest.objects.create(listing=listing, recipient=org, quantity=quantity)
    record(obj, user, 'Request submitted')
    notify(listing.provider, f'New request: {org.name} requested {quantity} {listing.unit} of {listing.name}.', listing)
    return obj

@transaction.atomic
def change_request(user, pk, action):
    listing_id = FoodRequest.objects.values_list('listing_id', flat=True).get(pk=pk)
    listing = Listing.objects.select_for_update().get(pk=listing_id)
    req = FoodRequest.objects.select_for_update().select_related('recipient').get(pk=pk)
    if user.is_staff:
        if action != 'cancel': raise PermissionDenied
        provider = recipient = False
    else:
        org = organisation(user)
        if org.status != 'approved': raise PermissionDenied
        provider = org.role == 'provider' and org.pk == listing.provider_id
        recipient = org.role in ['recipient', 'recovery'] and org.pk == req.recipient_id
        if not (provider or recipient): raise PermissionDenied
    if action == 'cancel' and req.status in ACTIVE:
        end_request(req, listing, 'cancelled', user, 'Request cancelled; reserved quantity released.')
        return req
    if listing.deadline <= timezone.now() or listing.status != 'available': raise ValidationError('This listing is no longer available for collection updates.')
    if action == 'accept' and provider and req.status == 'pending':
        if not listing.available or req.quantity > listing.remaining: raise ValidationError('Insufficient quantity or listing unavailable.')
        if req.created <= timezone.now()-timedelta(hours=settings.REQUEST_EXPIRY_HOURS): raise ValidationError('This request has expired.')
        if req.recipient.status != 'approved' or req.recipient.pathway != listing.pathway: raise ValidationError('Recipient is no longer eligible.')
        listing.allocated += req.quantity
        listing.save(update_fields=['allocated'])
        req.status = 'accepted'
        req.decision_time = timezone.now()
    elif action == 'decline' and provider and req.status == 'pending':
        req.status = 'declined'
        req.decision_time = timezone.now()
    elif action == 'ready' and provider and req.status == 'accepted': req.status = 'ready'
    elif action == 'confirm' and req.status == 'ready':
        if listing.provider.status != 'approved' or req.recipient.status != 'approved': raise ValidationError('Both organisations must remain approved.')
        if provider and not req.provider_confirmed:
            req.provider_confirmed = timezone.now()
            req.confirmed_quantity = req.quantity
        elif recipient and not req.recipient_confirmed: req.recipient_confirmed = timezone.now()
        else: raise ValidationError('You have already confirmed collection.')
        if req.provider_confirmed and req.recipient_confirmed:
            req.status = 'collected'
            req.collected_at = timezone.now()
    else: raise ValidationError('This action is not available for the current status.')
    req.save()
    description = f'{action.title()} ({req.quantity} {listing.unit})'
    record(req, user, description)
    notify(req.recipient if provider else listing.provider, f'{listing.name}: {description}; {req.get_status_display()}.', listing)
    return req

@transaction.atomic
def close_listing(user, pk, status, reason):
    if status not in ['withdrawn', 'removed']: raise ValidationError('Invalid listing action.')
    listing = Listing.objects.select_for_update().get(pk=pk)
    if status == 'removed':
        if not user.is_staff: raise PermissionDenied
    else:
        org = organisation(user)
        if org.role != 'provider' or org.pk != listing.provider_id or org.status != 'approved': raise PermissionDenied
    if listing.status != 'available': raise ValidationError('This listing has already been closed.')
    for req in listing.requests.select_for_update().filter(status__in=ACTIVE):
        end_request(req, listing, 'cancelled', user, f'Listing {status}: {reason}')
    listing.status = status
    listing.save(update_fields=['status'])
    AuditLog.objects.create(actor=user, action=f'Listing {pk}: {status}. {reason}'[:240])
    notify(listing.provider, f'{listing.name}: {status}. {reason}', listing)
    return listing

@transaction.atomic
def delete_listing(user, pk):
    org = organisation(user)
    listing = Listing.objects.select_for_update().get(pk=pk)
    if org.role != 'provider' or org.pk != listing.provider_id or org.status != 'approved': raise PermissionDenied
    if listing.status == 'deleted': raise ValidationError('This listing has already been deleted.')
    original_pk = listing.pk
    name = listing.name
    Notification.objects.filter(listing=listing,email_sent_at__isnull=True,email_skipped_at__isnull=True,email_claim_token='').update(email_skipped_at=timezone.now(),email_last_error='Listing deleted before this update was emailed.')
    for req in listing.requests.select_for_update().filter(status__in=ACTIVE):
        end_request(req, listing, 'cancelled', user, 'The provider deleted this listing. Any reserved quantity has been released.')
    retained = listing.requests.exists() or FlagReport.objects.filter(listing=listing).exists()
    if retained:
        listing.status = 'deleted'
        listing.deleted_at = timezone.now()
        listing.save(update_fields=['status','deleted_at'])
    else:
        photo_name = listing.photo.name
        storage = listing.photo.storage
        listing.delete()
        if photo_name: transaction.on_commit(lambda: storage.delete(photo_name),robust=True)
    AuditLog.objects.create(actor=user, action=f'Listing {original_pk}: deleted by provider; history retained: {retained}. {name}'[:240])
    return retained

@transaction.atomic
def verify_organisation(user, pk, status, reason):
    if not user.is_staff: raise PermissionDenied
    if status not in ['approved', 'rejected', 'suspended'] or not reason.strip(): raise ValidationError('Choose a decision and provide a reason.')
    org = Organisation.objects.select_for_update().get(pk=pk)
    if status == 'approved' and (org.role == 'recipient' and org.pathway != 'human' or org.role == 'recovery' and org.pathway == 'human'):
        raise ValidationError('The approved pathway does not match this organisation role.')
    if status == 'approved':
        required = {'physical_address': 'physical address', 'contact_name': 'named contact', 'contact_email': 'contact email', 'phone': 'contact phone', 'activity_description': 'activity or beneficiaries', 'terms_accepted': 'terms acknowledgement'}
        if org.role == 'provider': required['authorised_representative'] = 'authorised representative acknowledgement'
        if org.role == 'recipient': required['handling_capacity'] = 'storage and handling capacity'
        missing = [label for field, label in required.items() if not getattr(org, field)]
        if missing: raise ValidationError('Complete the verification evidence first: ' + ', '.join(missing) + '.')
    org.status = status
    org.verification_reason = reason
    org.save(update_fields=['status', 'verification_reason'])
    AuditLog.objects.create(actor=user, action=f'Organisation {pk}: {status}. {reason}'[:240])
    notify(org, f'Your organisation is {status}: {reason}')
    return org

@transaction.atomic
def review_flag(user, pk, decision, reason):
    if not user.is_staff: raise PermissionDenied
    if decision not in ['dismissed', 'removed'] or not reason.strip(): raise ValidationError('A review decision and reason are required.')
    # All moderation paths acquire the listing lock first.
    listing_id = FlagReport.objects.values_list('listing_id', flat=True).get(pk=pk)
    listing = Listing.objects.select_for_update().get(pk=listing_id)
    flag = FlagReport.objects.select_for_update().get(pk=pk)
    if flag.status != 'pending': raise ValidationError('This flag has already been reviewed.')
    if decision == 'removed' and listing.status != 'removed':
        if listing.status in ['withdrawn','deleted']:
            if listing.status != 'deleted':
                listing.status = 'removed'; listing.save(update_fields=['status'])
            AuditLog.objects.create(actor=user, action=f'Listing {listing.pk}: removed. {reason}'[:240])
        else: close_listing(user, listing.pk, 'removed', reason)
    flag.status = decision
    flag.outcome = reason
    flag.reviewed_by = user
    flag.reviewed_at = timezone.now()
    flag.save()
    AuditLog.objects.create(actor=user, action=f'Flag {pk}: {decision}. {reason}'[:240])
    Notification.objects.create(user=flag.reporter, listing=listing, message=f'Your report on {listing.name}: {decision}. {reason}'[:240])
    return flag
