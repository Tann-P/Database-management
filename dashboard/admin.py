from django.contrib import admin
from .models import DataUpload, DataPreview

class DataPreviewInline(admin.TabularInline):
    model = DataPreview
    extra = 0
    readonly_fields = ['sheet_name', 'column_name', 'column_data_type', 'sample_data']
    can_delete = False
    max_num = 0

@admin.register(DataUpload)
class DataUploadAdmin(admin.ModelAdmin):
    list_display = ['title', 'display_filename', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['title', 'description']
    readonly_fields = ['display_filename', 'get_extension']
    date_hierarchy = 'uploaded_at'
    inlines = [DataPreviewInline]
    
    def display_filename(self, obj):
        return obj.filename()
    
    display_filename.short_description = 'File Name'
