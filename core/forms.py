from django import forms
from django.core.files.base import ContentFile
from io import BytesIO
from PIL import Image, ImageOps
from .models import BeneficiaryApplication, ContactMessage, Listing, StorySubmission
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Organisation
from .models import EmailPreferences
from django.utils import timezone
from datetime import timedelta

UPLOAD_MAX_BYTES = 4 * 1024 * 1024
UPLOAD_MAX_MB = 4

class ListingForm(forms.ModelForm):
    photo = forms.ImageField(required=False, label='Food photo', help_text=f'Upload a clear photo of the actual food. JPG, PNG or WebP, up to {UPLOAD_MAX_MB} MB.', widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}))
    pickup_latitude = forms.DecimalField(required=False, min_value=-90, max_value=90, max_digits=9, decimal_places=6, widget=forms.HiddenInput())
    pickup_longitude = forms.DecimalField(required=False, min_value=-180, max_value=180, max_digits=9, decimal_places=6, widget=forms.HiddenInput())
    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if not photo:
            return photo
        if not hasattr(photo, 'temporary_file_path') and photo == self.instance.photo and not self.files:
            return photo
        if photo.size > UPLOAD_MAX_BYTES:
            raise forms.ValidationError(f'Choose a photo smaller than {UPLOAD_MAX_MB} MB.')
        try:
            with Image.open(photo) as source:
                if source.format not in {'JPEG', 'PNG', 'WEBP'}:
                    raise forms.ValidationError('Use a JPG, PNG or WebP photo.')
                if source.width * source.height > 25_000_000:
                    raise forms.ValidationError('Choose a photo smaller than 25 megapixels.')
                image = ImageOps.exif_transpose(source).convert('RGB')
                image.thumbnail((1600, 1600))
                output = BytesIO()
                image.save(output, format='JPEG', quality=82, optimize=True)
            return ContentFile(output.getvalue(), name='food.jpg')
        except (OSError, Image.DecompressionBombError):
            raise forms.ValidationError('This photo could not be read. Choose another image.')
    safety_acknowledged = forms.BooleanField(label='I confirm that the food information is accurate. FoodLoop does not inspect or certify food; I remain responsible for describing it honestly.')
    class Meta:
        model = Listing
        fields = ['photo', 'name', 'quantity', 'unit', 'pathway', 'condition', 'area', 'address', 'deadline', 'notes', 'safety_acknowledged', 'pickup_latitude', 'pickup_longitude', 'share_pickup_pin', 'access_surface', 'access_condition', 'access_notes']
        widgets = {'deadline': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local', 'step': '60'}), 'notes': forms.Textarea(attrs={'rows': 3}), 'access_notes': forms.Textarea(attrs={'rows': 3})}
        labels = {'deadline': 'Collection deadline (CAT, UTC+2)', 'address': 'Exact pickup address (private until acceptance)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        prompts = {
            'name': 'e.g. Fresh bread rolls',
            'quantity': 'Enter the quantity available',
            'area': 'e.g. Lusaka Central',
            'address': 'e.g. Shop 4, Kabulonga Road, Lusaka',
            'notes': 'Add useful details such as packaging, storage or collection instructions',
        }
        for name, prompt in prompts.items():
            self.fields[name].widget.attrs['placeholder'] = prompt
        for name, prompt in {'unit': 'Choose a unit', 'pathway': 'Choose a recovery pathway', 'condition': 'Choose the food condition'}.items():
            field = self.fields[name]
            field.choices = [('', prompt), *field.choices]
        self.fields['pathway'].help_text = "All approved beneficiaries can request from any pathway. The selected pathway tells them the intended use: human consumption, animal feed or composting."
        now = timezone.localtime()
        self.fields['deadline'].widget.attrs['min'] = now.strftime('%Y-%m-%dT%H:%M')
        self.fields['deadline'].help_text = 'Times use Zambia time (CAT, UTC+2). Choose a future date and time.'
        if self.instance.pk and self.instance.deadline:
            self.initial['deadline'] = timezone.localtime(self.instance.deadline).replace(tzinfo=None)
        elif not self.is_bound:
            suggested = (now + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
            self.initial['deadline'] = suggested.replace(tzinfo=None)

    def save(self, commit=True):
        listing = super().save(commit=False)
        report_fields = {'access_surface', 'access_condition', 'access_notes'}
        if report_fields.intersection(self.changed_data):
            listing.access_reported_at = timezone.now() if any(getattr(listing, name) for name in report_fields) else None
        if commit:
            listing.save()
            self.save_m2m()
        return listing

    def clean_deadline(self):
        deadline = self.cleaned_data['deadline']
        if deadline <= timezone.now():
            raise forms.ValidationError('Choose a future collection deadline in Zambia time.')
        return deadline

    def clean(self):
        cleaned = super().clean()
        latitude = cleaned.get('pickup_latitude')
        longitude = cleaned.get('pickup_longitude')
        if (latitude is None) != (longitude is None):
            self.add_error(None, 'Capture both pickup coordinates together, or clear the pin and use the area instead.')
        return cleaned

class RequestForm(forms.Form):
    quantity = forms.DecimalField(min_value=0.01, max_digits=10, decimal_places=2)
    safety = forms.BooleanField(label='Our organisation can safely collect, handle and use this item for the purpose shown on the listing. I will inspect it at collection and will not resell it. FoodLoop does not certify food as safe.')

class FlagForm(forms.Form):
    reason = forms.CharField(max_length=2000, min_length=5, label='What should we review?', widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe the safety concern or inaccurate information.'}))

class DecisionForm(forms.Form):
    reason = forms.CharField(max_length=1000, min_length=3, widget=forms.Textarea(attrs={'rows': 3}))

class ProfileForm(forms.ModelForm):
    email_notifications = forms.BooleanField(required=False, label='Email me updates about my requests, collections and account.')
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        pref = EmailPreferences.objects.filter(user=self.instance).first() if self.instance.pk else None
        self.fields['email_notifications'].initial = pref.enabled if pref else True
    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('This email is already linked to another account.')
        return email

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

class PreferencesForm(forms.Form):
    usual_quantity = forms.DecimalField(min_value=0.01, max_digits=10, decimal_places=2, label='Usual collection quantity')
    usual_unit = forms.ChoiceField(choices=Listing._meta.get_field('unit').choices, label='Usual quantity unit')

class CollectionNotesForm(forms.Form):
    notes = forms.CharField(max_length=2000, required=False, widget=forms.Textarea(attrs={'rows': 3}), label='Collection notes')

class SignupForm(UserCreationForm):
    email = forms.EmailField(label='Email address', max_length=254)
    organisation_name = forms.CharField(max_length=160, label='Organisation name')
    account_type = forms.ChoiceField(label='How will you use FoodLoop?', choices=[('provider', 'Donor — share surplus food'), ('recipient', 'Beneficiary — food for people'), ('feed', 'Recovery partner — animal feed'), ('compost', 'Recovery partner — composting')])
    contact_name = forms.CharField(max_length=140, label='Your full name')
    phone = forms.CharField(max_length=40, label='Contact phone')
    area = forms.CharField(max_length=100, label='General area', widget=forms.TextInput(attrs={'placeholder': 'For example, Lusaka Central'}))
    physical_address = forms.CharField(max_length=240, label='Organisation address', help_text='For account records and collection coordination. Your pickup address stays private until acceptance.')
    registration_reference = forms.CharField(max_length=160, required=False, label='Registration or recognition reference (if applicable)')
    activity_description = forms.CharField(max_length=2000, label='What does your organisation do?', help_text='Describe whom you serve, your food business, animals kept, or composting activity.', widget=forms.Textarea(attrs={'rows': 3}))
    handling_capacity = forms.CharField(max_length=2000, required=False, label='Storage and handling capacity', help_text='Describe safe storage, handling and transport for your intended recovery use.', widget=forms.Textarea(attrs={'rows': 3}))
    authorised_representative = forms.BooleanField(required=False, label='I am authorised to list food on behalf of this organisation (required for donors).')
    terms_accepted = forms.BooleanField(label='I agree to the food-sharing terms and have read the privacy notice.')
    email_updates = forms.BooleanField(required=False, initial=True, label='Email me updates about my account, requests and collections.')

    class Meta(UserCreationForm.Meta):
        fields = ['username', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('This email is already linked to an account. Sign in or reset your password.')
        return email

    def clean_username(self):
        username = self.cleaned_data['username'].casefold()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken. Choose another.')
        return username

    def clean_organisation_name(self):
        name = self.cleaned_data['organisation_name'].strip()
        if Organisation.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError('This organisation already has an account. Ask its administrator for access.')
        return name

    def clean(self):
        data = super().clean()
        if data.get('account_type') == 'provider' and not data.get('authorised_representative'):
            self.add_error('authorised_representative', 'Confirm that you are authorised to list food for this organisation.')
        if data.get('account_type') == 'recipient' and not data.get('handling_capacity'):
            self.add_error('handling_capacity', 'Describe how you can safely store and handle food or recovery materials.')
        return data


class BeneficiaryEligibilityForm(forms.Form):
    programme_type = forms.ChoiceField(
        label='Which programme best describes your organisation?',
        choices=[('', 'Select a programme type')] + BeneficiaryApplication.PROGRAMMES,
    )
    accepted = forms.BooleanField(
        label='I confirm that our organisation fits one of these categories and agree to FoodLoop’s beneficiary participation rules.',
    )


class BeneficiaryApplicationForm(forms.ModelForm):
    submit_for_review = forms.BooleanField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = BeneficiaryApplication
        fields = ['legal_form', 'registration_document', 'programme_type', 'people_served', 'feeding_days_per_week', 'years_operating', 'health_clearance', 'health_clearance_note', 'health_document', 'food_handler_evidence', 'food_handler_note', 'storage_description', 'governance_description', 'community_references', 'beneficiary_records', 'has_food_transport', 'has_performance_indicators', 'has_financial_records', 'staff_or_volunteers', 'supporting_document', 'additional_context', 'no_resale_agreement', 'nondiscrimination_agreement', 'inspection_consent', 'information_accuracy']
        widgets = {
            'storage_description': forms.Textarea(attrs={'rows': 3}),
            'governance_description': forms.Textarea(attrs={'rows': 3}),
            'community_references': forms.Textarea(attrs={'rows': 3}),
            'additional_context': forms.Textarea(attrs={'rows': 3}),
            'people_served': forms.NumberInput(attrs={'min': 1}),
            'feeding_days_per_week': forms.NumberInput(attrs={'min': 1, 'max': 7}),
            'years_operating': forms.NumberInput(attrs={'min': 0, 'step': '0.5'}),
            'staff_or_volunteers': forms.NumberInput(attrs={'min': 0}),
        }
        labels = {
            'legal_form': 'Organisation type / registration route',
            'registration_document': 'Registration or recognition document (optional)',
            'programme_type': 'Main programme type',
            'people_served': 'Approximate people served',
            'feeding_days_per_week': 'Days per week food is provided',
            'years_operating': 'Years operating',
            'health_clearance': 'Local council health clearance for your premises',
            'health_clearance_note': 'Explain if pending or not applicable',
            'health_document': 'Health permit or related evidence (optional)',
            'food_handler_evidence': 'Food-handler training or certification',
            'food_handler_note': 'Explain if pending or not applicable',
            'storage_description': 'How will food be stored, handled and transported?',
            'governance_description': 'Leadership, committee or governance details',
            'community_references': 'Community or government references (optional)',
            'beneficiary_records': 'We keep basic records of people served and food distributed',
            'has_food_transport': 'We have suitable transport for food collections',
            'has_performance_indicators': 'We track programme results or progress',
            'has_financial_records': 'We keep basic financial records',
            'staff_or_volunteers': 'Number of staff and regular volunteers',
            'supporting_document': 'Other supporting document (optional)',
            'additional_context': 'Anything else that will help assess the application',
            'no_resale_agreement': 'We will not sell, exchange or barter donated food',
            'nondiscrimination_agreement': 'We will distribute food fairly and without discrimination',
            'inspection_consent': 'We agree to reasonable verification visits and records checks',
            'information_accuracy': 'The information provided is accurate to the best of our knowledge',
        }

    def __init__(self, *args, submitting=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.submitting = submitting
        pathway = self.instance.organisation.pathway if self.instance.organisation_id else 'human'
        self.recovery_pathway = pathway
        self.fields['programme_type'].choices = [('', 'Select a programme type')] + [(value, label) for value, label in BeneficiaryApplication.PROGRAMMES if BeneficiaryApplication.pathway_for_programme(value) == pathway]
        if pathway != 'human':
            for name in ('people_served', 'feeding_days_per_week', 'health_clearance', 'health_clearance_note', 'health_document', 'food_handler_evidence', 'food_handler_note', 'nondiscrimination_agreement'):
                self.fields.pop(name)
            self.fields['storage_description'].label = 'Describe the animals, feed use, storage and transport' if pathway == 'feed' else 'Describe the composting process, site, storage and transport'
            self.fields['has_food_transport'].label = 'We have suitable transport for collection materials'
            self.fields['beneficiary_records'].label = 'We keep records of collections and how materials are used'
            self.fields['no_resale_agreement'].label = 'We will use collected materials for the approved recovery purpose and will not resell or barter them'
        for field in self.fields.values():
            field.required = False
        if submitting:
            for name in ('legal_form', 'programme_type', 'people_served', 'feeding_days_per_week', 'health_clearance', 'food_handler_evidence', 'storage_description'):
                if name in self.fields:
                    self.fields[name].required = True
            for name in ('beneficiary_records', 'no_resale_agreement', 'nondiscrimination_agreement', 'inspection_consent', 'information_accuracy'):
                if name in self.fields:
                    self.fields[name].required = True
        for name in ('registration_document', 'health_document', 'supporting_document'):
            if name in self.fields:
                self.fields[name].help_text = f'PDF, JPG or PNG, up to {UPLOAD_MAX_MB} MB. Files are visible only to you and FoodLoop administrators.'

    def clean(self):
        cleaned = super().clean()
        for name in ('registration_document', 'health_document', 'supporting_document'):
            file = cleaned.get(name)
            if file and getattr(file, 'size', 0) > UPLOAD_MAX_BYTES:
                self.add_error(name, f'Choose a file smaller than {UPLOAD_MAX_MB} MB.')
        if self.submitting:
            if cleaned.get('people_served') is not None and cleaned['people_served'] < 1:
                self.add_error('people_served', 'Enter at least one person served.')
            if cleaned.get('feeding_days_per_week') is not None and not 1 <= cleaned['feeding_days_per_week'] <= 7:
                self.add_error('feeding_days_per_week', 'Enter a value from 1 to 7 days.')
            for value_field, note_field in (('health_clearance', 'health_clearance_note'), ('food_handler_evidence', 'food_handler_note')):
                if cleaned.get(value_field) in ('applied', 'not_required') and not cleaned.get(note_field, '').strip():
                    self.add_error(note_field, 'Please explain the situation.')
        return cleaned


class ContactMessageForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'autocomplete': 'name', 'placeholder': 'Your name'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email', 'placeholder': 'you@example.com'}),
            'subject': forms.TextInput(attrs={'placeholder': 'What would you like to discuss?'}),
            'message': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Write your message'}),
        }
        labels = {'name': 'Full name', 'email': 'Email address', 'subject': 'Subject', 'message': 'Message'}

    def clean_message(self):
        value = self.cleaned_data['message'].strip()
        if len(value) < 10:
            raise forms.ValidationError('Please include a little more detail (at least 10 characters).')
        return value

class StorySubmissionForm(forms.ModelForm):
    consent_confirmed = forms.BooleanField(required=True, label='I have permission to share this story and any identifiable details or images included.')
    class Meta:
        model = StorySubmission
        fields = ['title', 'summary', 'body', 'image', 'consent_confirmed']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'A clear, specific story title', 'maxlength': 200}),
            'summary': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Briefly describe what happened and why it matters.', 'maxlength': 400}),
            'body': forms.Textarea(attrs={'rows': 10, 'placeholder': 'Share the background, what the partners did, and the outcome.'}),
            'image': forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
        }
        labels = {'title': 'Story title', 'summary': 'Short summary', 'body': 'Story', 'image': 'Photo (optional)'}
        help_texts = {'image': f'Use a photo you have permission to share. JPG, PNG or WebP, up to {UPLOAD_MAX_MB} MB.'}
    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and image.size > UPLOAD_MAX_BYTES:
            raise forms.ValidationError(f'Choose an image smaller than {UPLOAD_MAX_MB} MB.')
        return image
