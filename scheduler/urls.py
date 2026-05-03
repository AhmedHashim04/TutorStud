from django.urls import path
from . import views

app_name = 'scheduler'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Students
    path('students/', views.student_list, name='student_list'),
    path('students/create/', views.student_create, name='student_create'),
    path('students/<int:pk>/', views.student_detail, name='student_detail'),
    path('students/<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('students/<int:pk>/delete/', views.student_delete, name='student_delete'),

    # Subscriptions
    path('students/<int:student_pk>/subscription/', views.subscription_edit, name='subscription_edit'),

    # Recurring Schedules
    path('students/<int:student_pk>/schedules/add/', views.recurring_schedule_create, name='recurring_schedule_create'),
    path('schedules/<int:pk>/edit/', views.recurring_schedule_edit, name='recurring_schedule_edit'),
    path('schedules/<int:pk>/delete/', views.recurring_schedule_delete, name='recurring_schedule_delete'),
    path('schedules/<int:pk>/generate/', views.recurring_schedule_generate, name='recurring_schedule_generate'),

    # Sessions / Calendar
    path('calendar/', views.calendar_view, name='calendar'),
    path('sessions/', views.session_list, name='session_list'),
    path('sessions/create/', views.session_create, name='session_create'),
    path('sessions/<int:pk>/', views.session_detail, name='session_detail'),
    path('sessions/<int:pk>/edit/', views.session_edit, name='session_edit'),
    path('sessions/<int:pk>/delete/', views.session_delete, name='session_delete'),
    path('sessions/<int:pk>/status/', views.session_status_update, name='session_status'),
    path('sessions/<int:pk>/reschedule/', views.session_reschedule, name='session_reschedule'),
    path('sessions/<int:pk>/makeup/', views.session_makeup, name='session_makeup'),

    # API endpoints
    path('api/sessions/', views.api_sessions, name='api_sessions'),
    path('api/suggest-slot/', views.api_suggest_slot, name='api_suggest_slot'),
    path('api/preview-schedule/', views.api_preview_schedule, name='api_preview_schedule'),

    # Working hours & exceptions
    path('settings/working-hours/', views.working_hours, name='working_hours'),
    path('settings/exceptions/', views.exception_days, name='exception_days'),
    path('settings/exceptions/<int:pk>/delete/', views.exception_day_delete, name='exception_day_delete'),
    path('settings/prayer-times/', views.prayer_times, name='prayer_times'),
    path('settings/prayer-times/<int:pk>/delete/', views.prayer_time_delete, name='prayer_time_delete'),

    # Reports & Analytics
    path('reports/', views.reports, name='reports'),
    path('analytics/', views.analytics, name='analytics'),
]
