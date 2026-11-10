from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import F, Q, Sum
from django.db import transaction
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.db import IntegrityError
from django.forms import HiddenInput
from django.http import FileResponse, HttpResponse, JsonResponse
import csv
import hmac
import json
import math
import os
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.http import HttpResponseNotFound
from django.core.management import call_command
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST
from .forms import BeneficiaryApplicationForm, BeneficiaryEligibilityForm, CollectionNotesForm, DecisionForm, FlagForm, ListingForm, PreferencesForm, ProfileForm, RequestForm
from .forms import SignupForm, StorySubmissionForm
from .models import AuditLog, BeneficiaryApplication, FlagReport, FoodRequest, Listing, Notification, Organisation, PATHWAYS, PlatformSetting, StorySubmission
from .models import Membership, PushSubscription
from .models import EmailPreferences
from .services import change_request, close_listing, end_request, expire_requests, notify, organisation, request_food, review_flag, verify_organisation, handover_code_for, reoffer_listing, platform_setting
from .matching import rank_listing
from .services import delete_listing as delete_listing_record
from .location import distance_km

BENEFICIARY_ELIGIBILITY_VERSION = 'zambia-beneficiary-v1'

def beneficiary_eligibility(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = BeneficiaryEligibilityForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        request.session['beneficiary_eligibility'] = {
            'version': BENEFICIARY_ELIGIBILITY_VERSION,
            'programme_type': form.cleaned_data['programme_type'],
            'accepted_at': timezone.now().isoformat(),
        }
        return redirect(f"{reverse('signup')}?type=recipient")
    return render(request, 'beneficiary_eligibility.html', {
        'form': form,
        'eligibility_version': BENEFICIARY_ELIGIBILITY_VERSION,
    })

def signup(request):
    if request.user.is_authenticated: return redirect('home')
    signup_type = request.GET.get('type', '')
    acceptance = request.session.get('beneficiary_eligibility', {})
    if signup_type == 'recipient' and acceptance.get('version') != BENEFICIARY_ELIGIBILITY_VERSION:
        messages.info(request, 'Review and accept the beneficiary application requirements before continuing.')
        return redirect('beneficiary_eligibility')
    form = SignupForm(request.POST or None)
    if signup_type in ('provider', 'recipient'):
        form.fields['account_type'].choices = [(signup_type, 'Donor account' if signup_type == 'provider' else 'Beneficiary account')]
        form.fields['account_type'].widget = HiddenInput()
        form.initial['account_type'] = signup_type
    if request.method == 'POST' and form.is_valid():
        account_type = form.cleaned_data['account_type']
        if account_type == 'recipient' and acceptance.get('version') != BENEFICIARY_ELIGIBILITY_VERSION:
            messages.info(request, 'Review and accept the beneficiary application requirements before continuing.')
            return redirect('beneficiary_eligibility')
        try:
            with transaction.atomic():
                user = form.save(commit=False)
                user.email = form.cleaned_data['email']
                user.first_name = form.cleaned_data['contact_name'][:150]
                user.is_staff = False
                user.is_superuser = False
                user.save()
                application_draft = account_type == 'recipient'
                immediate_donor = account_type == 'provider'
                beneficiary_pathway = BeneficiaryApplication.pathway_for_programme(acceptance.get('programme_type', ''))
                org = Organisation.objects.create(name=form.cleaned_data['organisation_name'], role=account_type if account_type in ['provider', 'recipient'] else 'recovery', pathway=beneficiary_pathway if application_draft else account_type if account_type in ['feed', 'compost'] else 'human', status='draft' if application_draft else 'approved' if immediate_donor else 'pending', verification_reason='Donor posting enabled at registration; administrator approval is not required.' if immediate_donor else '', contact_name=form.cleaned_data['contact_name'], contact_email=form.cleaned_data['email'], phone=form.cleaned_data['phone'], area=form.cleaned_data['area'], physical_address=form.cleaned_data['physical_address'], registration_reference=form.cleaned_data['registration_reference'], activity_description=form.cleaned_data['activity_description'], handling_capacity=form.cleaned_data['handling_capacity'], authorised_representative=form.cleaned_data['authorised_representative'], terms_accepted=True)
                Membership.objects.create(user=user, organisation=org)
                if application_draft:
                    BeneficiaryApplication.objects.create(
                        organisation=org,
                        programme_type=acceptance.get('programme_type', ''),
                        eligibility_rules_version=acceptance.get('version', ''),
                        eligibility_accepted_at=parse_datetime(acceptance.get('accepted_at', '')) or timezone.now(),
                    )
                EmailPreferences.objects.create(user=user, enabled=form.cleaned_data['email_updates'])
                AuditLog.objects.create(actor=user, action=f'Organisation {org.pk}: beneficiary application draft created' if application_draft else f'Organisation {org.pk}: donor posting enabled at registration' if immediate_donor else f'Organisation {org.pk}: self-registration submitted for verification')
                Notification.objects.create(user=user, message='Your beneficiary application is saved as a draft.' if application_draft else 'Welcome to FoodLoop. Your donor account is active. You can publish food listings immediately.' if immediate_donor else 'Welcome to FoodLoop. Your organisation is awaiting administrator verification. Review may take up to 72 hours.')
                for admin in User.objects.filter(is_staff=True, is_active=True):
                    message = f'New beneficiary registration (assessment not yet submitted): {org.name}' if application_draft else f'New donor registered with immediate posting access: {org.name}' if immediate_donor else f'New organisation awaiting verification: {org.name}'
                    Notification.objects.create(user=admin, message=message[:240])
        except IntegrityError:
            form.add_error('username', 'This username was just registered. Choose another and try again.')
        else:
            login(request, user)
            if application_draft:
                request.session.pop('beneficiary_eligibility', None)
                messages.success(request, 'Account created. Your beneficiary application is saved as a draft. Complete it when you are ready to submit for review.')
                return redirect('beneficiary_application')
            if immediate_donor:
                messages.success(request, 'Your donor account is ready. Publish your first listing now; no administrator approval is required.')
                return redirect('create_listing')
            messages.success(request, 'Account created. Your organisation is awaiting verification. Review may take up to 72 hours; you can list or request food once approved.')
            return redirect('home')
    return render(request, 'signup.html', {'form': form, 'signup_type': signup_type if signup_type in ('provider', 'recipient') else ''})

@login_required
def beneficiary_application(request):
    org = organisation(request.user)
    if org.role != 'recipient': raise PermissionDenied
    application, _ = BeneficiaryApplication.objects.get_or_create(organisation=org)
    editable = org.status in ('draft', 'needs_info')
    submitting = request.method == 'POST' and request.POST.get('action') == 'submit'
    if request.method == 'POST' and not editable:
        messages.info(request, 'Your application is already under review. You can update it if FoodLoop requests more information.')
        return redirect('beneficiary_application')
    form = BeneficiaryApplicationForm(request.POST or None, request.FILES or None, instance=application, submitting=submitting)
    if request.method == 'POST' and form.is_valid():
        application = form.save(commit=False)
        application.organisation = org
        if submitting:
            application.submitted_at = timezone.now()
            org.status = 'pending'
            org.save(update_fields=['status'])
            AuditLog.objects.create(actor=request.user, action=f'Beneficiary application for organisation {org.pk} submitted for review')
            Notification.objects.create(user=request.user, message='Your beneficiary application has been submitted for review. Review may take up to 72 hours.')
            for admin in User.objects.filter(is_staff=True, is_active=True):
                Notification.objects.create(user=admin, message=f'Beneficiary application awaiting review: {org.name}'[:240])
            application.save()
            messages.success(request, 'Your application has been submitted for review. Review may take up to 72 hours.')
        else:
            application.save()
            messages.success(request, 'Your application draft has been saved.' if org.status == 'draft' else 'Your changes are saved. Submit the updated application when ready.')
        return redirect('beneficiary_application')
    return render(request, 'beneficiary_application.html', {'form': form, 'org': org, 'application': application, 'editable': editable})

@login_required
def beneficiary_document(request, pk, kind):
    if kind not in ('registration_document', 'health_document', 'supporting_document'):
        raise HttpResponseNotFound()
    application = get_object_or_404(BeneficiaryApplication.objects.select_related('organisation'), organisation_id=pk)
    if not request.user.is_staff and not Membership.objects.filter(user=request.user, organisation=application.organisation).exists():
        raise PermissionDenied
    evidence = getattr(application, kind)
    if not evidence:
        raise HttpResponseNotFound()
    return FileResponse(evidence.open('rb'), as_attachment=True, filename=evidence.name.rsplit('/', 1)[-1])

def visible(user):
    listings = Listing.objects.select_related('provider')
    if user.is_staff: return listings
    org = organisation(user)
    if org.role == 'provider': return listings.filter(provider=org)
    listings = listings.filter(provider__status='approved').filter(~Q(status='deleted')|Q(requests__recipient=org)).distinct()
    return listings

def workspace_context(request):
    expire_requests()
    org = None if request.user.is_staff else organisation(request.user)
    listings = visible(request.user).exclude(status='deleted')
    requests = FoodRequest.objects.select_related('listing', 'recipient')
    if org:
        requests = requests.filter(listing__provider=org) if org.role == 'provider' else requests.filter(recipient=org)
        if org.role != 'provider': listings = listings.filter(status='available', deadline__gt=timezone.now()).exclude(allocated__gte=F('quantity'))
    area = request.GET.get('area', '').strip()
    search = request.GET.get('q', '').strip()
    pathway = request.GET.get('pathway', '')
    if search: listings = listings.filter(name__icontains=search)
    if pathway in dict(PATHWAYS): listings = listings.filter(pathway=pathway)
    if area: listings = listings.filter(area__icontains=area)
    availability = request.GET.get('availability', '')
    if availability == 'available': listings = listings.filter(status='available', deadline__gt=timezone.now(), allocated__lt=F('quantity'))
    elif availability == 'expired': listings = listings.filter(status='available', deadline__lte=timezone.now())
    elif availability == 'allocated': listings = listings.filter(status='available', deadline__gt=timezone.now(), allocated__gte=F('quantity'))
    elif availability in ['withdrawn', 'removed']: listings = listings.filter(status=availability)
    cards = list(listings.order_by('deadline'))
    for listing in cards:
        same = org and org.area.casefold() == listing.area.casefold()
        listing.match_reason = ('Same area · ' if same else '') + 'Collect by ' + timezone.localtime(listing.deadline).strftime('%d %b, %H:%M CAT')
    if org and org.role != 'provider':
        ranked = []
        for listing in cards:
            listing.can_collect = org.status == 'approved' and not (listing.pathway == 'human' and listing.condition == 'spoiled')
            match = rank_listing(listing, org)
            if match:
                listing.match_score, listing.match_reason = match
            else:
                listing.match_score = None
                listing.match_reason = f'For {listing.get_pathway_display().lower()}. Request only if your organisation can handle and use it for this purpose.'
            ranked.append(listing)
        cards = sorted(ranked, key=lambda item: (item.match_score is None, -(item.match_score or 0), item.deadline, item.pk))
    collected = requests.filter(status='collected')
    kg = collected.aggregate(n=Sum('confirmed_weight_kg'))['n'] or Decimal('0')
    human = collected.filter(listing__pathway='human').aggregate(n=Sum('confirmed_weight_kg'))['n'] or Decimal('0')
    meal_weight = platform_setting('meal_weight_kg', settings.MEAL_WEIGHT_KG, Decimal)
    if meal_weight <= 0: meal_weight = Decimal('0.4')
    pathway_totals = []
    for code, label in PATHWAYS:
        total = collected.filter(listing__pathway=code).aggregate(n=Sum('confirmed_weight_kg'))['n'] or Decimal('0')
        pathway_totals.append({'code': code, 'label': label, 'kg': total, 'percent': round(float(total / kg * 100)) if kg else 0})
    own_listings = visible(request.user)
    if org and org.role != 'provider': own_listings = own_listings.filter(pk__in=requests.values('listing_id'))
    listed_kg = own_listings.filter(unit='kg').aggregate(n=Sum('quantity'))['n'] or 0
    closed_kg = own_listings.filter(unit='kg', deadline__lte=timezone.now()).exclude(status__in=['withdrawn', 'removed', 'deleted'])
    collected_by_listing = {row['listing_id']: row['amount'] or Decimal('0') for row in requests.filter(status='collected').values('listing_id').annotate(amount=Sum('confirmed_quantity'))}
    wasted_kg = sum((max(Decimal('0'), item.quantity-collected_by_listing.get(item.pk, Decimal('0'))) for item in closed_kg), Decimal('0'))
    return {'org': org, 'listings': cards, 'requests': requests.order_by('-created'), 'kg': kg, 'listed_kg': listed_kg, 'wasted_kg': wasted_kg, 'availability': availability, 'meals': int(Decimal(human) / meal_weight), 'meal_weight': meal_weight, 'weight_limit': platform_setting('weight_sanity_limit_kg', settings.WEIGHT_SANITY_LIMIT_KG, int), 'area': area, 'collection_count': requests.filter(status='collected').count(), 'search': search, 'pathway': pathway, 'pathways': PATHWAYS, 'pathway_totals': pathway_totals, 'pending_count': requests.filter(status='pending').count(), 'listing_count': len(cards)}

def landing_page(request):
    from .models import NewsArticle
    return render(request, 'landing.html', {
        'is_landing': True,
        'provider_count': Organisation.objects.filter(role='provider', status='approved').count(),
        'beneficiary_count': Organisation.objects.filter(role='recipient', status='approved').count(),
        'collection_count': FoodRequest.objects.filter(status='collected').count(),
        'success_stories': NewsArticle.objects.filter(category='success_story', published=True, published_at__lte=timezone.now())[:3],
    })

def home(request):
    if not request.user.is_authenticated:
        return landing_page(request)
    context=workspace_context(request)
    sort=request.GET.get('sort','recommended')
    if sort=='newest': context['listings'].sort(key=lambda item:item.created,reverse=True)
    elif sort=='deadline': context['listings'].sort(key=lambda item:item.deadline)
    context['sort']=sort
    return render(request,'exchange.html',context)

@login_required
@require_POST
def nearby_listings(request):
    org = None if request.user.is_staff else organisation(request.user)
    if org and (org.role == 'provider' or org.status != 'approved'):
        raise PermissionDenied
    try:
        payload = json.loads(request.body or '{}')
        latitude = float(payload['latitude'])
        longitude = float(payload['longitude'])
        listing_ids = list(dict.fromkeys(int(value) for value in payload.get('listing_ids', [])))
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return JsonResponse({'error': 'A valid current location is required.'}, status=400)
    if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180 or len(listing_ids) > 300:
        return JsonResponse({'error': 'The location or listing selection is invalid.'}, status=400)
    permitted = visible(request.user).filter(pk__in=listing_ids, status='available', deadline__gt=timezone.now(), allocated__lt=F('quantity'), provider__status='approved').select_related('provider')
    rows = []
    for listing in permitted:
        if listing.pickup_latitude is None or listing.pickup_longitude is None:
            rows.append((None, listing.pk, None))
            continue
        km = distance_km(latitude, longitude, listing.pickup_latitude, listing.pickup_longitude)
        label = '<1 km away' if km < 1 else f'About {int(km + 0.5)} km away'
        rows.append((km, listing.pk, label))
    original_order = {pk: position for position, pk in enumerate(listing_ids)}
    rows.sort(key=lambda row: (row[0] is None, row[0] if row[0] is not None else original_order.get(row[1], 9999)))
    response = JsonResponse({'listings': [{'id': pk, 'distance': label} for _, pk, label in rows]})
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'no-referrer'
    return response

@login_required
def dashboard(request):
    from datetime import timedelta
    from django.db.models.functions import TruncDate
    from .models import RequestEvent
    context=workspace_context(request)
    requests=context['requests']
    context['accepted_count']=requests.filter(status='accepted').count()
    context['ready_count']=requests.filter(status='ready').count()
    context['active_count']=requests.filter(status__in=['pending','accepted','ready']).count()
    context['recent_events']=RequestEvent.objects.filter(request__in=requests).select_related('request__listing','actor').order_by('-created')[:8]
    start=timezone.localdate()-timedelta(days=6)
    daily=requests.filter(status='collected',collected_at__date__gte=start).annotate(day=TruncDate('collected_at')).values('day').annotate(quantity=Sum('confirmed_weight_kg'))
    values={row['day']:row['quantity'] for row in daily}
    maximum=max(values.values(),default=Decimal('1')) or Decimal('1')
    context['daily_collections']=[{'day':start+timedelta(days=i),'quantity':values.get(start+timedelta(days=i),0),'height':round(float(values.get(start+timedelta(days=i),0)/maximum)*100)} for i in range(7)]
    from .dashboard_data import visual_context
    context.update(visual_context(requests,context['pathway_totals']))
    context['area_impact_url'] = '/impact/'
    impact_org = context['org']
    impact_listings = Listing.objects.all()
    impact_collections = FoodRequest.objects.filter(status='collected')
    if impact_org:
        impact_listings = impact_listings.filter(provider=impact_org) if impact_org.role == 'provider' else impact_listings.filter(pk__in=FoodRequest.objects.filter(recipient=impact_org).values('listing_id'))
        impact_collections = impact_collections.filter(listing__provider=impact_org) if impact_org.role == 'provider' else impact_collections.filter(recipient=impact_org)
    context['area_measure'] = request.GET.get('measure', 'listed')
    if context['area_measure'] not in {'listed', 'collected', 'wasted'}: context['area_measure'] = 'listed'
    context['area_rows'], _ = build_area_impact_rows(impact_listings, impact_collections, context['area_measure'])
    return render(request,'dashboard.html',context)

@login_required
def submit_success_story(request):
    org = organisation(request.user)
    if org.status != 'approved' or org.role not in ('provider', 'recipient', 'recovery'):
        raise PermissionDenied('Only approved FoodLoop partners can submit stories.')
    form = StorySubmissionForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        submission = form.save(commit=False)
        submission.organisation = org
        submission.submitted_by = request.user
        submission.save()
        Notification.objects.create(user=request.user, message='Your success story has been sent to FoodLoop for review.')
        for admin_user in User.objects.filter(is_staff=True, is_active=True):
            Notification.objects.create(user=admin_user, message=f'Success story awaiting review from {org.name}.'[:240])
        AuditLog.objects.create(actor=request.user, action=f'Success story submitted by organisation {org.pk}: {submission.title[:160]}')
        messages.success(request, 'Your story has been sent to FoodLoop for review. It will appear publicly if approved.')
        return redirect('submit_success_story')
    submissions = StorySubmission.objects.filter(organisation=org).select_related('news_article')
    return render(request, 'story_submission.html', {'form': form, 'org': org, 'submissions': submissions})

@require_GET
def scheduled_jobs(request):
    secret = os.environ.get('CRON_SECRET', '')
    authorization = request.headers.get('Authorization', '')
    if not secret or not hmac.compare_digest(authorization, f'Bearer {secret}'):
        return HttpResponseNotFound()
    call_command('run_jobs')
    return JsonResponse({'ok': True})

@login_required
def collections(request):
    context=workspace_context(request)
    status=request.GET.get('status','')
    if status in dict(FoodRequest._meta.get_field('status').choices):context['requests']=context['requests'].filter(status=status)
    context['selected_status']=status
    context['request_statuses']=FoodRequest._meta.get_field('status').choices
    context['return_to_collections']=True
    return render(request,'collections.html',context)

@login_required
def create_listing(request):
    org = organisation(request.user)
    if org.role != 'provider' or org.status != 'approved': raise PermissionDenied
    form = ListingForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        listing = form.save(commit=False)
        listing.provider = org
        listing.save()
        reoffer_listing(listing, 'New listing published.')
        messages.success(request, 'Listing published and available to eligible organisations.')
        return redirect('detail', pk=listing.pk)
    return render(request, 'form.html', {'form': form})

@login_required
def detail(request, pk):
    expire_requests()
    listing = get_object_or_404(visible(request.user), pk=pk)
    org = None if request.user.is_staff else organisation(request.user)
    provider = org and org.role == 'provider' and listing.provider_id == org.pk
    accepted = org and listing.requests.filter(recipient=org, status__in=['accepted', 'ready', 'collected']).exists()
    form = RequestForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            request_food(request.user, pk, form.cleaned_data['quantity'], form.cleaned_data['safety'])
            messages.success(request, 'Request submitted. Track its status under Menu / Requests & collections. Stock is reserved when the donor accepts.')
            return redirect('home')
        except ValidationError as exc: form.add_error(None, exc)
    history = listing.requests.select_related('recipient').prefetch_related('events')
    if org and not provider: history = history.filter(recipient=org)
    form.fields['quantity'].widget.attrs.update({'max': str(listing.remaining), 'step':'0.01'})
    from .routing import destination_for
    route_destination = destination_for(listing, request.user, org) if request.user.is_staff or (org and org.status == 'approved') else None
    return render(request, 'detail.html', {'route_destination':route_destination, 'org':org,'listing': listing, 'form': form, 'show_private': provider or accepted or request.user.is_staff, 'can_request': org and org.role != 'provider' and org.status == 'approved' and not (listing.pathway == 'human' and listing.condition == 'spoiled') and listing.available, 'is_provider': provider, 'can_edit': provider and listing.available and listing.allocated == 0, 'can_delete':provider and org.status == 'approved' and listing.status != 'deleted', 'can_flag': org and org.role != 'provider' and org.status == 'approved', 'history': history, 'requests':history,'return_to_listing':True,'flag_form': FlagForm()})

@login_required
@require_POST
def transition(request, pk, action):
    try:
        raw_weight = request.POST.get('weight_kg', '').strip()
        try: weight = Decimal(raw_weight) if raw_weight else None
        except Exception: weight = None
        raw_quantity = request.POST.get('confirmed_quantity', '').strip()
        try: confirmed_quantity = Decimal(raw_quantity) if raw_quantity else None
        except Exception: confirmed_quantity = None
        result = change_request(request.user, pk, action, code=request.POST.get('handover_code', ''), confirmed_weight_kg=weight, confirmed_quantity=confirmed_quantity)
        failed_code = isinstance(result, tuple)
        item = result[0] if failed_code else result
    except FoodRequest.DoesNotExist: return HttpResponseNotFound()
    except ValidationError as exc: messages.error(request, '; '.join(exc.messages))
    else:
        if failed_code:
            messages.error(request, result[1])
        else:
            messages.success(request, 'Request accepted and quantity reserved.' if action == 'accept' else 'Request updated.')
        if request.POST.get('return_to_listing') == '1': return redirect('detail', pk=item.listing_id)
        if request.POST.get('return_to_collections') == '1': return redirect('collections')
    if request.POST.get('return_to_collections') == '1': return redirect('collections')
    return redirect('home')

@login_required
def delete_listing(request, pk):
    org = organisation(request.user)
    listing = get_object_or_404(Listing, pk=pk)
    if org.role != 'provider' or org.pk != listing.provider_id or org.status != 'approved': raise PermissionDenied
    if request.method == 'POST':
        if request.POST.get('confirm') != 'yes':
            messages.error(request, 'Confirm deletion before continuing.')
            return redirect('delete_listing',pk=pk)
        try: retained = delete_listing_record(request.user,pk)
        except ValidationError as exc: messages.error(request,'; '.join(exc.messages))
        else: messages.success(request,'Listing deleted from your listings. Request and collection history has been retained.' if retained else 'Listing deleted.')
        return redirect('home')
    return render(request,'delete_listing.html',{'listing':listing,'active_requests':listing.requests.filter(status__in=['pending','accepted','ready']).count(),'has_history':listing.requests.exists()})

@login_required
@transaction.atomic
def edit_listing(request, pk):
    org = organisation(request.user)
    listing = get_object_or_404(Listing.objects.select_for_update(), pk=pk)
    if org.role != 'provider' or org.pk != listing.provider_id or org.status != 'approved': raise PermissionDenied
    if not listing.available or listing.allocated != 0:
        messages.error(request, 'Only available listings with no accepted allocations can be edited.')
        return redirect('detail', pk=pk)
    form = ListingForm(request.POST or None, request.FILES or None, instance=listing)
    if request.method == 'POST' and form.is_valid():
        if form.cleaned_data['deadline'] <= timezone.now():
            form.add_error('deadline', 'Choose a future collection deadline.')
        else:
            listing = form.save()
            for req in listing.requests.select_for_update().filter(status='pending'):
                end_request(req, listing, 'cancelled', request.user, 'Listing details changed. Review the updated donation and request again.')
            AuditLog.objects.create(actor=request.user, action=f'Listing {pk}: edited')
            messages.success(request, 'Listing updated. Any pending requesters have been asked to review the new details.')
            return redirect('detail', pk=pk)
    return render(request, 'form.html', {'form': form, 'editing': True, 'listing': listing})

@login_required
@require_POST
def withdraw_listing(request, pk):
    try: close_listing(request.user, pk, 'withdrawn', 'Withdrawn by the donor.')
    except Listing.DoesNotExist: return HttpResponseNotFound()
    except ValidationError as exc: messages.error(request, '; '.join(exc.messages))
    else: messages.success(request, 'Listing withdrawn. Active requests were cancelled and reserved quantities released.')
    return redirect('detail', pk=pk)

@login_required
@require_POST
@transaction.atomic
def report_listing(request, pk):
    listing = get_object_or_404(Listing.objects.select_for_update().filter(pk__in=visible(request.user).values('pk')), pk=pk)
    org = organisation(request.user)
    if org.role not in ['recipient', 'recovery'] or org.status != 'approved': raise PermissionDenied
    form = FlagForm(request.POST)
    if form.is_valid():
        flag = FlagReport.objects.create(listing=listing, reporter=request.user, reason=form.cleaned_data['reason'])
        AuditLog.objects.create(actor=request.user, action=f'Flag {flag.pk}: submitted for listing {pk}')
        for admin in User.objects.filter(is_staff=True, is_active=True):
            Notification.objects.create(user=admin, listing=listing, message=f'Listing report: {listing.name}. Review in Administration.')
        messages.success(request, 'Your report was sent to the administrator for review.')
    else: messages.error(request, 'Please describe the concern using 5 to 2000 characters.')
    return redirect('detail', pk=pk)

@login_required
def notifications(request):
    if request.method == 'POST':
        items = Notification.objects.filter(user=request.user)
        if request.POST.get('notification_id'):
            try: note_id = int(request.POST['notification_id'])
            except ValueError: return HttpResponse('Invalid notification.', status=400)
            items = items.filter(pk=note_id)
        items.update(read=True)
        return redirect('notifications')
    return render(request, 'notifications.html', {'notifications': Notification.objects.filter(user=request.user)[:100]})

@login_required
def moderation(request):
    if not request.user.is_staff: raise PermissionDenied
    form = DecisionForm(request.POST or None)
    if request.method == 'POST' and request.POST.get('kind') == 'bulk_organisation':
        ids = list(dict.fromkeys(request.POST.getlist('organisation_ids')))
        decision = request.POST.get('decision', '')
        reason = request.POST.get('reason', '').strip()
        if not ids or decision not in ['approved', 'needs_info', 'rejected', 'suspended'] or len(reason) < 3 or len(reason) > 1000:
            messages.error(request, 'Select at least one organisation, choose a decision and enter a reason of at least 3 characters.')
        else:
            try:
                with transaction.atomic():
                    pending_ids = list(Organisation.objects.select_for_update().filter(pk__in=ids, status__in=['pending', 'needs_info']).values_list('pk', flat=True))
                    if len(pending_ids) != len(ids):
                        raise ValidationError('Some selected organisations are no longer pending. Refresh the page and review the current decisions.')
                    for org_id in pending_ids:
                        verify_organisation(request.user, org_id, decision, reason)
            except (Organisation.DoesNotExist, ValidationError) as exc:
                messages.error(request, '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'An organisation could not be found.')
            else:
                messages.success(request, f'Recorded {decision} for {len(ids)} organisations. Each decision is in the audit trail.')
        return redirect('moderation')
    if request.method == 'POST' and form.is_valid():
        try:
            if request.POST.get('kind') == 'organisation': verify_organisation(request.user, request.POST.get('record_id'), request.POST.get('decision'), form.cleaned_data['reason'])
            elif request.POST.get('kind') == 'flag': review_flag(request.user, request.POST.get('record_id'), request.POST.get('decision'), form.cleaned_data['reason'])
            elif request.POST.get('kind') == 'listing': close_listing(request.user, request.POST.get('record_id'), 'removed', form.cleaned_data['reason'])
            else: raise ValidationError('Choose a valid review action.')
        except (Organisation.DoesNotExist, FlagReport.DoesNotExist, Listing.DoesNotExist, ValueError): messages.error(request, 'That record could not be found.')
        except ValidationError as exc: messages.error(request, '; '.join(exc.messages))
        else: messages.success(request, 'Decision recorded in the audit trail.')
        return redirect('moderation')
    return render(request, 'moderation.html', {'beneficiary_drafts': Organisation.objects.filter(role='recipient', status='draft').order_by('-pk'), 'organisations': Organisation.objects.exclude(status='draft').order_by('status', 'name'), 'flags': FlagReport.objects.select_related('listing', 'reporter').filter(status='pending'), 'moderation_listings': Listing.objects.filter(status='available').select_related('provider'), 'audit': AuditLog.objects.select_related('actor').order_by('-created', '-pk')[:60], 'decision_form': form})

def build_area_impact_rows(listings, collections, measure):
    units = Listing._meta.get_field('unit').choices
    listed_items = list(listings)
    collected_by_listing = {row['listing_id']: row['amount'] or Decimal('0') for row in collections.values('listing_id').annotate(amount=Sum('confirmed_quantity'))}
    area_data = {}
    wasted_by_unit = {unit: Decimal('0') for unit, _ in units}
    now = timezone.now()
    for item in listed_items:
        key = (item.area, item.unit)
        row = area_data.setdefault(key, {'area': item.area, 'unit': item.get_unit_display(), 'listed': Decimal('0'), 'collected': Decimal('0'), 'wasted': Decimal('0')})
        row['listed'] += item.quantity
        row['collected'] += collected_by_listing.get(item.pk, Decimal('0'))
        if item.deadline <= now and item.status not in {'withdrawn', 'removed', 'deleted'}:
            amount = max(Decimal('0'), item.quantity - collected_by_listing.get(item.pk, Decimal('0')))
            row['wasted'] += amount
            wasted_by_unit[item.unit] += amount
    maximum = max((row[measure] for row in area_data.values()), default=Decimal('0')) or Decimal('1')
    rows = []
    for row in sorted(area_data.values(), key=lambda value: (value['area'].casefold(), value['unit'])):
        row['level'] = min(5, max(1, int(float(row[measure] / maximum) * 5))) if row[measure] else 0
        rows.append(row)
    wasted_rows = [{'unit': dict(units).get(unit, unit), 'quantity': amount} for unit, amount in wasted_by_unit.items()]
    return rows, wasted_rows


@login_required
def impact(request):
    org = None if request.user.is_staff else organisation(request.user)
    listings = Listing.objects.select_related('provider').all()
    collections = FoodRequest.objects.filter(status='collected').select_related('listing', 'recipient', 'listing__provider')
    if org:
        listings = listings.filter(provider=org) if org.role == 'provider' else listings.filter(pk__in=FoodRequest.objects.filter(recipient=org).values('listing_id'))
        collections = collections.filter(listing__provider=org) if org.role == 'provider' else collections.filter(recipient=org)
    form_errors = []
    from datetime import date
    for key, lookup in [('start', 'gte'), ('end', 'lte')]:
        value = request.GET.get(key)
        if value:
            try: day = date.fromisoformat(value)
            except ValueError: form_errors.append('Use a valid date in the date filter.')
            else:
                listings = listings.filter(**{f'created__date__{lookup}': day})
                collections = collections.filter(**{f'collected_at__date__{lookup}': day})
    pathway = request.GET.get('pathway', '')
    if pathway in dict(PATHWAYS):
        listings = listings.filter(pathway=pathway)
        collections = collections.filter(listing__pathway=pathway)
    measure = request.GET.get('measure', 'listed')
    if measure not in {'listed', 'collected', 'wasted'}: measure = 'listed'
    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="foodloop-confirmed-collections.csv"'
        writer = csv.writer(response)
        writer.writerow(['Food', 'Pathway', 'Quantity', 'Unit', 'Confirmed weight (kg)', 'Donor', 'Recipient', 'Confirmed at (CAT)'])
        for item in collections:
            def safe(value):
                value = str(value)
                return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value
            writer.writerow([safe(item.listing.name), item.listing.get_pathway_display(), item.confirmed_quantity or item.quantity, item.listing.unit, item.confirmed_weight_kg or '', safe(item.listing.provider.name), safe(item.recipient.name), timezone.localtime(item.collected_at or item.updated).isoformat()])
        return response
    rows = []
    units = Listing._meta.get_field('unit').choices
    for unit, label in units:
        rows.append({'unit': label, 'listed': listings.filter(unit=unit).aggregate(n=Sum('quantity'))['n'] or 0, 'collected': collections.filter(listing__unit=unit).aggregate(n=Sum('confirmed_quantity'))['n'] or 0})
    kg = collections.aggregate(n=Sum('confirmed_weight_kg'))['n'] or Decimal('0')
    human = collections.filter(listing__pathway='human').aggregate(n=Sum('confirmed_weight_kg'))['n'] or Decimal('0')
    meal_weight = platform_setting('meal_weight_kg', settings.MEAL_WEIGHT_KG, Decimal)
    meal_weight = meal_weight if meal_weight > 0 else Decimal('0.4')
    totals = [{'label': label, 'kg': collections.filter(listing__pathway=code).aggregate(n=Sum('confirmed_weight_kg'))['n'] or Decimal('0')} for code, label in PATHWAYS]
    pathway_rows = []
    for code, label in PATHWAYS:
        for unit, unit_label in units:
            listed = listings.filter(pathway=code, unit=unit).aggregate(n=Sum('quantity'))['n'] or 0
            recovered = collections.filter(listing__pathway=code, listing__unit=unit).aggregate(n=Sum('confirmed_quantity'))['n'] or 0
            if listed or recovered: pathway_rows.append({'pathway': label, 'unit': unit_label, 'listed': listed, 'collected': recovered})
    area_rows, wasted_rows = build_area_impact_rows(listings, collections, measure)
    co2 = Decimal(kg) * Decimal(settings.CO2E_KG_PER_KG) if settings.CO2E_KG_PER_KG and settings.CO2E_SOURCE else None
    return render(request, 'impact.html', {'rows': rows, 'pathway_rows': pathway_rows, 'totals': totals, 'kg': kg, 'meals': int(Decimal(human)/meal_weight), 'meal_weight': meal_weight, 'co2': co2, 'co2_factor': settings.CO2E_KG_PER_KG, 'co2_source': settings.CO2E_SOURCE, 'pathways': PATHWAYS, 'pathway': pathway, 'start': request.GET.get('start', ''), 'end': request.GET.get('end', ''), 'form_errors': form_errors, 'area_rows': area_rows, 'measure': measure, 'area_measure': measure, 'wasted_rows': wasted_rows})

@login_required
def impact_statement(request):
    org = organisation(request.user)
    if org.role != 'provider' or org.status != 'approved': raise PermissionDenied
    from datetime import date
    collections = FoodRequest.objects.filter(status='collected', listing__provider=org).select_related('listing', 'recipient')
    start = request.GET.get('start', '')
    end = request.GET.get('end', '')
    try:
        if start: collections = collections.filter(collected_at__date__gte=date.fromisoformat(start))
        if end: collections = collections.filter(collected_at__date__lte=date.fromisoformat(end))
    except ValueError:
        messages.error(request, 'Choose valid dates for the statement period.')
        return redirect('impact_statement')
    rows=[]
    total_kg=Decimal('0')
    total_meals=0
    total_value=Decimal('0')
    value_configured=True
    meal_weight=platform_setting('meal_weight_kg', settings.MEAL_WEIGHT_KG, Decimal)
    if meal_weight <= 0: meal_weight=Decimal('0.4')
    for code,label in PATHWAYS:
        kg=collections.filter(listing__pathway=code).aggregate(n=Sum('confirmed_weight_kg'))['n'] or Decimal('0')
        key=f'value_per_kg_{code}'
        setting_default=getattr(settings, f'IMPACT_VALUE_PER_KG_{code.upper()}', '')
        raw=platform_setting(key, setting_default, str)
        try: rate=Decimal(raw) if raw not in (None, '') else None
        except Exception: rate=None
        if rate is not None and rate < 0: rate=None
        value=kg*rate if rate is not None else None
        if rate is None: value_configured=False
        rows.append({'pathway':label,'kg':kg,'rate':rate,'value':value})
        total_kg += kg
        if code=='human': total_meals=int(kg/meal_weight)
        if value is not None: total_value += value
    return render(request,'impact_statement.html',{'org':org,'rows':rows,'total_kg':total_kg,'total_meals':total_meals,'total_value':total_value,'value_configured':value_configured,'meal_weight':meal_weight,'start':start,'end':end,'collection_count':collections.count()})

@login_required
def listing_photo(request, pk):
    listing = get_object_or_404(visible(request.user), pk=pk)
    if not listing.photo: return HttpResponseNotFound('No photo has been added.')
    try: photo = listing.photo.open('rb')
    except (OSError, FileNotFoundError): return HttpResponseNotFound('This photo is unavailable.')
    response = FileResponse(photo, content_type='image/jpeg', filename='food.jpg')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response

@login_required
def profile(request):
    org = None if request.user.is_staff else organisation(request.user)
    form = ProfileForm(request.POST or None, instance=request.user)
    prefs = PreferencesForm(request.POST or None, initial={'usual_quantity': org.usual_quantity, 'usual_unit': org.usual_unit}) if org and org.role != 'provider' else None
    if request.method == 'POST' and form.is_valid() and (prefs is None or prefs.is_valid()):
        with transaction.atomic():
            form.save()
            EmailPreferences.objects.update_or_create(user=request.user, defaults={'enabled': form.cleaned_data['email_notifications']})
            if prefs:
                org.usual_quantity = prefs.cleaned_data['usual_quantity']
                org.usual_unit = prefs.cleaned_data['usual_unit']
                org.save(update_fields=['usual_quantity', 'usual_unit'])
            AuditLog.objects.create(actor=request.user, action='Updated own profile and matching preferences')
        messages.success(request, 'Your profile was updated.')
        return redirect('profile')
    return render(request, 'profile.html', {'form': form, 'preferences': prefs, 'org': org})

@login_required
@require_POST
@transaction.atomic
def collection_notes(request, pk):
    org = organisation(request.user)
    item = get_object_or_404(FoodRequest.objects.select_for_update().select_related('listing'), pk=pk)
    if org.status != 'approved' or org.pk not in [item.listing.provider_id, item.recipient_id]: raise PermissionDenied
    form = CollectionNotesForm(request.POST)
    if form.is_valid():
        item.collection_notes = form.cleaned_data['notes']
        item.save(update_fields=['collection_notes'])
        AuditLog.objects.create(actor=request.user, action=f'Request {pk}: updated collection notes')
        messages.success(request, 'Collection notes saved.')
    else: messages.error(request, 'Keep collection notes within 2000 characters.')
    return redirect('detail', pk=item.listing_id)


@login_required
@require_POST
def save_push_subscription(request):
    import json
    from urllib.parse import urlparse
    if not settings.WEB_PUSH_ENABLED:
        return JsonResponse({'error':'Phone notifications are not configured yet.'},status=503)
    try:
        data=json.loads(request.body)
        endpoint=data['endpoint']; keys=data['keys']; p256dh=keys['p256dh']; auth=keys['auth']
        parsed=urlparse(endpoint)
        if parsed.scheme!='https' or not parsed.netloc or not p256dh or not auth or len(endpoint)>2000:
            raise ValueError
    except (ValueError,KeyError,TypeError):
        return JsonResponse({'error':'The phone subscription is invalid.'},status=400)
    PushSubscription.objects.update_or_create(endpoint=endpoint,defaults={'user':request.user,'p256dh':p256dh,'auth':auth})
    return JsonResponse({'saved':True})

@login_required
@require_POST
def remove_push_subscription(request):
    import json
    try: endpoint=json.loads(request.body)['endpoint']
    except (ValueError,KeyError,TypeError): return JsonResponse({'error':'The phone subscription is invalid.'},status=400)
    PushSubscription.objects.filter(user=request.user,endpoint=endpoint).delete()
    return JsonResponse({'removed':True})


@login_required
@require_POST
def test_phone_notification(request):
    if not settings.WEB_PUSH_ENABLED:
        return JsonResponse({'error': 'Phone notifications are not configured yet.'}, status=503)
    if not PushSubscription.objects.filter(user=request.user).exists():
        return JsonResponse({'error': 'Enable phone notifications on this device first.'}, status=409)
    from django.core.cache import cache
    if not cache.add(f'push-test-{request.user.pk}', True, 30):
        return JsonResponse({'error': 'Wait 30 seconds before sending another test.'}, status=429)
    Notification.objects.create(user=request.user, message='Your FoodLoop phone notification test. If this appeared in your phone notification tray, alerts are working.')
    return JsonResponse({'queued': True})
