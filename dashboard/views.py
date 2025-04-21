from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django_tables2 import SingleTableView
from django.urls import reverse
from django.core.cache import cache
from django.conf import settings

from .models import DataUpload, DataPreview
from .forms import DataUploadForm

import pandas as pd
import numpy as np
import json
import sys  # Added for debug_upload view
import os

# Cache timeout in seconds (10 minutes)
CACHE_TIMEOUT = 60 * 10

def index(request):
    """Dashboard home page"""
    recent_uploads = DataUpload.objects.all().order_by('-uploaded_at')[:5]
    return render(request, 'dashboard/index.html', {'recent_uploads': recent_uploads})

def upload_file(request):
    """Handle file uploads"""
    if request.method == 'POST':
        form = DataUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # Check if a file was actually provided
                if 'file' not in request.FILES:
                    messages.error(request, 'No file was selected. Please choose a file to upload.')
                    return render(request, 'dashboard/upload_form.html', {'form': form})
                
                # Save the uploaded file
                data_upload = form.save()
                
                # Process the uploaded file
                process_excel_file(data_upload)
                
                messages.success(request, 'File uploaded successfully!')
                return redirect('dashboard:data_preview', pk=data_upload.pk)
            except Exception as e:
                messages.error(request, f'Error uploading file: {str(e)}')
                # Log the error for debugging
                print(f"Upload error: {str(e)}")
                return render(request, 'dashboard/upload_form.html', {'form': form})
        else:
            # Display form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = DataUploadForm()
    
    return render(request, 'dashboard/upload_form.html', {'form': form})

def data_preview(request, pk):
    upload = get_object_or_404(DataUpload, pk=pk)
    
    # Try to get cached data first
    cache_key = f'data_preview_{pk}'
    preview_data = cache.get(cache_key)
    
    if not preview_data:
        # Cache miss, process the data
        file_path = os.path.join(settings.MEDIA_ROOT, upload.file.name)
        
        if upload.get_extension() in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path)
        else:  # CSV
            df = pd.read_csv(file_path)
            
        # Basic data statistics
        stats = {
            'row_count': len(df),
            'column_count': len(df.columns),
            'memory_usage': df.memory_usage(deep=True).sum() / (1024 * 1024),  # MB
        }
        
        # Generate column statistics
        column_stats = []
        for col in df.columns:
            col_type = str(df[col].dtype)
            
            # Calculate statistics based on data type
            if pd.api.types.is_numeric_dtype(df[col]):
                col_stats = {
                    'name': col,
                    'type': col_type,
                    'min': df[col].min() if not df[col].isna().all() else 'N/A',
                    'max': df[col].max() if not df[col].isna().all() else 'N/A',
                    'mean': df[col].mean() if not df[col].isna().all() else 'N/A',
                    'null_count': df[col].isna().sum(),
                    'null_percentage': round((df[col].isna().sum() / len(df)) * 100, 2)
                }
            else:
                unique_values = df[col].nunique()
                col_stats = {
                    'name': col,
                    'type': col_type,
                    'unique_values': unique_values,
                    'most_common': df[col].value_counts().index[0] if unique_values > 0 and unique_values < len(df) / 2 else 'Too many to display',
                    'null_count': df[col].isna().sum(),
                    'null_percentage': round((df[col].isna().sum() / len(df)) * 100, 2)
                }
            column_stats.append(col_stats)
            
        # Get sample data (first 50 rows)
        sample_data = df.head(50).to_dict('records')
        columns = list(df.columns)
        
        preview_data = {
            'stats': stats,
            'column_stats': column_stats,
            'sample_data': sample_data,
            'columns': columns
        }
        
        # Save to cache
        cache.set(cache_key, preview_data, CACHE_TIMEOUT)
        
        # Save preview data to database
        try:
            data_preview_obj, created = DataPreview.objects.update_or_create(
                data_upload=upload,
                defaults={
                    'column_info': json.dumps(column_stats),
                    'row_count': stats['row_count'],
                    'preview_data': json.dumps(sample_data[:10])  # Store only first 10 rows
                }
            )
        except Exception as e:
            # Handle any database errors
            print(f"Error saving preview data: {e}")
    
    context = {
        'upload': upload,
        'stats': preview_data['stats'],
        'column_stats': preview_data['column_stats'],
        'sample_data': preview_data['sample_data'],
        'columns': preview_data['columns']
    }
    
    return render(request, 'dashboard/data_preview.html', context)

