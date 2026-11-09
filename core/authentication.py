from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User


class UsernameOrEmailAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label='Username or email', max_length=254,
        widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username'}),
    )
    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'Please enter a correct username or email and password.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].max_length = 254
        self.fields['username'].widget.attrs['maxlength'] = 254

    def clean(self):
        identifier = self.cleaned_data.get('username', '').strip()
        # Preserve exact username sign-in when a username resembles an email.
        if identifier and not User.objects.filter(username=identifier).exists():
            matches = list(User.objects.filter(email__iexact=identifier).exclude(email='')[:2])
            if len(matches) == 1:
                self.cleaned_data['username'] = matches[0].username
            elif len(matches) > 1:
                raise self.get_invalid_login_error()
        return super().clean()
