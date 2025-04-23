from .models import ActivityLog

def log_activity(request, action_type, description):
    """
    Helper function to create activity logs
    
    Args:
        request: The HTTP request object
        action_type: Type of action (from ActivityLog.ACTION_TYPES)
        description: Description of the activity
    """
    user = None
    if request.user.is_authenticated:
        user = request.user.username
    
    # Get client IP address
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(',')[0]
    else:
        ip_address = request.META.get('REMOTE_ADDR')
    
    # Get user agent
    user_agent = request.META.get('HTTP_USER_AGENT')
    
    # Create activity log
    ActivityLog.objects.create(
        action_type=action_type,
        description=description,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent
    )