from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def role_required(*roles):
    """
    Decorator for function-based views.
    Usage:
        @role_required('PRINCIPAL', 'VICE_PRINCIPAL')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')

            has_access = any(
                request.user.has_role(role)
                for role in roles
            )

            if not has_access:
                messages.error(
                    request,
                    'You do not have permission to access this page.'
                )
                return redirect('accounts:dashboard')

            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


def principal_required(view_func):
    return role_required('PRINCIPAL')(view_func)


def admin_staff_required(view_func):
    return role_required('PRINCIPAL', 'VICE_PRINCIPAL')(view_func)


def teaching_staff_required(view_func):
    return role_required(
        'PRINCIPAL', 'VICE_PRINCIPAL',
        'CLASS_TEACHER', 'SUBJECT_TEACHER'
    )(view_func)


def subject_teacher_required(view_func):
    """Only SUBJECT_TEACHER role can access"""
    return role_required('SUBJECT_TEACHER')(view_func)


def examiner_required(view_func):
    return role_required(
        'PRINCIPAL', 'VICE_PRINCIPAL', 'EXAMINER'
    )(view_func)


def class_teacher_required(view_func):
    return role_required(
        'PRINCIPAL', 'VICE_PRINCIPAL', 'CLASS_TEACHER'
    )(view_func)