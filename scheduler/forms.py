from django import forms
from django.utils import timezone

from .models import Student, Subscription, Session, WorkingHours, ExceptionDay, PrayerTime, DEFAULT_HOURLY_RATE

COUNTRY_TIMEZONE_MAP = {
    'Egypt': 'Africa/Cairo',
    'Germany': 'Europe/Berlin',
    'France': 'Europe/Paris',
    'United Kingdom': 'Europe/London',
    'United States': 'America/New_York',
    'USA': 'America/New_York',
    'Canada': 'America/Toronto',
    'Saudi Arabia': 'Asia/Riyadh',
    'UAE': 'Asia/Dubai',
    'Kuwait': 'Asia/Kuwait',
    'Lebanon': 'Asia/Beirut',
    'Jordan': 'Asia/Amman',
    'Iraq': 'Asia/Baghdad',
    'Japan': 'Asia/Tokyo',
    'China': 'Asia/Shanghai',
    'India': 'Asia/Kolkata',
    'Australia': 'Australia/Sydney',
}

COUNTRY_CHOICES = [
    ('', 'Select country…'),
    ('Egypt', '🇪🇬 Egypt'),
    ('Germany', '🇩🇪 Germany'),
    ('France', '🇫🇷 France'),
    ('United Kingdom', '🇬🇧 United Kingdom'),
    ('United States', '🇺🇸 United States'),
    ('Canada', '🇨🇦 Canada'),
    ('Saudi Arabia', '🇸🇦 Saudi Arabia'),
    ('UAE', '🇦🇪 UAE'),
    ('Kuwait', '🇰🇼 Kuwait'),
    ('Lebanon', '🇱🇧 Lebanon'),
    ('Jordan', '🇯🇴 Jordan'),
    ('Iraq', '🇮🇶 Iraq'),
    ('Japan', '🇯🇵 Japan'),
    ('China', '🇨🇳 China'),
    ('India', '🇮🇳 India'),
    ('Australia', '🇦🇺 Australia'),
]

TIMEZONE_CHOICES = [
    ('Africa/Cairo', 'Egypt — Cairo (UTC+2/+3)'),
    ('Europe/Berlin', 'Germany — Berlin (UTC+1/+2)'),
    ('Europe/Paris', 'France — Paris (UTC+1/+2)'),
    ('Europe/London', 'UK — London (UTC+0/+1)'),
    ('America/New_York', 'USA — New York (UTC-5/-4)'),
    ('America/Chicago', 'USA — Chicago (UTC-6/-5)'),
    ('America/Denver', 'USA — Denver (UTC-7/-6)'),
    ('America/Los_Angeles', 'USA — Los Angeles (UTC-8/-7)'),
    ('America/Toronto', 'Canada — Toronto (UTC-5/-4)'),
    ('Asia/Riyadh', 'Saudi Arabia — Riyadh (UTC+3)'),
    ('Asia/Dubai', 'UAE — Dubai (UTC+4)'),
    ('Asia/Kuwait', 'Kuwait (UTC+3)'),
    ('Asia/Beirut', 'Lebanon — Beirut (UTC+2/+3)'),
    ('Asia/Amman', 'Jordan — Amman (UTC+2/+3)'),
    ('Asia/Baghdad', 'Iraq — Baghdad (UTC+3)'),
    ('Asia/Tokyo', 'Japan — Tokyo (UTC+9)'),
    ('Asia/Shanghai', 'China — Shanghai (UTC+8)'),
    ('Asia/Kolkata', 'India — Kolkata (UTC+5:30)'),
    ('Australia/Sydney', 'Australia — Sydney (UTC+10/+11)'),
    ('UTC', 'UTC'),
]


