from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Student, Session, RecurringSchedule, GlobalSettings, PrayerTime, SessionDurationOption, COUNTRY_CHOICES, ScheduleException, WEEKDAYS

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


class RecurringScheduleForm(forms.ModelForm):
    """Form for editing recurring schedule rules."""
    weekday = forms.ChoiceField(
        choices=WEEKDAYS,
        widget=forms.Select(attrs={'class': 'form-select form-control'}),
        help_text=_('Which day of the week')
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        help_text=_('Start time of the session')
    )
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text=_('Uncheck to temporarily pause this schedule')
    )

    class Meta:
        model = RecurringSchedule
        fields = ['weekday', 'start_time', 'is_active']

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.weekday = int(self.cleaned_data['weekday'])
        if commit:
            instance.save()
        return instance


class ScheduleExceptionForm(forms.ModelForm):
    """Form for creating and managing schedule exceptions."""
    exception_type = forms.ChoiceField(
        choices=ScheduleException.EXCEPTION_TYPES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        help_text=_('Type of exception to apply')
    )
    week_start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        help_text=_('The Monday of the week affected')
    )
    move_to_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        help_text=_('(MOVE only) Date to move the session to')
    )
    move_to_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        help_text=_('(MOVE only) Time to move the session to')
    )
    add_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        help_text=_('(ADD only) Date to add extra sessions')
    )
    add_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        help_text=_('(ADD only) Time to start extra sessions')
    )
    add_count = forms.IntegerField(
        initial=1,
        min_value=1,
        max_value=10,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text=_('(ADD only) Number of extra sessions')
    )
    reason = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Student requested makeup session'}),
        help_text=_('Reason for this exception (optional)')
    )

    class Meta:
        model = ScheduleException
        fields = ['exception_type', 'week_start_date', 'move_to_date', 'move_to_time', 
                  'add_date', 'add_time', 'add_count', 'reason']

    def clean(self):
        cleaned_data = super().clean()
        exc_type = cleaned_data.get('exception_type')
        
        if exc_type == 'move':
            if not cleaned_data.get('move_to_date') or not cleaned_data.get('move_to_time'):
                raise forms.ValidationError(_('MOVE exceptions require a target date and time.'))
        
        elif exc_type == 'add':
            if not cleaned_data.get('add_date') or not cleaned_data.get('add_time'):
                raise forms.ValidationError(_('ADD exceptions require a date and time.'))
        
        return cleaned_data


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
