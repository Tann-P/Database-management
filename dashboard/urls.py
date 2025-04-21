from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),  # Changed from 'dashboard' to 'index' to match templates
    path('upload/', views.upload_file, name='upload_file'),
    path('preview/<int:pk>/', views.data_preview, name='data_preview'),
    path('uploads/', views.DataUploadListView.as_view(), name='upload_list'),
    path('debug/', views.debug_upload, name='debug_upload'),  # New debug URL
]