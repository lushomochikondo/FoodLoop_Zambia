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
from django.http import FileResponse, HttpResponse
import csv
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponseNotFound
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import CollectionNotesForm, DecisionForm, FlagForm, ListingForm, PreferencesForm, ProfileForm, RequestForm
from .forms import SignupForm
from .models import AuditLog, FlagReport, FoodRequest, Listing, Notification, Organisation, PATHWAYS
from .models import Membership
from .models import EmailPreferences
from .services import change_request, close_listing, end_request, expire_requests, notify, organisation, request_food, review_flag, verify_organisation
from .matching import rank_listing
from .services import delete_listing as delete_listing_record

def signup(request):
    if request.user.is_authenticated: return redirect('home')
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save(commit=False)
                user.email = form.cleaned_data['email']
                user.first_name = form.cleaned_data['contact_name'][:150]
                user.is_staff = False
                user.is_superuser = False
                user.save()
                account_type = form.cleaned_data['account_type']
                org = Organisation.objects.create(name=form.cleaned_data['organisation_name'], role=account_type if account_type in ['provider', 'recipient'] else 'recovery', pathway=account_type if account_type in ['feed', 'compost'] else 'human', status='pending', contact_name=form.cleaned_data['contact_name'], contact_email=form.cleaned_data['email'], phone=form.cleaned_data['phone'], area=form.cleaned_data['area'], physical_address=form.cleaned_data['physical_address'], registration_reference=form.cleaned_data['registration_reference'], activity_description=form.cleaned_data['activity_description'], handling_capacity=form.cleaned_data['handling_capacity'], authorised_representative=form.cleaned_data['authorised_representative'], terms_accepted=True)
                Membership.objects.create(user=user, organisation=org)
                EmailPreferences.objects.create(user=user, enabled=form.cleaned_data['email_updates'])
                AuditLog.objects.create(actor=user, action=f'Organisation {org.pk}: self-registration submitted for verification')
                Notification.objects.create(user=user, message='Welcome to FoodLoop. Your organisation is awaiting administrator verification.')
                for admin in User.objects.filter(is_staff=True, is_active=True):
                    Notification.objects.create(user=admin, message=f'New organisation awaiting verification: {org.name}'[:240])
        except IntegrityError:
            form.add_error('username', 'This username was just registered. Choose another and try again.')
        else:
            login(request, user)
            messages.success(request, 'Account created. Your organisation is awaiting verification; you can list or request food once approved.')
            return redirect('home')
    return render(request, 'signup.html', {'form': form})

def visible(user):
    listings = Listing.objects.select_related('provider')
    if user.is_staff: return listings
    org = organisation(user)
    if org.role == 'provider': return listings.filter(provider=org)
    listings = listings.filter(provider__status='approved', pathway=org.pathway).filter(~Q(status='deleted')|Q(requests__recipient=org)).distinct()
    return listings.exclude(condition='spoiled') if org.pathway == 'human' else listings

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
            match = rank_listing(listing, org)
            if match:
                listing.match_score, listing.match_reason = match
                ranked.append(listing)
        cards = sorted(ranked, key=lambda item: (-item.match_score, item.deadline, item.pk))
    collected = requests.filter(status='collected', listing__unit='kg')
    kg = collected.aggregate(n=Sum('confirmed_quantity'))['n'] or 0
    human = collected.filter(listing__pathway='human').aggregate(n=Sum('confirmed_quantity'))['n'] or 0
    pathway_totals = []
    for code, label in PATHWAYS:
        total = collected.filter(listing__pathway=code).aggregate(n=Sum('confirmed_quantity'))['n'] or 0
        pathway_totals.append({'code': code, 'label': label, 'kg': total, 'percent': round(float(total / kg * 100)) if kg else 0})
    own_listings = visible(request.user)
    if org and org.role != 'provider': own_listings = own_listings.filter(pk__in=requests.values('listing_id'))
    listed_kg = own_listings.filter(unit='kg').aggregate(n=Sum('quantity'))['n'] or 0
    return {'org': org, 'listings': cards, 'requests': requests.order_by('-created'), 'kg': kg, 'listed_kg': listed_kg, 'availability': availability, 'meals': int(Decimal(human) / Decimal(settings.MEAL_WEIGHT_KG)), 'meal_weight': settings.MEAL_WEIGHT_KG, 'area': area, 'collection_count': requests.filter(status='collected').count(), 'search': search, 'pathway': pathway, 'pathways': PATHWAYS, 'pathway_totals': pathway_totals, 'pending_count': requests.filter(status='pending').count(), 'listing_count': len(cards)}

