from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Student, Subscription, Session, RecurringSchedule, WorkingHours, ExceptionDay, PrayerTime, GlobalConfig, WEEKDAYS

PRAYER_TIME_FIELDS = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']

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
    ('', _('Select country…')),
    ('Egypt', _('🇪🇬 Egypt')),
    ('Germany', _('🇩🇪 Germany')),
    ('France', _('🇫🇷 France')),
    ('United Kingdom', _('🇬🇧 United Kingdom')),
    ('United States', _('🇺🇸 United States')),
    ('Canada', _('🇨🇦 Canada')),
    ('Saudi Arabia', _('🇸🇦 Saudi Arabia')),
    ('UAE', _('🇦🇪 UAE')),
    ('Kuwait', _('🇰🇼 Kuwait')),
    ('Lebanon', _('🇱🇧 Lebanon')),
    ('Jordan', _('🇯🇴 Jordan')),
    ('Iraq', _('🇮🇶 Iraq')),
    ('Japan', _('🇯🇵 Japan')),
    ('China', _('🇨🇳 China')),
    ('India', _('🇮🇳 India')),
    ('Australia', _('🇦🇺 Australia')),
]

TIMEZONE_CHOICES = [
    ('Africa/Cairo', _('Egypt — Cairo (UTC+2/+3)')),
    ('Europe/Berlin', _('Germany — Berlin (UTC+1/+2)')),
    ('Europe/Paris', _('France — Paris (UTC+1/+2)')),
    ('Europe/London', _('UK — London (UTC+0/+1)')),
    ('America/New_York', _('USA — New York (UTC-5/-4)')),
    ('America/Chicago', _('USA — Chicago (UTC-6/-5)')),
    ('America/Denver', _('USA — Denver (UTC-7/-6)')),
    ('America/Los_Angeles', _('USA — Los Angeles (UTC-8/-7)')),
    ('America/Toronto', _('Canada — Toronto (UTC-5/-4)')),
    ('Asia/Riyadh', _('Saudi Arabia — Riyadh (UTC+3)')),
    ('Asia/Dubai', _('UAE — Dubai (UTC+4)')),
    ('Asia/Kuwait', _('Kuwait (UTC+3)')),
    ('Asia/Beirut', _('Lebanon — Beirut (UTC+2/+3)')),
    ('Asia/Amman', _('Jordan — Amman (UTC+2/+3)')),
    ('Asia/Baghdad', _('Iraq — Baghdad (UTC+3)')),
    ('Asia/Tokyo', _('Japan — Tokyo (UTC+9)')),
    ('Asia/Shanghai', _('China — Shanghai (UTC+8)')),
    ('Asia/Kolkata', _('India — Kolkata (UTC+5:30)')),
    ('Australia/Sydney', _('Australia — Sydney (UTC+10/+11)')),
    ('UTC', _('UTC')),
]