class DataUploadListView(ListView):
    """List all uploaded files"""
    model = DataUpload
    template_name = 'dashboard/upload_list.html'
    context_object_name = 'uploads'
    ordering = ['-uploaded_at']
    paginate_by = 10

def process_excel_file(data_upload):
    """Process uploaded Excel file and extract preview data"""
    try:
        file_ext = data_upload.get_extension()
        
        # Use chunking for larger files to improve memory usage
        chunksize = 1000  # Adjust based on expected file sizes
        
        if file_ext in ['.xlsx', '.xls']:
            excel = pd.ExcelFile(data_upload.file.path)
            sheet_name = excel.sheet_names[0]  # Use first sheet
            
            # Use optimized reading with specific dtypes if possible
            df = pd.read_excel(
                data_upload.file.path, 
                sheet_name=sheet_name,
                nrows=100  # Limit initial read for preview/analysis
            )
        elif file_ext == '.csv':
            # Use optimized CSV reading
            df = pd.read_csv(
                data_upload.file.path,
                nrows=100,  # Limit initial read for preview/analysis
                low_memory=True
            )
            sheet_name = 'CSV Data'
        else:
            print(f"Unsupported file extension: {file_ext}")
            return
        
        # Clear any existing previews for this upload
        DataPreview.objects.filter(upload=data_upload).delete()
        
        # Store column information in DataPreview model
        for column in df.columns:
            data_type = str(df[column].dtype)
            
            # Optimize sample data storage by using JSON serialization
            # and limiting to first 3 non-null values when possible
            sample_values = df[column].dropna().head(3).tolist()
            sample = json.dumps(sample_values)
            
            # Create preview entry
            DataPreview.objects.create(
                upload=data_upload,
                sheet_name=sheet_name,
                column_name=column,
                column_data_type=data_type,
                sample_data=sample
            )
            
        # Return total rows count for user feedback
        if file_ext in ['.xlsx', '.xls']:
            total_rows = len(pd.read_excel(data_upload.file.path, sheet_name=sheet_name, header=None))
        else:
            total_rows = sum(1 for _ in open(data_upload.file.path))
        
        return total_rows
    except Exception as e:
        print(f"Error processing file: {str(e)}")
        # Log the error properly
        import logging
        logging.error(f"File processing error: {str(e)}")
        return None

def debug_upload(request):
    """Debug view for file uploads"""
    upload_dir = None
    upload_dir_exists = False
    media_root = None
    
    try:
        from django.conf import settings
        import os
        
        # Check if media directory exists
        media_root = settings.MEDIA_ROOT
        media_root_exists = os.path.exists(media_root)
        
        # Check if uploads directory exists
        upload_dir = os.path.join(media_root, 'uploads')
        upload_dir_exists = os.path.exists(upload_dir)
        
        # Try to create the upload directory if it doesn't exist
        if not upload_dir_exists:
            try:
                os.makedirs(upload_dir, exist_ok=True)
                upload_dir_exists = os.path.exists(upload_dir)
            except Exception as e:
                upload_dir_error = str(e)
        
        # Test write permissions
        write_permission = False
        test_file_path = os.path.join(upload_dir, 'test_write.txt')
        write_error = None
        
        try:
            with open(test_file_path, 'w') as f:
                f.write('test')
            write_permission = True
            os.remove(test_file_path)  # Clean up
        except Exception as e:
            write_error = str(e)
            
        context = {
            'media_root': str(media_root),
            'media_root_exists': media_root_exists,
            'upload_dir': str(upload_dir),
            'upload_dir_exists': upload_dir_exists,
            'write_permission': write_permission,
            'write_error': write_error,
            'python_path': sys.path,
        }
        
        return render(request, 'dashboard/debug.html', context)
    except Exception as e:
        return render(request, 'dashboard/debug.html', {
            'error': str(e),
            'media_root': str(media_root),
            'upload_dir': str(upload_dir),
            'upload_dir_exists': upload_dir_exists,
        })
