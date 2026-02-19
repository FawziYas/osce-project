"""
Forms for creator app with proper validation.
"""
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, RegexValidator
import re

from core.models import Examiner, Course, Exam, ExamSession, Path, Station


class ExaminerCreateForm(forms.ModelForm):
    """Form for creating/editing examiners with validation."""
    password = forms.CharField(
        required=False,
        min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    password_confirm = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Examiner
        fields = ['username', 'email', 'full_name', 'title', 'department', 'is_active', 'is_staff']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        """Validate password confirmation."""
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password != password_confirm:
            raise ValidationError('Passwords do not match')

        return cleaned_data


class FileUploadForm(forms.Form):
    """Generic file upload form with validation."""
    file = forms.FileField(
        validators=[FileExtensionValidator(allowed_extensions=['xlsx', 'xls'])],
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx,.xls'})
    )

    def clean_file(self):
        """Validate file size (max 5MB)."""
        file = self.cleaned_data.get('file')
        if file:
            if file.size > 5 * 1024 * 1024:  # 5MB
                raise ValidationError('File size must be less than 5MB')
        return file


class StudentUploadForm(FileUploadForm):
    """Student XLSX upload form."""
    path_id = forms.UUIDField(required=False)


class ExaminerUploadForm(FileUploadForm):
    """Examiner XLSX upload form."""
    pass


class SessionForm(forms.ModelForm):
    """Session creation/edit form."""
    class Meta:
        model = ExamSession
        fields = ['session_date', 'start_time', 'session_type', 'notes', 'number_of_stations', 'number_of_paths']
        widgets = {
            'session_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'session_type': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'number_of_stations': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'number_of_paths': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }

    def clean_number_of_stations(self):
        """Validate station count is positive."""
        value = self.cleaned_data.get('number_of_stations')
        if value and value < 1:
            raise ValidationError('Must have at least 1 station')
        return value

    def clean_number_of_paths(self):
        """Validate path count is positive."""
        value = self.cleaned_data.get('number_of_paths')
        if value and value < 1:
            raise ValidationError('Must have at least 1 path')
        return value


class StationForm(forms.ModelForm):
    """Station creation/edit form."""
    class Meta:
        model = Station
        fields = ['name', 'scenario', 'instructions', 'duration_minutes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 200}),
            'scenario': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 60}),
        }

    def clean_name(self):
        """Validate station name."""
        name = self.cleaned_data.get('name')
        if name and len(name) < 3:
            raise ValidationError('Station name must be at least 3 characters')
        return name

    def clean_duration_minutes(self):
        """Validate duration is reasonable."""
        duration = self.cleaned_data.get('duration_minutes')
        if duration and (duration < 1 or duration > 60):
            raise ValidationError('Duration must be between 1 and 60 minutes')
        return duration


class CourseForm(forms.ModelForm):
    """Course creation/edit form."""
    class Meta:
        model = Course
        fields = ['code', 'name', 'short_code', 'description']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 20}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 200}),
            'short_code': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 10}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean_code(self):
        """Validate course code format."""
        code = self.cleaned_data.get('code')
        if code and not re.match(r'^[A-Z0-9\-]+$', code):
            raise ValidationError('Course code must contain only uppercase letters, numbers, and hyphens')
        return code


class ExamForm(forms.ModelForm):
    """Exam creation/edit form."""
    class Meta:
        model = Exam
        fields = ['name', 'course', 'exam_date', 'station_duration_minutes', 'is_archived']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 200}),
            'course': forms.Select(attrs={'class': 'form-select'}),
            'exam_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'station_duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 60}),
            'is_archived': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PathForm(forms.ModelForm):
    """Path creation/edit form."""
    class Meta:
        model = Path
        fields = ['name', 'description', 'rotation_minutes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 100}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'rotation_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 60}),
        }
