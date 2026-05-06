from django.contrib import admin
from .models import Student, Subscription, StudentEnrollment, GlobalConfig, WorkingHours, WorkingHoursRange, ExceptionDay, PrayerTime, Session, SessionAttendance, SessionPayment, RecurringSchedule


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(GlobalConfig)
class GlobalConfigAdmin(admin.ModelAdmin):
    list_display = ['default_session_price', 'default_session_duration', 'cancellation_window_hours', 'allow_makeup_sessions', 'allow_extra_sessions', 'updated_at']


@admin.register(StudentEnrollment)
class StudentEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'session_price', 'session_duration', 'cancellation_window_hours', 'is_active', 'start_date']
    list_filter = ['is_active', 'session_duration', 'allow_makeup_sessions', 'allow_extra_sessions']


@admin.register(RecurringSchedule)
class RecurringScheduleAdmin(admin.ModelAdmin):
    list_display = ['student', 'day_of_week', 'start_time', 'duration', 'is_active']
    list_filter = ['day_of_week', 'is_active']


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
    list_display = ['student', 'start_time', 'end_time', 'status', 'session_type', 'is_makeup']
    list_filter = ['status', 'session_type', 'is_makeup', 'is_recurring']
    search_fields = ['student__name']


@admin.register(SessionAttendance)
class SessionAttendanceAdmin(admin.ModelAdmin):
    list_display = ['session', 'attendance_status', 'marked_at']
    list_filter = ['attendance_status']


@admin.register(SessionPayment)
class SessionPaymentAdmin(admin.ModelAdmin):
    list_display = ['session', 'base_amount', 'final_amount', 'rule_applied', 'is_paid']
    list_filter = ['is_paid', 'rule_applied']
