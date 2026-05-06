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


class GlobalConfig(models.Model):
    default_session_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('200'))
    default_session_duration = models.IntegerField(default=60, help_text=_('Duration in minutes'))
    cancellation_window_hours = models.IntegerField(default=2)
    allow_makeup_sessions = models.BooleanField(default=True)
    allow_extra_sessions = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Global Configuration')
        verbose_name_plural = _('Global Configuration')

    def __str__(self):
        return "System Configuration"


class Student(models.Model):
    name = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    country = models.CharField(max_length=100, blank=True)
    timezone = models.CharField(max_length=64, default='UTC')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    @property
    def active_enrollment(self):
        return self.subscriptions.filter(is_active=True).first()

    @property
    def active_subscription(self):
        return self.active_enrollment


class RecurringSchedule(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='recurring_schedules')
    subscription = models.ForeignKey('StudentEnrollment', on_delete=models.SET_NULL, null=True, blank=True, related_name='recurring_schedules')
    day_of_week = models.IntegerField(choices=WEEKDAYS)
    start_time = models.TimeField()
    duration = models.IntegerField(default=60)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        day = self.get_day_of_week_display()
        return f"{self.student.name} — {day} {self.start_time.strftime('%H:%M')}"


class StudentEnrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='subscriptions')
    recurring_schedule = models.ForeignKey(RecurringSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name='enrollments')
    
    # Pricing snapshot
    session_price = models.DecimalField(max_digits=10, decimal_places=2)
    session_duration = models.IntegerField(help_text=_('Duration in minutes'))
    
    # Rules snapshot
    cancellation_window_hours = models.IntegerField(default=2)
    allow_makeup_sessions = models.BooleanField(default=True)
    allow_extra_sessions = models.BooleanField(default=True)
    
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    
    config_snapshot = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.name} Enrollment"

    @property
    def session_rate(self):
        return self.session_price

    @property
    def weekly_earnings(self):
        if not self.recurring_schedule:
            return Decimal('0')
        return self.session_price

    @property
    def monthly_earnings(self):
        return self.session_price * Decimal('4')


Subscription = StudentEnrollment


class WorkingHours(models.Model):
    weekday = models.IntegerField(choices=WEEKDAYS, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_working = models.BooleanField(default=True)

    class Meta:
        ordering = ['weekday']

    def __str__(self):
        return f"{self.get_weekday_display()}: {self.start_time} - {self.end_time}"


class WorkingHoursRange(models.Model):
    working_hours = models.ForeignKey(WorkingHours, on_delete=models.CASCADE, related_name='ranges')
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"{self.working_hours.get_weekday_display()}: {self.start_time} - {self.end_time}"


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
        ('rescheduled', _('Rescheduled')),
    ]

    CANCELLED_BY_CHOICES = [
        ('student', _('Student')),
        ('teacher', _('Teacher')),
    ]

    SESSION_TYPE_CHOICES = [
        ('regular', _('Regular')),
        ('extra', _('Extra')),
        ('makeup', _('Makeup')),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='sessions')
    enrollment = models.ForeignKey(StudentEnrollment, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')
    recurring_schedule = models.ForeignKey(RecurringSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')
    
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    session_type = models.CharField(max_length=20, choices=SESSION_TYPE_CHOICES, default='regular')
    is_makeup = models.BooleanField(default=False)
    is_recurring = models.BooleanField(default=False)
    
    cancelled_by = models.CharField(max_length=10, choices=CANCELLED_BY_CHOICES, null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    
    original_session = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='makeup_sessions')
    is_override = models.BooleanField(default=False)
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"{self.student.name} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        if self.session_type == 'makeup':
            self.is_makeup = True
        elif self.is_makeup and self.session_type == 'regular':
            self.session_type = 'makeup'
        super().save(*args, **kwargs)

    @property
    def duration_minutes(self):
        delta = self.end_time - self.start_time
        return int(delta.total_seconds() / 60)
    
    def can_be_cancelled_free(self):
        if not self.enrollment:
            return True
        time_until = self.start_time - timezone.now()
        return (time_until.total_seconds() / 3600) >= self.enrollment.cancellation_window_hours

    @property
    def earnings(self):
        if self.enrollment:
            return self.enrollment.session_price
        active_enrollment = self.student.active_subscription
        if active_enrollment:
            return active_enrollment.session_price
        return Decimal('0')


class SessionAttendance(models.Model):
    ATTENDANCE_CHOICES = [
        ('present', _('Present')),
        ('absence', _('Absence')),
        ('late', _('Late')),
    ]
    session = models.OneToOneField(Session, on_delete=models.CASCADE, related_name='attendance')
    attendance_status = models.CharField(max_length=10, choices=ATTENDANCE_CHOICES, null=True, blank=True)
    marked_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)


class SessionPayment(models.Model):
    session = models.OneToOneField(Session, on_delete=models.CASCADE, related_name='payment')
    base_amount = models.DecimalField(max_digits=10, decimal_places=2)
    override_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2)
    rule_applied = models.CharField(max_length=100)
    is_paid = models.BooleanField(default=False)
    calculated_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True)
