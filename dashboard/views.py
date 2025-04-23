from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView
from django.http import JsonResponse, HttpResponse
from django.core.cache import cache
from django.conf import settings

from .models import DataUpload, DataPreview, UserRegistration, ActivityLog
from .forms import DataUploadForm, UserRegistrationForm
from .utils import log_activity

import pandas as pd
import numpy as np
import json
import sys
import os
import xlsxwriter
from io import BytesIO
from datetime import datetime

# Cache timeout in seconds (10 minutes)
CACHE_TIMEOUT = 60 * 10

@login_required
def index(request):
    """Dashboard home page"""
    # Get recent uploads
    uploads = DataUpload.objects.all().order_by('-uploaded_at')
    recent_uploads = uploads[:5]
    
    # Calculate statistics for dashboard cards
    upload_count = uploads.count()
    latest_upload_date = uploads.first().uploaded_at.strftime("%b %d, %Y") if uploads.exists() else "No uploads yet"
    
    # File type distribution for the chart (match the chart.js labels: 'Excel', 'CSV', 'JSON', 'Other')
    file_types = {"xlsx": 0, "xls": 0, "csv": 0, "json": 0, "other": 0}
    total_size = 0
    
    for upload in uploads:
        ext = upload.get_extension().lstrip('.')
        if ext in ['xlsx', 'xls']:
            file_types["xlsx"] += 1  # Count both xlsx/xls as Excel
        elif ext in file_types:
            file_types[ext] += 1
        else:
            file_types["other"] += 1
            
        # Calculate file size if file exists
        if upload.file and os.path.exists(upload.file.path):
            total_size += os.path.getsize(upload.file.path)
    
    # Format the total size nicely
    if total_size > 1024 * 1024 * 1024:  # GB
        total_size_formatted = f"{total_size / (1024 * 1024 * 1024):.2f} GB"
    elif total_size > 1024 * 1024:  # MB
        total_size_formatted = f"{total_size / (1024 * 1024):.2f} MB"
    elif total_size > 1024:  # KB
        total_size_formatted = f"{total_size / 1024:.2f} KB"
    else:
        total_size_formatted = f"{total_size} B"
    
    # Format data for chart.js
    file_formats_count = len([ft for ft, count in file_types.items() if count > 0])
    
    # Convert raw counts to percentages for Chart.js
    # Note: Chart.js labels are ['Excel', 'CSV', 'JSON', 'Other']
    if uploads.exists() and sum(file_types.values()) > 0:
        total_files = sum(file_types.values())
        excel_count = file_types["xlsx"] + file_types["xls"]  # Combine Excel formats
        
        file_type_distribution = [
            round((excel_count / total_files) * 100 if total_files > 0 else 0),
            round((file_types["csv"] / total_files) * 100 if total_files > 0 else 0),
            round((file_types["json"] / total_files) * 100 if total_files > 0 else 0),
            round((file_types["other"] / total_files) * 100 if total_files > 0 else 0)
        ]
    else:
        file_type_distribution = [25, 25, 25, 25]  # Default equal distribution for empty chart
    
    context = {
        'recent_uploads': recent_uploads,
        'upload_count': upload_count,
        'total_size': total_size_formatted,
        'latest_upload_date': latest_upload_date,
        'file_formats_count': file_formats_count,
        'file_type_distribution': file_type_distribution
    }
    
    return render(request, 'dashboard/index.html', context)

@login_required
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

@login_required
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

class DataUploadListView(LoginRequiredMixin, ListView):
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

@login_required
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

@login_required
def delete_upload(request, pk):
    """Delete an uploaded file"""
    upload = get_object_or_404(DataUpload, pk=pk)
    
    if request.method == 'POST':
        # Delete the actual file from storage
        if upload.file and os.path.isfile(upload.file.path):
            try:
                os.remove(upload.file.path)
            except OSError:
                pass  # File might already be deleted or inaccessible
        
        # Clear any cache entries for this upload
        cache_key = f'data_preview_{pk}'
        cache.delete(cache_key)
        
        # Store the name for feedback message
        filename = upload.filename()
        
        # Delete the database record (this will cascade delete related DataPreview objects)
        upload.delete()
        
        messages.success(request, f'File "{filename}" has been deleted successfully.')
        return redirect('dashboard:upload_list')
    
    # If not POST, show confirmation page (though we use modal in template)
    return render(request, 'dashboard/upload_confirm_delete.html', {'upload': upload})

@login_required
def visualize_data(request):
    """Data visualization page"""
    uploads = DataUpload.objects.all().order_by('-uploaded_at')
    
    context = {
        'uploads': uploads,
    }
    
    return render(request, 'dashboard/visualize.html', context)

