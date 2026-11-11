from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from .storage import private_evidence_storage

PATHWAYS = [('human', 'Human Consumption'), ('feed', 'Animal Feed'), ('compost', 'Composting / Organic Recovery')]
POSITIVE = MinValueValidator(Decimal('0.01'))

class Organisation(models.Model):
    name = models.CharField(max_length=160)
    role = models.CharField(max_length=20, choices=[('provider', 'Donor'), ('recipient', 'Beneficiary'), ('recovery', 'Recovery partner')])
    pathway = models.CharField(max_length=10, choices=PATHWAYS, default='human')
    area = models.CharField(max_length=100)
    phone = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=15, choices=[('draft', 'Application draft'), ('pending', 'Pending review'), ('needs_info', 'More information requested'), ('approved', 'Approved'), ('rejected', 'Declined'), ('suspended', 'Suspended')], default='pending')
    verification_reason = models.TextField(blank=True)
    registration_reference = models.CharField(max_length=160, blank=True)
    physical_address = models.CharField(max_length=240, blank=True)
    contact_name = models.CharField(max_length=140, blank=True)
    contact_email = models.EmailField(blank=True)
    activity_description = models.TextField(blank=True, help_text='Who the organisation serves, animals kept, or processing activity.')
    handling_capacity = models.TextField(blank=True)
    authorised_representative = models.BooleanField(default=False)
    terms_accepted = models.BooleanField(default=False)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    usual_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=10, validators=[POSITIVE])
    usual_unit = models.CharField(max_length=10, default='kg', choices=[('kg', 'Kilograms'), ('litres', 'Litres'), ('pieces', 'Pieces'), ('trays', 'Trays'), ('bags', 'Bags')])
    def __str__(self): return self.name

class BeneficiaryApplication(models.Model):
    PROGRAMMES = [
        ('training_skills', 'Training / skills development centre'),
        ('healthcare', 'Health-care organisation'),
        ('tertiary', 'Tertiary institution'),
        ('early_childhood', 'Early childhood development centre'),
        ('disability_care', 'Disability-care organisation'),
        ('school', 'Primary, secondary or special-needs school'),
        ('shelter_rehab', 'Shelter / rehabilitation centre'),
        ('aged_care', 'Aged-care organisation'),
        ('orphans_vulnerable_children', 'Orphans and vulnerable children programme'),
        ('community_kitchen', 'Community kitchen'),
        ('livestock_farmer', 'Livestock farmer / animal feed'),
        ('composting_operator', 'Composting / organic recovery'),
    ]
    @staticmethod
    def pathway_for_programme(programme):
        return {'livestock_farmer': 'feed', 'composting_operator': 'compost'}.get(programme, 'human')

    LEGAL_FORMS = [('ngo','NGO'),('society','Society / community organisation'),('company','Company / trust'),('community','Informal community group'),('other','Other / unsure')]
    EVIDENCE = [('yes','Yes'),('applied','Applied / being renewed'),('not_required','Not applicable to our activities')]
    organisation = models.OneToOneField(Organisation, on_delete=models.CASCADE, related_name='beneficiary_application')
    programme_type = models.CharField(max_length=32, choices=PROGRAMMES, blank=True)
    eligibility_rules_version = models.CharField(max_length=40, blank=True)
    eligibility_accepted_at = models.DateTimeField(null=True, blank=True)
    legal_form = models.CharField(max_length=20, choices=LEGAL_FORMS, blank=True)
    people_served = models.PositiveIntegerField(null=True, blank=True)
    feeding_days_per_week = models.PositiveSmallIntegerField(null=True, blank=True)
    years_operating = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    health_clearance = models.CharField(max_length=20, choices=EVIDENCE, blank=True)
    health_clearance_note = models.CharField(max_length=300, blank=True)
    food_handler_evidence = models.CharField(max_length=20, choices=EVIDENCE, blank=True)
    food_handler_note = models.CharField(max_length=300, blank=True)
    storage_description = models.TextField(blank=True)
    governance_description = models.TextField(blank=True)
    community_references = models.TextField(blank=True)
    beneficiary_records = models.BooleanField(default=False)
    no_resale_agreement = models.BooleanField(default=False)
    nondiscrimination_agreement = models.BooleanField(default=False)
    inspection_consent = models.BooleanField(default=False)
    information_accuracy = models.BooleanField(default=False)
    has_food_transport = models.BooleanField(default=False)
    has_performance_indicators = models.BooleanField(default=False)
    has_financial_records = models.BooleanField(default=False)
    staff_or_volunteers = models.PositiveSmallIntegerField(null=True, blank=True)
    additional_context = models.TextField(blank=True)
    registration_document = models.FileField(upload_to='beneficiary/registration/', blank=True, storage=private_evidence_storage, validators=[FileExtensionValidator(['pdf','jpg','jpeg','png'])])
    health_document = models.FileField(upload_to='beneficiary/health/', blank=True, storage=private_evidence_storage, validators=[FileExtensionValidator(['pdf','jpg','jpeg','png'])])
    supporting_document = models.FileField(upload_to='beneficiary/supporting/', blank=True, storage=private_evidence_storage, validators=[FileExtensionValidator(['pdf','jpg','jpeg','png'])])
    submitted_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self): return f'Beneficiary application: {self.organisation.name}'

