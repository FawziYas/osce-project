"""
Forms for examiner app with proper validation.
"""
from django import forms
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError


class ExaminerLoginForm(forms.Form):
    """Login form with validation."""
    username = forms.CharField(
        max_length=80,
        required=True,
        strip=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
        })
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        """Validate username and password."""
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')

        if username and password:
            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password
            )
            if self.user_cache is None:
                raise ValidationError(
                    'Invalid username or password',
                    code='invalid_login'
                )
            if not self.user_cache.is_active:
                raise ValidationError(
                    'This account is inactive',
                    code='inactive'
                )
        return cleaned_data

    def get_user(self):
        """Return authenticated user."""
        return getattr(self, 'user_cache', None)
