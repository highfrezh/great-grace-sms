from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(
                request,
                f'Welcome back, {user.get_full_name() or user.username}!'
            )
            return redirect('accounts:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('accounts:login')


@login_required
def dashboard_view(request):
    user = request.user
    primary = user.primary_role if not user.is_superuser else 'PRINCIPAL'

    if primary == 'STUDENT':
        return render(request, 'accounts/dashboard_student.html')
    elif primary == 'PARENT':
        return render(request, 'accounts/dashboard_parent.html')
    else:
        # Principal, VP, Examiner, Class Teacher, Subject Teacher
        return render(request, 'accounts/dashboard.html')