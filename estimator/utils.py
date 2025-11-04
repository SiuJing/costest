# estimator/utils.py
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def qs_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        profile = request.user.userprofile
        if not (profile.role == 'qs' or request.user.is_staff):
            messages.error(request, "Only QS users can perform this action.")
            return redirect('project_detail', pk=kwargs.get('pk') or 1)
        return view_func(request, *args, **kwargs)
    return wrapper

def admin_or_qs_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        profile = request.user.userprofile
        if not (request.user.is_staff or profile.role in ['qs', 'admin']):
            messages.error(request, "Permission denied.")
            return redirect('project_detail', pk=kwargs.get('pk') or 1)
        return view_func(request, *args, **kwargs)
    return wrapper