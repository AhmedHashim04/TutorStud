from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal


DEFAULT_HOURLY_RATE = Decimal('200')

WEEKDAYS = [
    (0, _('Monday')),
    (1, _('Tuesday')),
    (2, _('Wednesday')),
    (3, _('Thursday')),
    (4, _('Friday')),
    (5, _('Saturday')),
    (6, _('Sunday')),
]


class Student(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    country = models.CharField(max_length=100, blank=True)
    timezone = models.CharField(max_length=64, default='UTC')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    @property
    def active_subscription(self):
        return self.subscriptions.filter(is_active=True).first()

    @property
    def weekly_earnings(self):
        sub = self.active_subscription
        if not sub:
            return Decimal('0')
        return sub.weekly_earnings

    @property
    def monthly_earnings(self):
        sub = self.active_subscription
        if not sub:
            return Decimal('0')
        return sub.monthly_earnings


class Subscription(models.Model):
    DURATION_CHOICES = [
        (30, _('30 minutes')),
        (60, _('60 minutes')),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='subscriptions')
    sessions_per_week = models.PositiveIntegerField(default=3)
    session_duration = models.IntegerField(choices=DURATION_CHOICES, default=60)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=DEFAULT_HOURLY_RATE)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.name} - {self.sessions_per_week}x/week"

    @property
    def session_rate(self):
        return (self.hourly_rate * self.session_duration) / 60

    @property
    def weekly_earnings(self):
        return self.session_rate * self.sessions_per_week

    @property
    def monthly_earnings(self):
        return self.weekly_earnings * Decimal('4.33')


class RecurringSchedule(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='recurring_schedules')
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name='recurring_schedules')
    day_of_week = models.IntegerField(choices=WEEKDAYS)
    start_time = models.TimeField(help_text=_('Cairo time (Africa/Cairo)'))
    duration = models.IntegerField(choices=[(30, _('30 minutes')), (45, _('45 minutes')), (60, _('60 minutes')), (90, _('90 minutes'))], default=60, help_text=_('Duration in minutes'))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        day = self.get_day_of_week_display()
        return f"{self.student.name} — {day} {self.start_time.strftime('%H:%M')} ({self.duration} min)"

    @property
    def day_name(self):
        return dict(WEEKDAYS).get(self.day_of_week, '')


class WorkingHours(models.Model):
    weekday = models.IntegerField(choices=WEEKDAYS, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_working = models.BooleanField(default=True)

    class Meta:
        ordering = ['weekday']

    def __str__(self):
        return f"{self.get_weekday_display()}: {self.start_time} - {self.end_time}"


class ExceptionDay(models.Model):
    date = models.DateField(unique=True)
    reason = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f"Exception: {self.date} - {self.reason}"


class PrayerTime(models.Model):
    PRAYER_CHOICES = [
        ('fajr', _('Fajr')),
        ('dhuhr', _('Dhuhr')),
        ('asr', _('Asr')),
        ('maghrib', _('Maghrib')),
        ('isha', _('Isha')),
    ]

    date = models.DateField()
    prayer = models.CharField(max_length=10, choices=PRAYER_CHOICES)
    adhan_time = models.TimeField()

    class Meta:
        unique_together = ['date', 'prayer']
        ordering = ['date', 'adhan_time']

    def __str__(self):
        return f"{self.get_prayer_display()} on {self.date} at {self.adhan_time}"


class Session(models.Model):
    STATUS_CHOICES = [
        ('scheduled', _('Scheduled')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
        ('missed', _('Missed')),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='sessions')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    is_makeup = models.BooleanField(default=False)
    original_session = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='makeup_sessions')
    recurring_schedule = models.ForeignKey(RecurringSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions', help_text=_('The recurring pattern this session was generated from.'))
    is_override = models.BooleanField(default=False, help_text=_('True when this session has been individually modified from its recurring pattern.'))
    is_recurring = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"{self.student.name} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    @property
    def duration_minutes(self):
        delta = self.end_time - self.start_time
        return int(delta.total_seconds() / 60)

    @property
    def earnings(self):
        sub = self.student.active_subscription
        if not sub:
            return Decimal('0')
        return (sub.hourly_rate * Decimal(self.duration_minutes)) / 60
