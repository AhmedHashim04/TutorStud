from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from datetime import timedelta

class GlobalSettings(models.Model):
    """Singleton model for global application settings."""
    default_session_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('200'))
    
    class Meta:
        verbose_name_plural = "Global Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super(GlobalSettings, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Global System Settings"

class SessionDurationOption(models.Model):
    """Configurable options for session duration."""
    duration_minutes = models.IntegerField(unique=True, help_text=_("Duration in minutes (e.g. 30, 60)"))

    class Meta:
        ordering = ['duration_minutes']

    def __str__(self):
        return f"{self.duration_minutes} mins"


WEEKDAYS = [
    (5, _('Saturday')),
    (6, _('Sunday')),
    (0, _('Monday')),
    (1, _('Tuesday')),
    (2, _('Wednesday')),
    (3, _('Thursday')),
    (4, _('Friday')),
]

class Student(models.Model):
    """Unified Profile and Enrollment Model."""
    name = models.CharField(max_length=200)
    timezone = models.CharField(max_length=64, default='UTC')
    session_duration = models.IntegerField(default=60, help_text=_('Duration in minutes'))
    session_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('200'))
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class RecurringSchedule(models.Model):
    """The master recurring schedule rules for a student."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='schedules')
    weekday = models.IntegerField(choices=WEEKDAYS)
    start_time = models.TimeField()

    class Meta:
        ordering = ['weekday', 'start_time']

    def __str__(self):
        return f"{self.student.name} - {self.get_weekday_display()} at {self.start_time}"


class Session(models.Model):
    """A unified block of time representing an appointment."""
    STATUS_CHOICES = [
        ('scheduled', _('Scheduled')),
        ('attended', _('Attended ✅')),
        ('absent', _('Absent (No-Show) ❌')),
        ('excused', _('Excused (No Pay) 💬')),
        ('cancelled_by_teacher', _('Cancelled by Teacher 🚫')),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='sessions')
    start_time = models.DateTimeField()
    duration = models.IntegerField(help_text=_('Duration in minutes'))
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='scheduled')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"{self.student.name} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    @property
    def end_time(self):
        return self.start_time + timedelta(minutes=self.duration)

    @property
    def is_payable(self):
        """Teacher gets paid if student attended or no-showed."""
        return self.status in ['attended', 'absent']


class PrayerTime(models.Model):
    """Blocks out time on the calendar to prevent scheduling conflicts."""
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
    duration = models.IntegerField(default=30, help_text=_('Blocked duration in minutes for this prayer'))

    class Meta:
        unique_together = ['date', 'prayer']
        ordering = ['date', 'adhan_time']

    def __str__(self):
        return f"{self.get_prayer_display()} on {self.date} at {self.adhan_time}"
