from django.urls import path
from . import views

urlpatterns = [
    # Employer Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Employer Command Center Dashboard
    path('', views.dashboard_view, name='dashboard'),
    path('employees/', views.employee_list_view, name='employee_list'),
    path('cleanup/', views.trigger_cleanup_view, name='trigger_cleanup'),
    path('recording/<int:pk>/download/', views.download_recording_view, name='download_recording'),
    path('recording/<int:pk>/delete/', views.delete_recording_view, name='delete_recording'),

    # REST APIs for Employee Laptop Software
    path('api/agent/register/', views.api_register_device, name='api_register_device'),
    path('api/agent/ping/', views.api_ping, name='api_ping'),
    path('api/agent/upload/', views.api_upload_chunk, name='api_upload_chunk'),
]
