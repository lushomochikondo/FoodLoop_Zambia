from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

PATHWAYS = [('human', 'Human Consumption'), ('feed', 'Animal Feed'), ('compost', 'Composting / Organic Recovery')]
POSITIVE = MinValueValidator(Decimal('0.01'))

class Organisation(models.Model):
    name = models.CharField(max_length=160)
    role = models.CharField(max_length=20, choices=[('provider', 'Provider'), ('recipient', 'Recipient'), ('recovery', 'Recovery partner')])
    pathway = models.CharField(max_length=10, choices=PATHWAYS, default='human')
    area = models.CharField(max_length=100)
    phone = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=15, choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('suspended', 'Suspended')], default='pending')
    verification_reason = models.TextField(blank=True)
    registration_reference = models.CharField(max_length=160, blank=True)
    physical_address = models.CharField(max_length=240, blank=True)
    contact_name = models.CharField(max_length=140, blank=True)
    contact_email = models.EmailField(blank=True)
    activity_description = models.TextField(blank=True, help_text='Who the organisation serves, animals kept, or processing activity.')
    handling_capacity = models.TextField(blank=True)
    authorised_representative = models.BooleanField(default=False)
    terms_accepted = models.BooleanField(default=False)
    usual_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=10, validators=[POSITIVE])
    usual_unit = models.CharField(max_length=10, default='kg', choices=[('kg', 'Kilograms'), ('litres', 'Litres'), ('pieces', 'Pieces'), ('trays', 'Trays'), ('bags', 'Bags')])
    def __str__(self): return self.name

class Membership(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organisation = models.ForeignKey(Organisation, on_delete=models.PROTECT)

class Listing(models.Model):
    provider = models.ForeignKey(Organisation, on_delete=models.PROTECT)
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
    notes = models.TextField(blank=True)
    deadline = models.DateTimeField()
    safety_acknowledged = models.BooleanField(default=False)
    status = models.CharField(max_length=15, choices=[('available', 'Available'), ('withdrawn', 'Withdrawn'), ('removed', 'Removed'), ('deleted', 'Deleted')], default='available')
    deleted_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    @property
    def remaining(self): return self.quantity - self.allocated
    @property
    def available(self): return self.status == 'available' and self.deadline > timezone.now() and self.remaining > 0 and self.provider.status == 'approved'
    @property
    def display_status(self):
        if self.status != 'available': return self.get_status_display()
        if self.deadline <= timezone.now(): return 'Expired'
        return 'Fully Allocated' if self.remaining <= 0 else 'Available'
    @property
    def status_key(self):
        if self.status != 'available': return self.status
        if self.deadline <= timezone.now(): return 'expired'
        return 'allocated' if self.remaining <= 0 else 'available'
    def clean(self):
        errors = {}
        if self.pathway == 'human' and self.condition == 'spoiled': errors['condition'] = 'This condition is unsuitable for human consumption.'
        if not self.pk and self.deadline and self.deadline <= timezone.now(): errors['deadline'] = 'Choose a future deadline (CAT).'
        if not self.safety_acknowledged: errors['safety_acknowledged'] = 'Please acknowledge your responsibility before publishing.'
        if errors: raise ValidationError(errors)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gt=0), name='positive_listing'), models.CheckConstraint(condition=models.Q(allocated__gte=0) & models.Q(allocated__lte=models.F('quantity')), name='allocation_bounds')]
    def __str__(self): return self.name

class FoodRequest(models.Model):
    listing = models.ForeignKey(Listing, related_name='requests', on_delete=models.PROTECT)
    recipient = models.ForeignKey(Organisation, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[POSITIVE])
    status = models.CharField(max_length=20, default='pending', choices=[(v, 'Ready for Collection' if v == 'ready' else 'No-show' if v == 'no_show' else v.replace('_', ' ').title()) for v in ['pending', 'accepted', 'ready', 'collected', 'declined', 'cancelled', 'expired', 'no_show']])
    provider_confirmed = models.DateTimeField(null=True, blank=True)
    recipient_confirmed = models.DateTimeField(null=True, blank=True)
    confirmed_quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    collection_notes = models.TextField(blank=True)
    decision_time = models.DateTimeField(null=True, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gt=0), name='positive_request')]

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
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    summary = models.CharField(max_length=400)
    body = models.TextField()
    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['-published_at','-pk']
    def __str__(self): return self.title
