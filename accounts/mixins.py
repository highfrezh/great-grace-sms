from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages


class RoleRequiredMixin(LoginRequiredMixin):
    """
    Mixin to restrict views to specific roles.
    Usage:
        class MyView(RoleRequiredMixin, View):
            required_roles = ['PRINCIPAL', 'VICE_PRINCIPAL']
    """
    required_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if self.required_roles:
            has_access = any(
                request.user.has_role(role)
                for role in self.required_roles
            )
            if not has_access:
                messages.error(
                    request,
                    'You do not have permission to access this page.'
                )
                return redirect('accounts:dashboard')

        return super().dispatch(request, *args, **kwargs)


class PrincipalRequiredMixin(RoleRequiredMixin):
    required_roles = ['PRINCIPAL']


class AdminStaffRequiredMixin(RoleRequiredMixin):
    required_roles = ['PRINCIPAL', 'VICE_PRINCIPAL']


class TeachingStaffRequiredMixin(RoleRequiredMixin):
    required_roles = [
        'PRINCIPAL',
        'VICE_PRINCIPAL',
        'CLASS_TEACHER',
        'SUBJECT_TEACHER'
    ]


class ExaminerRequiredMixin(RoleRequiredMixin):
    required_roles = ['PRINCIPAL', 'VICE_PRINCIPAL', 'EXAMINER']


class StudentRequiredMixin(RoleRequiredMixin):
    required_roles = ['STUDENT']


class ParentRequiredMixin(RoleRequiredMixin):
    required_roles = ['PARENT']