class Membership(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organisation = models.ForeignKey(Organisation, on_delete=models.PROTECT)

class Listing(models.Model):
    provider = models.ForeignKey(Organisation, on_delete=models.PROTECT, verbose_name='donor')
    name = models.CharField(max_length=140)
    photo = models.ImageField(upload_to='listings/%Y/%m/', blank=True)
    listing_type = models.CharField(max_length=15, choices=[('donation', 'Donation (free)')], default='donation')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[POSITIVE])
    allocated = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit = models.CharField(max_length=10, choices=[('kg', 'Kilograms'), ('litres', 'Litres'), ('pieces', 'Pieces'), ('trays', 'Trays'), ('bags', 'Bags')], default='kg')
    pathway = models.CharField(max_length=10, choices=PATHWAYS)
    condition = models.CharField(max_length=30, choices=[('fresh', 'Fresh'), ('cooked', 'Cooked and freshly prepared'), ('sealed', 'Packaged, sealed'), ('near_expiry', 'Near expiry'), ('damaged', 'Damaged packaging'), ('spoiled', 'Overripe or spoiled (not for people)')])
    area = models.CharField(max_length=100)
    address = models.CharField(max_length=240)
    pickup_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    pickup_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    share_pickup_pin = models.BooleanField(default=False, help_text='Allow eligible organisations to see the exact pickup pin before requesting. The written address and phone remain private until acceptance.')
    access_surface = models.CharField('Pickup access road surface', max_length=20, blank=True, choices=[('', 'Unknown / not reported'), ('asphalt', 'Tarred / asphalt / bituminous'), ('gravel', 'Gravel'), ('dirt', 'Dirt / earth'), ('concrete', 'Concrete'), ('paved', 'Other paved surface'), ('mixed', 'Mixed surfaces')])
    access_condition = models.CharField('Pickup access road condition', max_length=20, blank=True, choices=[('', 'Unknown / not reported'), ('good', 'Good'), ('fair', 'Fair'), ('rough', 'Rough'), ('very_rough', 'Very rough'), ('impassable', 'Currently impassable')])
    access_notes = models.CharField('Pickup access notes', max_length=600, blank=True, help_text='Describe the final approach, potholes, wet-weather access or vehicle requirements. Shared after acceptance. Example: final 600 m is gravel and becomes muddy after rain.')
    access_reported_at = models.DateTimeField(null=True, blank=True, editable=False)

    notes = models.TextField(blank=True)
    deadline = models.DateTimeField()
    safety_acknowledged = models.BooleanField(default=False)
    status = models.CharField(max_length=15, choices=[('available', 'Available'), ('withdrawn', 'Withdrawn'), ('removed', 'Removed'), ('deleted', 'Deleted')], default='available')
    deleted_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    reoffer_second_wave_at = models.DateTimeField(null=True, blank=True)
    @property
    def remaining(self): return self.quantity - self.allocated
    @property
    def available(self): return self.status == 'available' and self.deadline > timezone.now() and self.remaining > 0 and self.provider.status == 'approved'
    @property
    def collected_quantity(self):
        if hasattr(self, '_collected_total'):
            return self._collected_total or Decimal('0')
        return self.requests.filter(status='collected').aggregate(total=models.Sum('quantity'))['total'] or Decimal('0')
    @property
    def reserved_quantity(self):
        return max(Decimal('0'), self.allocated - self.collected_quantity)
    @property
    def display_status(self):
        if self.status != 'available': return self.get_status_display()
        if self.remaining <= 0:
            return 'Exhausted' if self.collected_quantity >= self.quantity else 'Fully reserved'
        if self.deadline <= timezone.now(): return 'Expired'
        return 'Available'
    @property
    def status_key(self):
        if self.status != 'available': return self.status
        if self.remaining <= 0:
            return 'exhausted' if self.collected_quantity >= self.quantity else 'allocated'
        if self.deadline <= timezone.now(): return 'expired'
        return 'available'
    def clean(self):
        errors = {}
        if self.pathway == 'human' and self.condition == 'spoiled': errors['condition'] = 'This condition is unsuitable for human consumption.'
        if not self.pk and self.deadline and self.deadline <= timezone.now(): errors['deadline'] = 'Choose a future deadline (CAT).'
        if not self.safety_acknowledged: errors['safety_acknowledged'] = 'Please acknowledge your responsibility before publishing.'
        if errors: raise ValidationError(errors)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gt=0), name='positive_listing'), models.CheckConstraint(condition=models.Q(allocated__gte=0) & models.Q(allocated__lte=models.F('quantity')), name='allocation_bounds'), models.CheckConstraint(condition=(models.Q(pickup_latitude__isnull=True, pickup_longitude__isnull=True) | models.Q(pickup_latitude__isnull=False, pickup_longitude__isnull=False)), name='pickup_coordinates_together'), models.CheckConstraint(condition=models.Q(pickup_latitude__isnull=True) | models.Q(pickup_latitude__gte=-90, pickup_latitude__lte=90), name='pickup_latitude_bounds'), models.CheckConstraint(condition=models.Q(pickup_longitude__isnull=True) | models.Q(pickup_longitude__gte=-180, pickup_longitude__lte=180), name='pickup_longitude_bounds')]
    def __str__(self): return self.name

