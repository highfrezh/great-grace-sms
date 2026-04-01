from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from accounts.decorators import admin_staff_required
from .models import StaffProfile
from .forms import StaffUserForm, StaffProfileForm

User = get_user_model()


@login_required
@admin_staff_required
def staff_list(request):
    # Get all active staff
    staff_list = StaffProfile.objects.filter(
        is_active=True
    ).select_related('user').prefetch_related('user__roles').order_by('-user__date_joined')
    
    # Calculate teaching staff count
    teaching_staff_count = 0
    for s in staff_list:
        if s.user.roles.filter(name='TEACHER').exists():
            teaching_staff_count += 1
    
    # Get inactive staff
    inactive_staff = StaffProfile.objects.filter(
        is_active=False
    ).select_related('user').prefetch_related('user__roles').order_by('-user__date_joined')
    
    # Pagination for active staff
    paginator = Paginator(staff_list, 10)  # Show 10 staff per page
    page = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    return render(request, 'staff/staff_list.html', {
        'page_obj': page_obj,  # Pass paginated object
        'staff': page_obj,  # Also pass as staff for backward compatibility
        'inactive_staff': inactive_staff,
        'teaching_staff_count': teaching_staff_count,
        'page_title': 'Staff Management'
    })


@login_required
@admin_staff_required
@transaction.atomic
def staff_create(request):
    user_form = StaffUserForm(request.POST or None)
    profile_form = StaffProfileForm(
        request.POST or None,
        request.FILES or None
    )

    if request.method == 'POST':
        if user_form.is_valid() and profile_form.is_valid():
            # Create user account
            user = user_form.save(commit=False)

            # Get phone from form cleaned data
            phone = user_form.cleaned_data.get('phone_number', '').strip()
            
            if not phone:
                phone = 'changeme123'
                
            user.set_password(phone)
            user.is_first_login = True
            user.phone_number = phone
            user.save()

            # Assign roles
            user_form.save_m2m()

            # Create staff profile
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.save()

            messages.success(
                request,
                f'Staff account created for {user.get_full_name()}. '
                f'Default password is their phone number.'
            )
            return redirect('staff:staff_list')
        else:
            messages.error(request, 'Please fix the errors below.')

    return render(request, 'staff/staff_form.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'page_title': 'Add New Staff',
        'is_edit': False
    })


@login_required
@admin_staff_required
@transaction.atomic
def staff_edit(request, pk):
    profile = get_object_or_404(StaffProfile, pk=pk)
    user = profile.user

    user_form = StaffUserForm(
        request.POST or None,
        instance=user
    )
    profile_form = StaffProfileForm(
        request.POST or None,
        request.FILES or None,
        instance=profile
    )

    if request.method == 'POST':
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(
                request,
                f'{user.get_full_name()} updated successfully.'
            )
            return redirect('staff:staff_detail', pk=profile.pk)
        else:
            messages.error(request, 'Please fix the errors below.')

    return render(request, 'staff/staff_form.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'page_title': f'Edit — {user.get_full_name()}',
        'is_edit': True,
        'profile': profile
    })


@login_required
@admin_staff_required
def staff_detail(request, pk):
    profile = get_object_or_404(
        StaffProfile.objects.select_related('user')
        .prefetch_related('user__roles'),
        pk=pk
    )
    return render(request, 'staff/staff_detail.html', {
        'profile': profile,
        'page_title': profile.full_name
    })


@login_required
@admin_staff_required
def staff_deactivate(request, pk):
    profile = get_object_or_404(StaffProfile, pk=pk)
    if request.method == 'POST':
        profile.is_active = False
        profile.user.is_active = False
        profile.user.save()
        profile.save()
        messages.success(
            request,
            f'{profile.full_name} has been deactivated.'
        )
    return redirect('staff:staff_list')


@login_required
@admin_staff_required
def staff_activate(request, pk):
    profile = get_object_or_404(StaffProfile, pk=pk)
    profile.is_active = True
    profile.user.is_active = True
    profile.user.save()
    profile.save()
    messages.success(
        request,
        f'{profile.full_name} has been reactivated.'
    )
    return redirect('staff:staff_list')


@login_required
@admin_staff_required
def staff_delete(request, pk):
    """Permanently delete a staff member"""
    profile = get_object_or_404(StaffProfile, pk=pk)
    user = profile.user
    
    if request.method == 'POST':
        name = profile.full_name
        # Delete user (this will cascade delete the profile due to OneToOne)
        user.delete()
        messages.success(
            request,
            f'{name} has been permanently deleted from the system.'
        )
    return redirect('staff:staff_list')


@login_required
@admin_staff_required
def staff_reset_password(request, pk):
    profile = get_object_or_404(StaffProfile, pk=pk)
    if request.method == 'POST':
        # Reset to phone number
        phone = profile.user.phone_number or 'changeme123'
        profile.user.set_password(phone)
        profile.user.is_first_login = True
        profile.user.save()
        messages.success(
            request,
            f'Password reset for {profile.full_name}. '
            f'New password is their phone number.'
        )
    return redirect('staff:staff_detail', pk=pk)