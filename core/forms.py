"""
Forms for forced password change flow.
"""
import re

from django import forms


class ForcePasswordChangeForm(forms.Form):
    """
    Minimal form for the forced password-change screen.

    No "current password" field — the user is on a default password
    they never chose, so asking for it would defeat the purpose.
    """

    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'New password',
            'autocomplete': 'new-password',
            'id': 'new_password',
        }),
        min_length=8,
        label='New Password',
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password',
            'autocomplete': 'new-password',
            'id': 'confirm_password',
        }),
        label='Confirm Password',
    )

    def clean_new_password(self):
        pw = self.cleaned_data['new_password']
        if len(pw) < 8:
            raise forms.ValidationError('Password must be at least 8 characters.')
        if not re.search(r'[A-Z]', pw):
            raise forms.ValidationError('Password must contain at least 1 uppercase letter.')
        if not re.search(r'[0-9]', pw):
            raise forms.ValidationError('Password must contain at least 1 number.')
        # Prevent setting the password back to the default
        from django.conf import settings
        default_pw = getattr(settings, 'DEFAULT_USER_PASSWORD', '123456789')
        if pw == default_pw:
            raise forms.ValidationError('You cannot use the default password. Please choose a different one.')
        return pw

    def clean(self):
        cleaned = super().clean()
        new_pw = cleaned.get('new_password')
        confirm = cleaned.get('confirm_password')
        if new_pw and confirm and new_pw != confirm:
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned


class UserPasswordChangeForm(forms.Form):
    """
    Profile page password-change form.

    Requires the user's current password to authenticate the change,
    then enforces strength rules on the new password.
    """

    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Current password',
            'autocomplete': 'current-password',
            'id': 'current_password',
        }),
        label='Current Password',
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'New password (min 8 chars)',
            'autocomplete': 'new-password',
            'id': 'new_password',
        }),
        label='New Password',
    )
    confirm_new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password',
            'autocomplete': 'new-password',
            'id': 'confirm_new_password',
        }),
        label='Confirm New Password',
    )

    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        pw = self.cleaned_data['current_password']
        if self.user and not self.user.check_password(pw):
            raise forms.ValidationError('Your current password is incorrect.')
        return pw

    def clean_new_password(self):
        pw = self.cleaned_data['new_password']
        errors = []
        if len(pw) < 8:
            errors.append('At least 8 characters.')
        if not re.search(r'[A-Z]', pw):
            errors.append('At least one uppercase letter.')
        if not re.search(r'[0-9]', pw):
            errors.append('At least one number.')
        if errors:
            raise forms.ValidationError(errors)
        return pw

    def clean(self):
        cleaned = super().clean()
        new_pw = cleaned.get('new_password')
        confirm = cleaned.get('confirm_new_password')
        if new_pw and confirm and new_pw != confirm:
            self.add_error('confirm_new_password', 'Passwords do not match.')
        return cleaned