class FoodRequest(models.Model):
    listing = models.ForeignKey(Listing, related_name='requests', on_delete=models.PROTECT)
    recipient = models.ForeignKey(Organisation, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[POSITIVE])
    status = models.CharField(max_length=20, default='pending', choices=[(v, 'Ready for Collection' if v == 'ready' else 'No-show' if v == 'no_show' else v.replace('_', ' ').title()) for v in ['pending', 'accepted', 'ready', 'collected', 'declined', 'cancelled', 'expired', 'no_show']])
    provider_confirmed = models.DateTimeField(null=True, blank=True)
    recipient_confirmed = models.DateTimeField(null=True, blank=True)
    confirmed_quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    confirmed_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    collection_notes = models.TextField(blank=True)
    decision_time = models.DateTimeField(null=True, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    @property
    def proposed_weight_kg(self):
        from django.conf import settings
        if self.listing.unit == 'kg': return self.confirmed_weight_kg or self.quantity
        if self.listing.unit == 'litres':
            from .services import platform_setting
            factor = platform_setting('litre_to_kg_factor', getattr(settings, 'LITRE_TO_KG_FACTOR', 1), Decimal)
            return self.confirmed_weight_kg or self.quantity * factor
        return self.confirmed_weight_kg or ''
    @property
    def collector_handover_code(self):
        from .services import handover_code_for
        return handover_code_for(self)
    @property
    def collector_handover_qr(self):
        import base64
        from io import BytesIO
        import qrcode
        from qrcode.image.svg import SvgPathImage
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=7, border=3)
        qr.add_data(self.collector_handover_code)
        qr.make(fit=True)
        output = BytesIO()
        qr.make_image(image_factory=SvgPathImage, fill_color='#1F5E3B', back_color='#FFFFFF').save(output)
        return base64.b64encode(output.getvalue()).decode('ascii')
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gt=0), name='positive_request'), models.CheckConstraint(condition=models.Q(confirmed_weight_kg__isnull=True) | models.Q(confirmed_weight_kg__gt=0), name='positive_confirmed_weight')]

class HandoverCode(models.Model):
    request = models.OneToOneField(FoodRequest, on_delete=models.CASCADE, related_name='handover_code')
    code_hash = models.CharField(max_length=256)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    verified_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

class PlatformSetting(models.Model):
    key = models.CharField(max_length=80, unique=True)
    value = models.CharField(max_length=160, blank=True)
    description = models.CharField(max_length=240, blank=True)
    updated = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['key']
    def __str__(self): return f'{self.key} = {self.value}'

