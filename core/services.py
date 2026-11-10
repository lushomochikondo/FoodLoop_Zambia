from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.contrib.auth.hashers import check_password, make_password
from functools import lru_cache
from .models import AuditLog, BeneficiaryApplication, FlagReport, FoodRequest, HandoverCode, Listing, ListingReoffer, Notification, Organisation, RequestEvent, PlatformSetting

ACTIVE = ['pending', 'accepted', 'ready']

@lru_cache(maxsize=1)
def _platform_settings():
    return dict(PlatformSetting.objects.values_list('key', 'value'))

def platform_setting(key, default=None, cast=str):
    value = _platform_settings().get(key, default)
    if value is None: value = default
    try: return cast(value)
    except (TypeError, ValueError): return cast(default)

def handover_code_for(req):
    digest = salted_hmac('foodloop.handover.v1', f'{req.pk}:{req.listing_id}', secret=settings.SECRET_KEY).hexdigest()
    return f'{int(digest[:16], 16) % 1_000_000:06d}'

def issue_handover_code(req):
    code = handover_code_for(req)
    HandoverCode.objects.update_or_create(request=req, defaults={
        'code_hash': make_password(code), 'expires_at': req.listing.deadline,
        'attempts': 0, 'verified_at': None,
    })
    return code

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

def end_request(req, listing, status, actor, reason, reoffer=True):
    if req.status in ['accepted', 'ready']:
        listing.allocated -= req.quantity
        listing.save(update_fields=['allocated'])
    req.status = status
    req.save()
    record(req, actor, reason)
    notify(req.recipient, f'{listing.name}: {reason}', listing)
    notify(listing.provider, f'{listing.name}: {reason}', listing)
    if reoffer and status in ['cancelled', 'expired', 'no_show'] and listing.status == 'available' and listing.deadline > timezone.now():
        reoffer_listing(listing, reason)

def reoffer_listing(listing, reason=''):
    if not listing.available: return 0
    from .matching import rank_listing
    excluded = set(listing.reoffers.values_list('organisation_id', flat=True))
    active = set(listing.requests.filter(status__in=ACTIVE).values_list('recipient_id', flat=True))
    candidates = Organisation.objects.filter(status='approved', role__in=['recipient', 'recovery'], pathway=listing.pathway).exclude(pk__in=excluded | active)
    ranked = []
    for org in candidates:
        match = rank_listing(listing, org)
        if match: ranked.append((match[0], org.pk, org))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    wave = (listing.reoffers.order_by('-wave').values_list('wave', flat=True).first() or 0) + 1
    limit = platform_setting('reoffer_group_size', getattr(settings, 'REOFFER_GROUP_SIZE', 5), int)
    sent = 0
    for score, _, org in ranked[:max(1, limit)]:
        ListingReoffer.objects.create(listing=listing, organisation=org, wave=wave)
        notify(org, f'{listing.name} is available for collection. Match score: {score}%.', listing,
               f'listing-match:{listing.pk}:{wave}:{org.pk}')
        sent += 1
    if sent:
        AuditLog.objects.create(actor=None, action=f'Listing {listing.pk}: re-offer wave {wave} sent to {sent} eligible organisation(s)')
        notify(listing.provider, f'{sent} suitable organisation(s) were notified about {listing.name}. {reason}'.strip(), listing,
               f'reoffer-provider:{listing.pk}:{wave}')
    return sent

def notify_half_time_waves():
    now = timezone.now()
    listings = Listing.objects.filter(status='available', deadline__gt=now, provider__status='approved', reoffer_second_wave_at__isnull=True)
    for listing in listings.select_related('provider').iterator():
        fraction = platform_setting('reoffer_half_time_fraction', getattr(settings, 'REOFFER_HALF_TIME_FRACTION', '0.5'), Decimal)
        midpoint = listing.created + (listing.deadline - listing.created) * float(fraction)
        if now < midpoint or listing.requests.filter(status='accepted').exists(): continue
        reoffer_listing(listing, 'No request has been accepted yet; this is the next matching group.')
        Listing.objects.filter(pk=listing.pk, reoffer_second_wave_at__isnull=True).update(reoffer_second_wave_at=now)

@transaction.atomic
def expire_requests():
    now = timezone.now()
    expiry_hours = platform_setting('request_expiry_hours', settings.REQUEST_EXPIRY_HOURS, Decimal)
    stale = now - timedelta(hours=float(expiry_hours))
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
    notify_half_time_waves()
    return count