@login_required
def analytics(request):
    """Data analytics page"""
    uploads = DataUpload.objects.all().order_by('-uploaded_at')
    
    context = {
        'uploads': uploads,
    }
    
    return render(request, 'dashboard/analytics.html', context)

@login_required
def reports(request):
    """Reports page"""
    uploads = DataUpload.objects.all().order_by('-uploaded_at')
    
    context = {
        'uploads': uploads,
    }
    
    return render(request, 'dashboard/reports.html', context)

@login_required
def export_data(request, pk=None):
    """Export data to various formats"""
    if pk:
        upload = get_object_or_404(DataUpload, pk=pk)
        # Process specific file export
        messages.success(request, f'Export of "{upload.filename()}" initiated. Download will begin shortly.')
        return redirect('dashboard:data_preview', pk=pk)
    else:
        # Export all or filtered data
        messages.success(request, 'Data export prepared. Download will begin shortly.')
        return redirect('dashboard:upload_list')

# Registration views - publicly accessible
def register_user(request):
    """Handle user registration"""
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                # Save the registration
                registration = form.save()
                
                # Log the registration activity
                log_activity(
                    request=request,
                    action_type='registration',
                    description=f'New user registration: {registration.full_name} (ID: {registration.citizen_id})'
                )
                
                messages.success(request, 'Registration completed successfully!')
                return redirect('dashboard:registration_success', pk=registration.pk)
            except Exception as e:
                messages.error(request, f'Error during registration: {str(e)}')
                return render(request, 'dashboard/register_form.html', {'form': form})
        else:
            # Display form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = UserRegistrationForm()
    
    return render(request, 'dashboard/register_form.html', {'form': form})

def registration_success(request, pk):
    """Registration success page"""
    registration = get_object_or_404(UserRegistration, pk=pk)
    
    context = {
        'registration': registration
    }
    
    return render(request, 'dashboard/registration_success.html', context)

class RegistrationListView(LoginRequiredMixin, ListView):
    """List all registered users"""
    model = UserRegistration
    template_name = 'dashboard/registration_list.html'
    context_object_name = 'registrations'
    ordering = ['-registered_at']
    paginate_by = 10

@login_required
def export_registrations(request):
    """Export registration data to Excel"""
    # Create a BytesIO object to store Excel file
    output = BytesIO()
    
    # Create a workbook and add a worksheet
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('Registrations')
    
    # Add headers with formatting
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#4e73df',  # Match Bootstrap primary color
        'color': 'white',
        'border': 1
    })
    
    headers = ['Full Name', 'Citizen ID', 'Phone Number', 'Email', 'Registration Date']
    for col_num, header in enumerate(headers):
        worksheet.write(0, col_num, header, header_format)
    
    # Get all registrations
    registrations = UserRegistration.objects.all().order_by('-registered_at')
    
    # Add data to worksheet
    row_num = 1
    for registration in registrations:
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss'})
        worksheet.write(row_num, 0, registration.full_name)
        worksheet.write(row_num, 1, registration.citizen_id)
        worksheet.write(row_num, 2, registration.phone_number)
        worksheet.write(row_num, 3, registration.email)
        worksheet.write(row_num, 4, registration.registered_at, date_format)
        row_num += 1
    
    # Auto-adjust column widths
    for i, col in enumerate(headers):
        worksheet.set_column(i, i, len(col) + 10)
    
    # Close the workbook
    workbook.close()
    
    # Set response headers for file download
    output.seek(0)
    filename = f'registrations_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    # Log the activity
    log_activity(
        request=request,
        action_type='export',
        description=f'Exported registration data to Excel. {row_num-1} records exported.'
    )
    
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    
    messages.success(request, 'Registration data exported successfully!')
    return response

@login_required
def activity_logs(request):
    """Activity log dashboard for administrators"""
    logs = ActivityLog.objects.all().order_by('-timestamp')
    
    # Add filtering capability
    action_type = request.GET.get('action_type', '')
    user = request.GET.get('user', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if action_type:
        logs = logs.filter(action_type=action_type)
    
    if user:
        logs = logs.filter(user__icontains=user)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            logs = logs.filter(timestamp__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            # Add a day to include the end date fully
            date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
            logs = logs.filter(timestamp__lte=date_to_obj)
        except ValueError:
            pass
    
    # Log this view action
    if not (action_type or user or date_from or date_to):
        log_activity(
            request=request,
            action_type='view',
            description='Viewed activity logs'
        )
    
    # Get unique action types and users for filters
    action_types = ActivityLog.ACTION_TYPES
    users = ActivityLog.objects.values_list('user', flat=True).distinct()
    
    context = {
        'logs': logs,
        'action_types': action_types,
        'unique_users': users,
        'selected_action_type': action_type,
        'selected_user': user,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'dashboard/activity_logs.html', context)