class StudentForm(forms.ModelForm):
    country = forms.ChoiceField(choices=COUNTRY_CHOICES, required=True)
    timezone = forms.ChoiceField(
        choices=TIMEZONE_CHOICES,
        initial='Africa/Cairo',
        help_text='The student’s local timezone. Auto-fills from country, but can be changed.',
    )

    class Meta:
        model = Student
        fields = ['name', 'phone', 'country', 'timezone', 'notes', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Student full name'}),
            'phone': forms.TextInput(attrs={'placeholder': '+20 10...'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional notes about this student...'}),
        }
        labels = {
            'is_active': 'Active student',
        }

    def clean(self):
        cleaned = super().clean()
        country = cleaned.get('country')
        tz = cleaned.get('timezone')
        if country and not tz:
            cleaned['timezone'] = COUNTRY_TIMEZONE_MAP.get(country, 'UTC')
            tz = cleaned['timezone']
        if not country:
            self.add_error('country', 'Country is required.')
        if not tz:
            self.add_error('timezone', 'Timezone is required.')
        elif tz not in dict(TIMEZONE_CHOICES):
            self.add_error('timezone', 'Select a valid timezone.')
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.timezone = self.cleaned_data.get('timezone') or COUNTRY_TIMEZONE_MAP.get(self.cleaned_data.get('country'), 'UTC')
        if commit:
            obj.save()
            if hasattr(self, 'save_m2m'):
                self.save_m2m()
        return obj


class SubscriptionForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = ['sessions_per_week', 'session_duration', 'hourly_rate', 'start_date', 'is_active']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'sessions_per_week': forms.NumberInput(attrs={'min': 1, 'placeholder': 'e.g. 3'}),
            'hourly_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
        }
        labels = {
            'is_active': 'Active subscription',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hourly_rate'].initial = DEFAULT_HOURLY_RATE
        self.fields['hourly_rate'].help_text = 'Stored as a snapshot on the subscription. New subscriptions use the global default.'
        self.fields['start_date'].initial = timezone.localdate


class SessionForm(forms.ModelForm):
    start_time = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}), input_formats=['%Y-%m-%dT%H:%M'], help_text='Cairo time (Africa/Cairo)')
    end_time = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}), input_formats=['%Y-%m-%dT%H:%M'], help_text='Cairo time (Africa/Cairo)')

    class Meta:
        model = Session
        fields = ['student', 'start_time', 'end_time', 'status', 'is_makeup', 'original_session', 'is_recurring', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        from .services import to_cairo
        super().__init__(*args, **kwargs)
        self.fields['original_session'].queryset = Session.objects.filter(status='missed').select_related('student')
        self.fields['original_session'].required = False
        self.fields['student'].queryset = Student.objects.filter(is_active=True)
        if self.instance and self.instance.pk:
            if self.instance.start_time:
                self.initial['start_time'] = to_cairo(self.instance.start_time).strftime('%Y-%m-%dT%H:%M')
            if self.instance.end_time:
                self.initial['end_time'] = to_cairo(self.instance.end_time).strftime('%Y-%m-%dT%H:%M')


class QuickSessionForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.filter(is_active=True), empty_label='Select student…')
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), initial=timezone.localdate)
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}), help_text='Cairo time (Africa/Cairo)')
    duration = forms.ChoiceField(choices=[(30, '30 minutes'), (60, '60 minutes')], initial=60)
    is_recurring = forms.BooleanField(required=False, label='Mark as recurring')
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional session notes…'}), required=False)


class WorkingHoursForm(forms.ModelForm):
    class Meta:
        model = WorkingHours
        fields = ['weekday', 'start_time', 'end_time', 'is_working']
        widgets = {'start_time': forms.TimeInput(attrs={'type': 'time'}), 'end_time': forms.TimeInput(attrs={'type': 'time'})}


class ExceptionDayForm(forms.ModelForm):
    class Meta:
        model = ExceptionDay
        fields = ['date', 'reason']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'}), 'reason': forms.TextInput(attrs={'placeholder': 'e.g. Public holiday, sick day…'})}


class PrayerTimeForm(forms.ModelForm):
    class Meta:
        model = PrayerTime
        fields = ['date', 'prayer', 'adhan_time']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'}), 'adhan_time': forms.TimeInput(attrs={'type': 'time'})}


class DateRangeForm(forms.Form):
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False, label='From')
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False, label='To')
    student = forms.ModelChoiceField(queryset=Student.objects.filter(is_active=True), required=False, empty_label='All students')


class SessionStatusForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ['status', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}
