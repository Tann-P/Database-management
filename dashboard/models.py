from django.db import models
from django.utils import timezone
import os

class DataUpload(models.Model):
    """Model to store uploaded data files"""
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return self.title
    
    def filename(self):
        if self.file:
            return os.path.basename(self.file.name)
        return "No file"
    
    def get_extension(self):
        if self.file:
            name, extension = os.path.splitext(self.file.name)
            return extension.lower()
        return ""

class DataPreview(models.Model):
    """Model to store preview data from uploads"""
    upload = models.ForeignKey(DataUpload, on_delete=models.CASCADE, related_name='previews')
    sheet_name = models.CharField(max_length=100, default='Sheet1')
    column_name = models.CharField(max_length=100)
    column_data_type = models.CharField(max_length=50)
    sample_data = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.upload.title} - {self.column_name}"
