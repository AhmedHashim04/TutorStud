from django.urls import path
from . import views

app_name = 'scheduler'

urlpatterns = [
    # Main Command Center
    path('', views.dashboard, name='dashboard'),
    
    # Students / Mini OS
    path('students/', views.student_list, name='student_list'),
    path('students/<int:pk>/', views.student_detail, name='student_detail'),
    path('students/<int:pk>/update-notes/', views.update_student_notes, name='update_student_notes'),
    
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
