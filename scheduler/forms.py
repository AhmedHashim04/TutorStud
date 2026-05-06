from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Student, Session, RecurringSchedule, GlobalSettings, PrayerTime, SessionDurationOption, COUNTRY_CHOICES

class StudentForm(forms.ModelForm):
    country = forms.ChoiceField(
        choices=COUNTRY_CHOICES, 
        initial='Egypt', 
        widget=forms.Select(attrs={'class': 'form-select form-control'})
    )

    class Meta:
        model = Student
        fields = ['name', 'country', 'session_duration', 'session_price', 'notes', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Student Name'}),
            'session_duration': forms.NumberInput(attrs={'class': 'form-control'}),
            'session_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            settings = GlobalSettings.load()
            self.fields['session_price'].initial = settings.default_session_price
            
            # Get default duration if options exist
            default_dur = SessionDurationOption.objects.first()
            if default_dur:
                self.fields['session_duration'].initial = default_dur.duration_minutes


class ManualSessionForm(forms.ModelForm):
    start_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        input_formats=['%Y-%m-%dT%H:%M']
    )

    class Meta:
        model = Session
        fields = ['student', 'start_time', 'duration', 'price', 'status']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select form-control'}),
            'duration': forms.NumberInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-select form-control'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = Student.objects.filter(is_active=True)


class SessionStatusForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ['status']


class GlobalSettingsForm(forms.ModelForm):
    class Meta:
        model = GlobalSettings
        fields = ['default_session_price']
        widgets = {
            'default_session_price': forms.NumberInput(attrs={'class': 'form-control'})
        }


class PrayerTimeForm(forms.ModelForm):
    class Meta:
        model = PrayerTime
        fields = ['date', 'prayer', 'adhan_time', 'duration']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'adhan_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'duration': forms.NumberInput(attrs={'class': 'form-control'})
        }
