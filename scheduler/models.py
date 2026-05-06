from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from datetime import timedelta
import pytz
from django.db.models import Sum, Count

CAIRO_TZ = pytz.timezone('Africa/Cairo')

COUNTRY_TIMEZONE_MAP = {
    'Egypt': 'Africa/Cairo',
    'Germany': 'Europe/Berlin',
    'France': 'Europe/Paris',
    'United Kingdom': 'Europe/London',
    'United States': 'America/New_York',
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

class GlobalSettings(models.Model):
    """Singleton model for global application settings."""
    default_session_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('200'))
    prayer_buffer_minutes = models.IntegerField(default=10, help_text=_("Buffer time after Adhan to block scheduling"))
    
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
    country = models.CharField(max_length=100, choices=COUNTRY_CHOICES, default='Egypt')
    session_duration = models.IntegerField(default=60, help_text=_('Duration in minutes'))
    session_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('200'))
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def student_timezone(self):
        return pytz.timezone(COUNTRY_TIMEZONE_MAP.get(self.country, 'UTC'))
        
    @property
    def timezone_difference_str(self):
        """Returns string like '+1 hour ahead' or 'Same time'."""
        now = timezone.now()
        tutor_offset = now.astimezone(CAIRO_TZ).utcoffset().total_seconds()
        student_offset = now.astimezone(self.student_timezone).utcoffset().total_seconds()
        diff_hours = (student_offset - tutor_offset) / 3600
        
        if diff_hours == 0:
            return "Same time as Tutor"
        elif diff_hours > 0:
            return f"+{int(diff_hours)} hour{'s' if diff_hours > 1 else ''} ahead"
        else:
            return f"{int(diff_hours)} hour{'s' if diff_hours < -1 else ''} behind"

    @property
    def attendance_rate(self):
        past_sessions = self.sessions.filter(start_time__lt=timezone.now()).exclude(status__in=['scheduled', 'cancelled_by_teacher'])
        total = past_sessions.count()
        if total == 0: return 0
        attended = past_sessions.filter(status='attended').count()
        return round((attended / total) * 100)

    @property
    def no_show_rate(self):
        past_sessions = self.sessions.filter(start_time__lt=timezone.now()).exclude(status__in=['scheduled', 'cancelled_by_teacher'])
        total = past_sessions.count()
        if total == 0: return 0
        absent = past_sessions.filter(status='absent').count()
        return round((absent / total) * 100)
        
    @property
    def monthly_revenue(self):
        today = timezone.localdate(timezone=CAIRO_TZ)
        start_of_month = today.replace(day=1)
        return self.sessions.filter(
            start_time__date__gte=start_of_month, 
            status__in=['attended', 'absent']
        ).aggregate(Sum('price'))['price__sum'] or Decimal('0.00')


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
        ('cancelled_by_teacher', _('Cancelled by Tutor 🚫')),
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
    def tutor_time(self):
        return self.start_time.astimezone(CAIRO_TZ)
        
    @property
    def student_time(self):
        return self.start_time.astimezone(self.student.student_timezone)

    @property
    def tutor_time_formatted(self):
        return self.tutor_time.strftime("%I:%M %p").lstrip("0")
        
    @property
    def student_time_formatted(self):
        return self.student_time.strftime("%I:%M %p").lstrip("0")

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
