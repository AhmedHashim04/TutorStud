from django.contrib import admin
from .models import Student, Subscription, WorkingHours, WorkingHoursRange, ExceptionDay, PrayerTime, Session


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'phone']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['student', 'sessions_per_week', 'session_duration', 'hourly_rate', 'is_active']
    list_filter = ['is_active', 'session_duration']


@admin.register(WorkingHours)
class WorkingHoursAdmin(admin.ModelAdmin):
    list_display = ['weekday', 'start_time', 'end_time', 'is_working']


@admin.register(WorkingHoursRange)
class WorkingHoursRangeAdmin(admin.ModelAdmin):
    list_display = ['working_hours', 'start_time', 'end_time']
    list_filter = ['working_hours__weekday']


@admin.register(ExceptionDay)
class ExceptionDayAdmin(admin.ModelAdmin):
    list_display = ['date', 'reason']


@admin.register(PrayerTime)
class PrayerTimeAdmin(admin.ModelAdmin):
    list_display = ['date', 'prayer', 'adhan_time']
    list_filter = ['prayer']


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ['student', 'start_time', 'end_time', 'status', 'is_makeup']
    list_filter = ['status', 'is_makeup', 'is_recurring']
    search_fields = ['student__name']