@transaction.atomic
def request_food(user, listing_id, quantity, acknowledged):
    org = organisation(user)
    listing = Listing.objects.select_for_update().get(pk=listing_id)
    if org.status != 'approved' or org.role not in ['recipient', 'recovery']: raise PermissionDenied
    if not acknowledged: raise ValidationError('Accept the safety acknowledgement.')
    if not listing.available or quantity <= 0 or quantity > listing.remaining: raise ValidationError('The requested quantity is unavailable.')
    if listing.condition == 'spoiled' and listing.pathway == 'human': raise PermissionDenied
    obj = FoodRequest.objects.create(listing=listing, recipient=org, quantity=quantity)
    record(obj, user, 'Request submitted')
    notify(listing.provider, f'New request: {org.name} requested {quantity} {listing.unit} of {listing.name}.', listing)
    return obj

@transaction.atomic
def change_request(user, pk, action, code='', confirmed_weight_kg=None, confirmed_quantity=None):
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
        expiry_hours = platform_setting('request_expiry_hours', settings.REQUEST_EXPIRY_HOURS, Decimal)
        if req.created <= timezone.now()-timedelta(hours=float(expiry_hours)): raise ValidationError('This request has expired.')
        if req.recipient.status != 'approved' or req.recipient.role not in ['recipient', 'recovery']: raise ValidationError('Recipient is no longer eligible.')
        listing.allocated += req.quantity
        listing.save(update_fields=['allocated'])
        req.status = 'accepted'
        req.decision_time = timezone.now()
    elif action == 'decline' and provider and req.status == 'pending':
        req.status = 'declined'
        req.decision_time = timezone.now()
    elif action == 'ready' and provider and req.status == 'accepted':
        req.status = 'ready'
        req.save(update_fields=['status', 'updated'])
        issue_handover_code(req)
        record(req, user, 'Marked ready; one-time handover code issued')
        notify(req.recipient, f'{listing.name} is ready. Show the handover code in your Requests page at collection.', listing)
        notify(listing.provider, f'{listing.name} is ready for collection. Verify the recipient code at handover.', listing)
        return req
    elif action == 'confirm' and req.status == 'ready':
        if provider:
            if req.provider_confirmed:
                AuditLog.objects.create(actor=user, action=f'Handover code reuse attempt for request {req.pk}')
                return req, 'This handover has already been recorded.'
            if listing.provider.status != 'approved' or req.recipient.status != 'approved': raise ValidationError('Both organisations must remain approved.')
            if confirmed_quantity is None: confirmed_quantity = req.quantity
            if confirmed_quantity <= 0 or confirmed_quantity != req.quantity:
                raise ValidationError('Confirm the full accepted quantity. Partial collection is not supported.')
            if confirmed_weight_kg is None:
                if listing.unit == 'kg': confirmed_weight_kg = req.quantity
                elif listing.unit == 'litres': confirmed_weight_kg = req.quantity * Decimal(str(platform_setting('litre_to_kg_factor', getattr(settings, 'LITRE_TO_KG_FACTOR', 1), Decimal)))
            weight_limit = platform_setting('weight_sanity_limit_kg', getattr(settings, 'WEIGHT_SANITY_LIMIT_KG', 100000), Decimal)
            if confirmed_weight_kg is None or confirmed_weight_kg <= 0 or confirmed_weight_kg > Decimal(str(weight_limit)):
                raise ValidationError('Enter a weight greater than zero and within the supported limit.')
            handover = HandoverCode.objects.select_for_update().filter(request=req).first()
            if not handover:
                AuditLog.objects.create(actor=user, action=f'Handover code missing for collection attempt on request {req.pk}')
                return req, 'The handover code is unavailable. Mark the request ready again.'
            maximum = platform_setting('handover_attempt_limit', getattr(settings, 'HANDOVER_CODE_ATTEMPTS', 5), int)
            if handover.verified_at:
                AuditLog.objects.create(actor=user, action=f'Handover code reuse attempt for request {req.pk}')
                return req, 'This handover code has already been used.'
            if handover.expires_at <= timezone.now():
                AuditLog.objects.create(actor=user, action=f'Expired handover code attempted for request {req.pk}')
                return req, 'This handover code has expired.'
            if handover.attempts >= maximum:
                AuditLog.objects.create(actor=user, action=f'Locked handover code attempted for request {req.pk}')
                return req, 'This code is locked after too many incorrect attempts. Contact an administrator.'
            handover.attempts += 1
            if not code or not check_password(code.strip(), handover.code_hash):
                handover.save(update_fields=['attempts'])
                AuditLog.objects.create(actor=user, action=f'Handover code attempt failed for request {req.pk}; attempt {handover.attempts}'[:240])
                return req, f'Incorrect handover code. {max(0, maximum-handover.attempts)} attempt(s) remain.'
            handover.verified_at = timezone.now()
            handover.save(update_fields=['attempts', 'verified_at'])
            AuditLog.objects.create(actor=user, action=f'Handover code verified for request {req.pk}')
            req.provider_confirmed = timezone.now()
            req.confirmed_quantity = confirmed_quantity
            req.confirmed_weight_kg = confirmed_weight_kg
        elif recipient and req.provider_confirmed and not req.recipient_confirmed: req.recipient_confirmed = timezone.now()
        elif recipient and not req.provider_confirmed: raise ValidationError('The donor must verify the handover code and record the weight first.')
        else: raise ValidationError('You have already confirmed collection.')
        if req.provider_confirmed and req.recipient_confirmed:
            req.status = 'collected'
            req.collected_at = timezone.now()
    else: raise ValidationError('This action is not available for the current status.')
    req.save()
    description = f'{action.title()} ({req.quantity} {listing.unit})'
    if action == 'confirm' and provider:
        description += f'; recorded weight {req.confirmed_weight_kg} kg'
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
        end_request(req, listing, 'cancelled', user, f'Listing {status}: {reason}', reoffer=False)
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
        end_request(req, listing, 'cancelled', user, 'The donor deleted this listing. Any reserved quantity has been released.', reoffer=False)
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
    AuditLog.objects.create(actor=user, action=f'Listing {original_pk}: deleted by donor; history retained: {retained}. {name}'[:240])
    return retained

