from django import forms
from django.core.files.base import ContentFile
from io import BytesIO
from PIL import Image, ImageOps
from .models import Listing
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Organisation
from .models import EmailPreferences
from django.utils import timezone
from datetime import timedelta

class ListingForm(forms.ModelForm):
    photo = forms.ImageField(required=False, label='Food photo', help_text='Upload a clear photo of the actual food. JPG, PNG or WebP, up to 8 MB.', widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}))
    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if not photo:
            return photo
        if not hasattr(photo, 'temporary_file_path') and photo == self.instance.photo and not self.files:
            return photo
        if photo.size > 8 * 1024 * 1024:
            raise forms.ValidationError('Choose a photo smaller than 8 MB.')
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
        fields = ['photo', 'name', 'quantity', 'unit', 'pathway', 'condition', 'area', 'address', 'deadline', 'notes', 'safety_acknowledged']
        widgets = {'deadline': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local', 'step': '60'}), 'notes': forms.Textarea(attrs={'rows': 3})}
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
        now = timezone.localtime()
        self.fields['deadline'].widget.attrs['min'] = now.strftime('%Y-%m-%dT%H:%M')
        self.fields['deadline'].help_text = 'Times use Zambia time (CAT, UTC+2). Choose a future date and time.'
        if self.instance.pk and self.instance.deadline:
            self.initial['deadline'] = timezone.localtime(self.instance.deadline).replace(tzinfo=None)
        elif not self.is_bound:
            suggested = (now + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
            self.initial['deadline'] = suggested.replace(tzinfo=None)

    def clean_deadline(self):
        deadline = self.cleaned_data['deadline']
        if deadline <= timezone.now():
            raise forms.ValidationError('Choose a future collection deadline in Zambia time.')
        return deadline

class RequestForm(forms.Form):
    quantity = forms.DecimalField(min_value=0.01, max_digits=10, decimal_places=2)
    safety = forms.BooleanField(label='FoodLoop does not certify food as safe. I will inspect it on collection, use it only for my approved pathway, and will not resell it.')

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
    account_type = forms.ChoiceField(label='How will you use FoodLoop?', choices=[('provider', 'Food provider — donate surplus'), ('recipient', 'Recipient — food for people'), ('feed', 'Recovery partner — animal feed'), ('compost', 'Recovery partner — composting')])
    contact_name = forms.CharField(max_length=140, label='Your full name')
    phone = forms.CharField(max_length=40, label='Contact phone')
    area = forms.CharField(max_length=100, label='General area', widget=forms.TextInput(attrs={'placeholder': 'For example, Lusaka Central'}))
    physical_address = forms.CharField(max_length=240, label='Organisation address', help_text='For administrator verification. Your pickup address stays private until acceptance.')
    registration_reference = forms.CharField(max_length=160, required=False, label='Registration or recognition reference (if applicable)')
    activity_description = forms.CharField(max_length=2000, label='What does your organisation do?', help_text='Describe whom you serve, your food business, animals kept, or composting activity.', widget=forms.Textarea(attrs={'rows': 3}))
    handling_capacity = forms.CharField(max_length=2000, required=False, label='Food storage and handling capacity', help_text='Required for organisations receiving food for people.', widget=forms.Textarea(attrs={'rows': 3}))
    authorised_representative = forms.BooleanField(required=False, label='I am authorised to list food on behalf of this organisation (required for providers).')
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
            self.add_error('handling_capacity', 'Describe how you can safely store and handle the food.')
        return data
