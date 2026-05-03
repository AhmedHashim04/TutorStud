from django import forms
from django.utils import timezone
from .models import Student, Subscription, Session, WorkingHours, ExceptionDay, PrayerTime, WEEKDAYS


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['name', 'phone', 'notes', 'is_active']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class SubscriptionForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = ['sessions_per_week', 'session_duration', 'hourly_rate', 'start_date', 'is_active']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'hourly_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }


class SessionForm(forms.ModelForm):
    start_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        input_formats=['%Y-%m-%dT%H:%M'],
    )
    end_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        input_formats=['%Y-%m-%dT%H:%M'],
    )

    class Meta:
        model = Session
        fields = ['student', 'start_time', 'end_time', 'status', 'is_makeup',
                  'original_session', 'is_recurring', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['original_session'].queryset = Session.objects.filter(
            status='missed'
        ).select_related('student')
        self.fields['original_session'].required = False
        self.fields['student'].queryset = Student.objects.filter(is_active=True)


class QuickSessionForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=Student.objects.filter(is_active=True),
        empty_label="Select student..."
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=timezone.localdate,
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time'}),
    )
    duration = forms.ChoiceField(
        choices=[(30, '30 min'), (60, '60 min')],
        initial=60,
    )
    is_recurring = forms.BooleanField(required=False)
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
    )


class WorkingHoursForm(forms.ModelForm):
    class Meta:
        model = WorkingHours
        fields = ['weekday', 'start_time', 'end_time', 'is_working']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }


class ExceptionDayForm(forms.ModelForm):
    class Meta:
        model = ExceptionDay
        fields = ['date', 'reason']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }


class PrayerTimeForm(forms.ModelForm):
    class Meta:
        model = PrayerTime
        fields = ['date', 'prayer', 'adhan_time']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'adhan_time': forms.TimeInput(attrs={'type': 'time'}),
        }


class DateRangeForm(forms.Form):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False,
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False,
    )
    student = forms.ModelChoiceField(
        queryset=Student.objects.filter(is_active=True),
        required=False,
        empty_label="All students",
    )


class SessionStatusForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ['status', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
