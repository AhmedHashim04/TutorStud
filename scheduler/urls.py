from django.urls import path
from . import views

app_name = 'scheduler'

urlpatterns = [
    # Main Command Center
    path('', views.dashboard, name='dashboard'),
    
    # Calendar System
    path('calendar/', views.calendar_view, name='calendar'),
    path('api/calendar-events/', views.api_calendar_events, name='api_calendar_events'),
    
    # Analytics
    path('analytics/', views.analytics_dashboard, name='analytics'),
    path('api/analytics/', views.api_analytics, name='api_analytics'),
    
    # Students / Mini OS
    path('students/', views.student_list, name='student_list'),
    path('students/<int:pk>/', views.student_detail, name='student_detail'),
    path('students/<int:pk>/update-notes/', views.update_student_notes, name='update_student_notes'),
    path('students/<int:pk>/toggle-status/', views.toggle_student_status, name='toggle_student_status'),
    
    # Schedule Management (NEW)
    path('students/<int:student_id>/schedules/', views.student_schedules, name='student_schedules'),
    path('schedules/<int:pk>/edit/', views.edit_schedule, name='edit_schedule'),
    path('schedules/<int:pk>/delete/', views.delete_schedule, name='delete_schedule'),
    
    # Schedule Exceptions (NEW)
    path('students/<int:student_id>/exceptions/', views.manage_exceptions, name='manage_exceptions'),
    path('exceptions/<int:schedule_id>/create/', views.create_exception, name='create_exception'),
    path('exceptions/<int:pk>/edit/', views.edit_exception, name='edit_exception'),
    path('exceptions/<int:pk>/delete/', views.delete_exception, name='delete_exception'),
    
    # Fast Actions
    path('add-student/', views.add_student, name='add_student'),
    path('add-session/', views.add_session, name='add_session'),
    path('session/<int:pk>/status/', views.update_session_status, name='update_session_status'),
    path('session/<int:pk>/delete/', views.delete_session, name='delete_session'),
    path('generate-sessions/', views.generate_sessions_view, name='generate_sessions'),
    
    # Basic Settings & API
    path('settings/', views.settings_view, name='settings'),
    path('settings/fetch-prayers/', views.fetch_prayers, name='fetch_prayers'),
]