@transaction.atomic
def verify_organisation(user, pk, status, reason):
    if not user.is_staff: raise PermissionDenied
    if status not in ['approved', 'needs_info', 'rejected', 'suspended'] or not reason.strip(): raise ValidationError('Choose a decision and provide a reason.')
    org = Organisation.objects.select_for_update().get(pk=pk)
    if status == 'approved' and org.role == 'recovery' and org.pathway == 'human':
        raise ValidationError('The approved pathway does not match this organisation role.')
    if status == 'approved':
        required = {'physical_address': 'physical address', 'contact_name': 'named contact', 'contact_email': 'contact email', 'phone': 'contact phone', 'activity_description': 'activity or beneficiaries', 'terms_accepted': 'terms acknowledgement'}
        if org.role == 'provider': required['authorised_representative'] = 'authorised representative acknowledgement'
        if org.role == 'recipient': required['handling_capacity'] = 'storage and handling capacity'
        missing = [label for field, label in required.items() if not getattr(org, field)]
        if org.role == 'recipient':
            try:
                application = org.beneficiary_application
            except BeneficiaryApplication.DoesNotExist:
                application = None
            if not application or not application.submitted_at:
                missing.append('submitted beneficiary assessment')
            else:
                evidence = [application.legal_form, application.programme_type, application.storage_description.strip(), application.beneficiary_records, application.no_resale_agreement, application.inspection_consent, application.information_accuracy]
                if org.pathway == 'human':
                    evidence += [application.people_served, application.feeding_days_per_week, application.health_clearance, application.food_handler_evidence, application.nondiscrimination_agreement]
                if not all(evidence):
                    missing.append('completed beneficiary assessment and required acknowledgements')
                if BeneficiaryApplication.pathway_for_programme(application.programme_type) != org.pathway:
                    missing.append('programme type matching the approved recovery pathway')
        if missing: raise ValidationError('Complete the verification evidence first: ' + ', '.join(missing) + '.')
    org.status = status
    org.verification_reason = reason
    if status == 'approved': org.last_verified_at = timezone.now()
    org.save(update_fields=['status', 'verification_reason', 'last_verified_at'])
    AuditLog.objects.create(actor=user, action=f'Organisation {pk}: {status}. {reason}'[:240])
    notification = 'FoodLoop requests additional information about your organisation' if status == 'needs_info' else f'Your organisation is {status}: {reason}'
    notify(org, f'{notification}: {reason}' if status == 'needs_info' else notification)
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
