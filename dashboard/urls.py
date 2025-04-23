from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_file, name='upload_file'),
    path('preview/<int:pk>/', views.data_preview, name='data_preview'),
    path('uploads/', views.DataUploadListView.as_view(), name='upload_list'),
    path('delete/<int:pk>/', views.delete_upload, name='delete_upload'),
    path('visualize/', views.visualize_data, name='visualize'),
    path('analytics/', views.analytics, name='analytics'),
    path('reports/', views.reports, name='reports'),
    path('export/', views.export_data, name='export'),
    path('export/<int:pk>/', views.export_data, name='export_file'),
    path('debug/', views.debug_upload, name='debug_upload'),
    # Registration URLs
    path('register/', views.register_user, name='register_user'),
    path('register/success/<int:pk>/', views.registration_success, name='registration_success'),
    path('registrations/', views.RegistrationListView.as_view(), name='registration_list'),
    path('registrations/export/', views.export_registrations, name='export_registrations'),
    # Activity logs
    path('activity-logs/', views.activity_logs, name='activity_logs'),
]