class StudentForm(forms.ModelForm):
    country = forms.ChoiceField(
        choices=COUNTRY_CHOICES, 
        required=True, 
        label=_('Country'),
        widget=forms.Select(attrs={
            'class': 'form-select form-control',
            'style': 'appearance: none; padding-right: 40px;'
        })
    )
    timezone = forms.ChoiceField(
        choices=TIMEZONE_CHOICES, 
        initial='Africa/Cairo', 
        help_text=_('The student\'s local timezone. Auto-fills from country, but can be changed.'), 
        label=_('Timezone'),
        widget=forms.Select(attrs={
            'class': 'form-select form-control',
            'style': 'appearance: none; padding-right: 40px;'
        })
    )

    class Meta:
        model = Student
        fields = ['name', 'country', 'timezone', 'notes', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': _('Student full name')}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': _('Optional notes about this student...')}),
        }
        labels = {'is_active': _('Active student')}

    def clean(self):
        cleaned = super().clean()
        country = cleaned.get('country')
        tz = cleaned.get('timezone')
        if country and not tz:
            cleaned['timezone'] = COUNTRY_TIMEZONE_MAP.get(country, 'UTC')
            tz = cleaned['timezone']
        if not country:
            self.add_error('country', _('Country is required.'))
        if not tz:
            self.add_error('timezone', _('Timezone is required.'))
        elif tz not in dict(TIMEZONE_CHOICES):
            self.add_error('timezone', _('Select a valid timezone.'))
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
    recurring_schedule = forms.ModelChoiceField(
        queryset=RecurringSchedule.objects.select_related('student').all(),
        required=False,
        empty_label=_('Create a new schedule below'),
        widget=forms.Select(attrs={'class': 'form-select form-control'}),
    )
    day_of_week = forms.ChoiceField(
        choices=WEEKDAYS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-control'}),
        label=_('Day of week'),
    )
    start_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        label=_('Start time'),
    )
    schedule_duration = forms.IntegerField(
        required=False,
        min_value=15,
        widget=forms.NumberInput(attrs={'min': 15, 'class': 'form-control'}),
        label=_('Schedule duration (minutes)'),
    )

    class Meta:
        model = Subscription
        fields = [
            'recurring_schedule',
            'session_price',
            'session_duration',
            'cancellation_window_hours',
            'allow_makeup_sessions',
            'allow_extra_sessions',
            'start_date',
            'end_date',
            'is_active',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'session_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': _('0.00')}),
            'session_duration': forms.Select(attrs={
                'class': 'form-select form-control',
                'style': 'appearance: none; padding-right: 40px;'
            }),
            'cancellation_window_hours': forms.NumberInput(attrs={'min': 0}),
        }
        labels = {
            'is_active': _('Active enrollment'),
            'session_price': _('Price per session'),
            'session_duration': _('Session duration'),
            'cancellation_window_hours': _('Cancellation window (hours)'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        defaults = GlobalConfig.objects.first()
        if defaults:
            self.fields['session_price'].initial = defaults.default_session_price
            self.fields['session_duration'].initial = defaults.default_session_duration
            self.fields['cancellation_window_hours'].initial = defaults.cancellation_window_hours
            self.fields['allow_makeup_sessions'].initial = defaults.allow_makeup_sessions
            self.fields['allow_extra_sessions'].initial = defaults.allow_extra_sessions
            self.fields['schedule_duration'].initial = defaults.default_session_duration
        else:
            self.fields['session_price'].initial = 200
            self.fields['session_duration'].initial = 60
            self.fields['cancellation_window_hours'].initial = 2
            self.fields['allow_makeup_sessions'].initial = True
            self.fields['allow_extra_sessions'].initial = True
            self.fields['schedule_duration'].initial = 60
        self.fields['session_price'].help_text = _('Stored as a snapshot on the enrollment. Changing this creates a new enrollment record.')
        self.fields['recurring_schedule'].queryset = RecurringSchedule.objects.select_related('student').order_by('student__name', 'day_of_week', 'start_time')
        self.fields['start_date'].initial = timezone.localdate

class RecurringScheduleForm(forms.ModelForm):
    weeks_to_generate = forms.IntegerField(min_value=1, max_value=12, initial=4, label=_('Generate sessions for (weeks)'), help_text=_('How many weeks of sessions to generate immediately.'))

    class Meta:
        model = RecurringSchedule
        fields = ['day_of_week', 'start_time', 'duration', 'is_active']
        widgets = {
            'day_of_week': forms.Select(attrs={'class': 'form-select form-control'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'duration': forms.Select(attrs={'class': 'form-select form-control'}),
        }
        labels = {'day_of_week': _('Day of week'), 'start_time': _('Start time (Cairo)'), 'duration': _('Session duration'), 'is_active': _('Active schedule')}

    def __init__(self, *args, **kwargs):
        self.student = kwargs.pop('student', None)
        super().__init__(*args, **kwargs)

class SessionForm(forms.ModelForm):
    start_time = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}), input_formats=['%Y-%m-%dT%H:%M'], help_text=_('Cairo time (Africa/Cairo)'))
    end_time = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}), input_formats=['%Y-%m-%dT%H:%M'], help_text=_('Cairo time (Africa/Cairo)'))

    class Meta:
        model = Session
        fields = ['student', 'enrollment', 'recurring_schedule', 'start_time', 'end_time', 'status', 'session_type', 'is_makeup', 'is_recurring', 'cancelled_by', 'cancellation_reason', 'original_session', 'is_override', 'notes']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select form-control'}),
            'enrollment': forms.Select(attrs={'class': 'form-select form-control'}),
            'recurring_schedule': forms.Select(attrs={'class': 'form-select form-control'}),
            'status': forms.Select(attrs={'class': 'form-select form-control'}),
            'session_type': forms.Select(attrs={'class': 'form-select form-control'}),
            'cancelled_by': forms.Select(attrs={'class': 'form-select form-control'}),
            'original_session': forms.Select(attrs={'class': 'form-select form-control'}),
            'is_override': forms.CheckboxInput(),
            'notes': forms.Textarea(attrs={'rows': 2})
        }

    def __init__(self, *args, **kwargs):
        from .services import to_cairo
        super().__init__(*args, **kwargs)
        self.fields['original_session'].queryset = Session.objects.filter(status__in=['scheduled', 'completed', 'cancelled', 'rescheduled']).select_related('student')
        self.fields['original_session'].required = False
        self.fields['student'].queryset = Student.objects.filter(is_active=True)
        self.fields['enrollment'].queryset = Subscription.objects.filter(is_active=True).select_related('student')
        self.fields['recurring_schedule'].queryset = RecurringSchedule.objects.select_related('student').all()
        self.fields['session_type'].required = False
        self.fields['cancelled_by'].required = False
        self.fields['cancelled_by'].choices = [('', _('---------'))] + list(self.fields['cancelled_by'].choices)
        if self.instance and self.instance.pk:
            if self.instance.start_time:
                self.initial['start_time'] = to_cairo(self.instance.start_time).strftime('%Y-%m-%dT%H:%M')
            if self.instance.end_time:
                self.initial['end_time'] = to_cairo(self.instance.end_time).strftime('%Y-%m-%dT%H:%M')

class QuickSessionForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=Student.objects.filter(is_active=True), 
        empty_label=_('Select student…'),
        widget=forms.Select(attrs={'class': 'form-select form-control'})
    )
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), initial=timezone.localdate)
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}), help_text=_('Cairo time (Africa/Cairo)'))
    duration = forms.ChoiceField(
        choices=[(30, _('30 minutes')), (60, _('60 minutes'))], 
        initial=60,
        widget=forms.Select(attrs={'class': 'form-select form-control'})
    )
    is_recurring = forms.BooleanField(required=False, label=_('Mark as recurring'))
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 2, 'placeholder': _('Optional session notes…')}), required=False)

class WorkingHoursForm(forms.ModelForm):
    class Meta:
        model = WorkingHours
        fields = ['weekday', 'start_time', 'end_time', 'is_working']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'})
        }

class ExceptionDayForm(forms.ModelForm):
    class Meta:
        model = ExceptionDay
        fields = ['date', 'reason']
        widgets = {
            'date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'reason': forms.TextInput(attrs={
                'placeholder': _('e.g. Public holiday, sick day…'),
                'class': 'form-control'
            })
        }

class PrayerTimeForm(forms.ModelForm):
    class Meta:
        model = PrayerTime
        fields = ['date', 'prayer', 'adhan_time']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'}), 'adhan_time': forms.TimeInput(attrs={'type': 'time'})}


class PrayerTimesDayForm(forms.Form):
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-lg'}),
        label=_('Date'),
    )
    fajr = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control form-control-lg'}), label=_('Fajr'))
    dhuhr = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control form-control-lg'}), label=_('Dhuhr'))
    asr = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control form-control-lg'}), label=_('Asr'))
    maghrib = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control form-control-lg'}), label=_('Maghrib'))
    isha = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control form-control-lg'}), label=_('Isha'))

    def __init__(self, *args, **kwargs):
        initial_times = kwargs.pop('initial_times', None) or {}
        super().__init__(*args, **kwargs)
        for field_name in PRAYER_TIME_FIELDS:
            field = self.fields[field_name]
            field.required = True
            value = initial_times.get(field_name)
            if value:
                self.initial.setdefault(field_name, value)

class DateRangeForm(forms.Form):
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False, label=_('From'))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False, label=_('To'))
    student = forms.ModelChoiceField(queryset=Student.objects.filter(is_active=True), required=False, empty_label=_('All students'))

class SessionStatusForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ['status', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}