class ListingReoffer(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='reoffers')
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    wave = models.PositiveSmallIntegerField()
    created = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['listing', 'organisation', 'wave'], name='listing_reoffer_once')]

class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    action = models.CharField(max_length=240)
    created = models.DateTimeField(auto_now_add=True)

class RequestEvent(models.Model):
    request = models.ForeignKey(FoodRequest, related_name='events', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=20)
    description = models.CharField(max_length=240)
    created = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['created', 'pk']

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.CharField(max_length=240)
    listing = models.ForeignKey(Listing, on_delete=models.SET_NULL, null=True, blank=True)
    read = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_attempts = models.PositiveSmallIntegerField(default=0, db_default=0)
    email_last_attempt_at = models.DateTimeField(null=True, blank=True)
    email_next_retry_at = models.DateTimeField(null=True, blank=True)
    email_claim_token = models.CharField(max_length=32, blank=True, default='', db_default='')
    email_claim_expires_at = models.DateTimeField(null=True, blank=True)
    email_skipped_at = models.DateTimeField(null=True, blank=True)
    email_last_error = models.CharField(max_length=160, blank=True, default='', db_default='')
    event_key = models.CharField(max_length=120, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created', '-pk']
        constraints = [models.UniqueConstraint(fields=['user', 'event_key'], name='notification_event_once')]

class EmailPreferences(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='email_preferences')
    enabled = models.BooleanField(default=True)

class FlagReport(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.PROTECT)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField(max_length=2000)
    status = models.CharField(max_length=15, default='pending', choices=[('pending', 'Awaiting review'), ('dismissed', 'Dismissed'), ('removed', 'Listing removed')])
    outcome = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='reviewed_flags', on_delete=models.PROTECT, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

class DropOffLocation(models.Model):
    name = models.CharField(max_length=160)
    area = models.CharField(max_length=100)
    address = models.CharField(max_length=240)
    opening_hours = models.CharField(max_length=240, blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)
    published = models.BooleanField(default=False, help_text='Publish only a confirmed public drop-off location. Listing pickup addresses are separate and private.')
    class Meta:
        ordering = ['area','name']
    def __str__(self): return self.name

class NewsArticle(models.Model):
    category = models.CharField(max_length=20, choices=[('news', 'News'), ('success_story', 'Success story')], default='news')
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    summary = models.CharField(max_length=400)
    body = models.TextField()
    image = models.ImageField(upload_to='news/%Y/%m/', blank=True)
    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['-published_at','-pk']
    def __str__(self): return self.title

class StorySubmission(models.Model):
    STATUS_CHOICES = [('pending', 'Awaiting review'), ('published', 'Published'), ('declined', 'Declined')]
    organisation = models.ForeignKey(Organisation, on_delete=models.PROTECT, related_name='story_submissions')
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='story_submissions')
    title = models.CharField(max_length=200)
    summary = models.CharField(max_length=400)
    body = models.TextField()
    image = models.ImageField(upload_to='story-submissions/%Y/%m/', blank=True)
    consent_confirmed = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=400, blank=True)
    news_article = models.OneToOneField(NewsArticle, on_delete=models.SET_NULL, null=True, blank=True, related_name='source_submission')
    class Meta:
        ordering = ['-submitted_at', '-pk']
    def __str__(self): return f'{self.title} — {self.organisation.name}'

class ContactMessage(models.Model):
    name = models.CharField(max_length=140)
    email = models.EmailField()
    subject = models.CharField(max_length=160)
    message = models.TextField(max_length=3000)
    created = models.DateTimeField(auto_now_add=True)
    reviewed = models.BooleanField(default=False)
    def __str__(self): return f'{self.subject} — {self.name}'
    class Meta:
        ordering = ['-created', '-pk']


class PushSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.URLField(max_length=2000, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

class PushDelivery(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='push_deliveries')
    subscription = models.ForeignKey(PushSubscription, on_delete=models.CASCADE, related_name='deliveries')
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=120, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    claim_token = models.CharField(max_length=32, blank=True, default='')
    claim_expires_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['notification','subscription'], name='push_delivery_once')]


class ScheduledJobState(models.Model):
    name = models.CharField(max_length=80, unique=True)
    claim_token = models.CharField(max_length=32, blank=True, default='')
    claim_expires_at = models.DateTimeField(null=True, blank=True)
    last_started_at = models.DateTimeField(null=True, blank=True)
    last_completed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=160, blank=True, default='')