@login_required
def home(request):
    context=workspace_context(request)
    sort=request.GET.get('sort','recommended')
    if sort=='newest': context['listings'].sort(key=lambda item:item.created,reverse=True)
    elif sort=='deadline': context['listings'].sort(key=lambda item:item.deadline)
    context['sort']=sort
    return render(request,'exchange.html',context)

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
    daily=requests.filter(status='collected',listing__unit='kg',collected_at__date__gte=start).annotate(day=TruncDate('collected_at')).values('day').annotate(quantity=Sum('confirmed_quantity'))
    values={row['day']:row['quantity'] for row in daily}
    maximum=max(values.values(),default=Decimal('1')) or Decimal('1')
    context['daily_collections']=[{'day':start+timedelta(days=i),'quantity':values.get(start+timedelta(days=i),0),'height':round(float(values.get(start+timedelta(days=i),0)/maximum)*100)} for i in range(7)]
    from .dashboard_data import visual_context
    context.update(visual_context(requests,context['pathway_totals']))
    return render(request,'dashboard.html',context)

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
            messages.success(request, 'Request submitted. Track its status under Menu / Requests & collections. Stock is reserved when the provider accepts.')
            return redirect('home')
        except ValidationError as exc: form.add_error(None, exc)
    history = listing.requests.select_related('recipient').prefetch_related('events')
    if org and not provider: history = history.filter(recipient=org)
    form.fields['quantity'].widget.attrs.update({'max': str(listing.remaining), 'step':'0.01'})
    return render(request, 'detail.html', {'org':org,'listing': listing, 'form': form, 'show_private': provider or accepted or request.user.is_staff, 'can_request': org and org.role != 'provider' and org.status == 'approved' and listing.available, 'is_provider': provider, 'can_edit': provider and listing.available and listing.allocated == 0, 'can_delete':provider and org.status == 'approved' and listing.status != 'deleted', 'can_flag': org and org.role != 'provider' and org.status == 'approved', 'history': history, 'requests':history,'return_to_listing':True,'flag_form': FlagForm()})

@login_required
@require_POST
def transition(request, pk, action):
    try: item = change_request(request.user, pk, action)
    except FoodRequest.DoesNotExist: return HttpResponseNotFound()
    except ValidationError as exc: messages.error(request, '; '.join(exc.messages))
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
    try: close_listing(request.user, pk, 'withdrawn', 'Withdrawn by the provider.')
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
        if not ids or decision not in ['approved', 'rejected', 'suspended'] or len(reason) < 3 or len(reason) > 1000:
            messages.error(request, 'Select at least one organisation, choose a decision and enter a reason of at least 3 characters.')
        else:
            try:
                with transaction.atomic():
                    pending_ids = list(Organisation.objects.select_for_update().filter(pk__in=ids, status='pending').values_list('pk', flat=True))
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
    return render(request, 'moderation.html', {'organisations': Organisation.objects.order_by('status', 'name'), 'flags': FlagReport.objects.select_related('listing', 'reporter').filter(status='pending'), 'moderation_listings': Listing.objects.filter(status='available').select_related('provider'), 'audit': AuditLog.objects.select_related('actor').order_by('-created', '-pk')[:60], 'decision_form': form})

@login_required
def impact(request):
    org = None if request.user.is_staff else organisation(request.user)
    listings = Listing.objects.all()
    collections = FoodRequest.objects.filter(status='collected').select_related('listing', 'recipient')
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
    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="foodloop-confirmed-collections.csv"'
        writer = csv.writer(response)
        writer.writerow(['Food', 'Pathway', 'Quantity', 'Unit', 'Provider', 'Recipient', 'Confirmed at (CAT)'])
        for item in collections:
            # Protect spreadsheet exports from interpreting organisation/user input as formulas.
            def safe(value):
                value = str(value)
                return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value
            writer.writerow([safe(item.listing.name), item.listing.get_pathway_display(), item.confirmed_quantity or item.quantity, item.listing.unit, safe(item.listing.provider.name), safe(item.recipient.name), timezone.localtime(item.collected_at or item.updated).isoformat()])
        return response
    rows = []
    for unit, label in Listing._meta.get_field('unit').choices:
        rows.append({'unit': label, 'listed': listings.filter(unit=unit).aggregate(n=Sum('quantity'))['n'] or 0, 'collected': collections.filter(listing__unit=unit).aggregate(n=Sum('confirmed_quantity'))['n'] or 0})
    kg = collections.filter(listing__unit='kg').aggregate(n=Sum('confirmed_quantity'))['n'] or 0
    human = collections.filter(listing__unit='kg', listing__pathway='human').aggregate(n=Sum('confirmed_quantity'))['n'] or 0
    totals = [{'label': label, 'kg': collections.filter(listing__unit='kg', listing__pathway=code).aggregate(n=Sum('confirmed_quantity'))['n'] or 0} for code, label in PATHWAYS]
    pathway_rows = []
    for code, label in PATHWAYS:
        for unit, unit_label in Listing._meta.get_field('unit').choices:
            listed = listings.filter(pathway=code, unit=unit).aggregate(n=Sum('quantity'))['n'] or 0
            recovered = collections.filter(listing__pathway=code, listing__unit=unit).aggregate(n=Sum('confirmed_quantity'))['n'] or 0
            if listed or recovered: pathway_rows.append({'pathway': label, 'unit': unit_label, 'listed': listed, 'collected': recovered})
    co2 = Decimal(kg) * Decimal(settings.CO2E_KG_PER_KG) if settings.CO2E_KG_PER_KG and settings.CO2E_SOURCE else None
    return render(request, 'impact.html', {'rows': rows, 'pathway_rows': pathway_rows, 'totals': totals, 'kg': kg, 'meals': int(Decimal(human)/Decimal(settings.MEAL_WEIGHT_KG)), 'meal_weight': settings.MEAL_WEIGHT_KG, 'co2': co2, 'co2_factor': settings.CO2E_KG_PER_KG, 'co2_source': settings.CO2E_SOURCE, 'pathways': PATHWAYS, 'pathway': pathway, 'start': request.GET.get('start', ''), 'end': request.GET.get('end', ''), 'form_errors': form_errors})

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
