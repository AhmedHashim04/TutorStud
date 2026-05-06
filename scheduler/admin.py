from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import (
    Student, Session, RecurringSchedule, GlobalSettings, 
    PrayerTime, ScheduleException, SessionDurationOption
)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'session_price', 'is_active', 'created_at')
    list_filter = ('is_active', 'country', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'attendance_rate', 'no_show_rate', 'monthly_revenue')
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'country', 'is_active')
        }),
        (_('Session Settings'), {
            'fields': ('session_duration', 'session_price')
        }),
        (_('Notes'), {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        (_('Statistics'), {
            'fields': ('attendance_rate', 'no_show_rate', 'monthly_revenue'),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )


@admin.register(RecurringSchedule)
class RecurringScheduleAdmin(admin.ModelAdmin):
    list_display = ('student', 'get_weekday_display', 'start_time', 'is_active', 'updated_at')
    list_filter = ('is_active', 'weekday', 'updated_at')
    search_fields = ('student__name',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (_('Schedule Rule'), {
            'fields': ('student', 'weekday', 'start_time', 'is_active')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_weekday_display(self, obj):
        return obj.get_weekday_display()
    get_weekday_display.short_description = _('Weekday')


@admin.register(ScheduleException)
class ScheduleExceptionAdmin(admin.ModelAdmin):
    list_display = ('schedule', 'get_exception_type_display', 'week_start_date', 'reason', 'created_at')
    list_filter = ('exception_type', 'week_start_date', 'created_at')
    search_fields = ('schedule__student__name', 'reason')
    readonly_fields = ('created_at', 'get_detailed_description')
    
    fieldsets = (
        (_('Exception'), {
            'fields': ('schedule', 'exception_type', 'week_start_date', 'reason')
        }),
        (_('Move Session (if applicable)'), {
            'fields': ('move_to_date', 'move_to_time'),
            'classes': ('collapse',)
        }),
        (_('Add Sessions (if applicable)'), {
            'fields': ('add_date', 'add_time', 'add_count'),
            'classes': ('collapse',)
        }),
        (_('Details'), {
            'fields': ('created_at', 'created_by', 'get_detailed_description'),
            'classes': ('collapse',)
        })
    )
    
    def get_exception_type_display(self, obj):
        return obj.get_exception_type_display()
    get_exception_type_display.short_description = _('Type')


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('student', 'start_time', 'duration', 'status', 'price', 'is_payable')
    list_filter = ('status', 'start_time', 'created_at')
    search_fields = ('student__name',)
    readonly_fields = ('created_at', 'end_time', 'tutor_time', 'student_time')
    
    fieldsets = (
        (_('Session Details'), {
            'fields': ('student', 'start_time', 'end_time', 'duration', 'status')
        }),
        (_('Pricing'), {
            'fields': ('price', 'is_payable')
        }),
        (_('Notes'), {
            'fields': ('notes',)
        }),
        (_('Timezone Info'), {
            'fields': ('tutor_time', 'student_time'),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def is_payable(self, obj):
        return obj.is_payable
    is_payable.boolean = True
    is_payable.short_description = _('Payable')


@admin.register(GlobalSettings)
class GlobalSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PrayerTime)
class PrayerTimeAdmin(admin.ModelAdmin):
    list_display = ('date', 'get_prayer_display', 'adhan_time', 'duration')
    list_filter = ('date', 'prayer')
    search_fields = ('date',)
    
    fieldsets = (
        (_('Prayer Time'), {
            'fields': ('date', 'prayer', 'adhan_time', 'duration')
        }),
    )


@admin.register(SessionDurationOption)
class SessionDurationOptionAdmin(admin.ModelAdmin):
    list_display = ('duration_minutes',)
    search_fields = ('duration_minutes',)
