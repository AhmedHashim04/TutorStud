from django.urls import path
from . import views

app_name = 'scheduler'

urlpatterns = [
    # Main Command Center
    path('', views.dashboard, name='dashboard'),
    
    # Fast Actions
    path('add-student/', views.add_student, name='add_student'),
    path('add-session/', views.add_session, name='add_session'),
    path('session/<int:pk>/status/', views.update_session_status, name='update_session_status'),
    path('session/<int:pk>/delete/', views.delete_session, name='delete_session'),
    path('generate-sessions/', views.generate_sessions_view, name='generate_sessions'),
    
    # Basic Settings
    path('settings/', views.settings_view, name='settings'),
]
