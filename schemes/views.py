from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from accounts.decorators import admin_staff_required
from academics.models import AcademicSession, Term, ClassArm, Subject
from students.models import Student
from .models import SchemeOfWork
from .forms import SchemeOfWorkForm

@login_required
def scheme_list(request):
    """
    List schemes of work. 
    Students: Only their current class arm.
    Teachers: All arms or restricted (currently all for view/download).
    VP/Admin: All with management links.
    """
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    
    schemes = SchemeOfWork.objects.select_related('session', 'term', 'class_arm', 'subject', 'uploaded_by')
    
    # Permission Restriction
    session_id = request.GET.get('session')
    student_id = request.GET.get('student_id')
    student_profile = None
    
    if student_id and (request.user.is_parent or request.user.is_superuser):
        student_profile = get_object_or_404(Student, id=student_id)
        if request.user.is_parent:
            if not request.user.guardian_profiles.filter(student=student_profile, phone=request.user.phone_number).exists():
                messages.error(request, "Access denied.")
                return redirect('accounts:dashboard')
    elif request.user.is_student:
        student_profile = getattr(request.user, 'student_profile', None)

    if student_profile:
        # Get current enrollment class arm for the student
        # If a session/term filter is active, use that, otherwise use current
        target_session = current_session
        if session_id:
            try: target_session = AcademicSession.objects.get(id=session_id)
            except: pass
            
        enrollment = student_profile.enrollments.filter(session=target_session).first()
        if enrollment:
            schemes = schemes.filter(class_arm=enrollment.class_arm)
        else:
            schemes = schemes.none()
    elif not request.user.is_admin_staff and not request.user.is_teaching_staff:
        # If not student/parent and not staff, see nothing
        schemes = schemes.none()

    # Filtering
    term_id = request.GET.get('term')
    class_arm_id = request.GET.get('class_arm')
    
    if session_id: schemes = schemes.filter(session_id=session_id)
    if term_id: schemes = schemes.filter(term_id=term_id)
    if class_arm_id: schemes = schemes.filter(class_arm_id=class_arm_id)
    
    # Filter data for dropdowns
    available_sessions = AcademicSession.objects.all().order_by('-start_date')
    
    # Base query for terms and arms
    if session_id:
        available_terms = Term.objects.filter(session_id=session_id)
        available_class_arms = ClassArm.objects.filter(session_id=session_id)
    else:
        available_terms = Term.objects.filter(session=current_session) if current_session else Term.objects.all()
        available_class_arms = ClassArm.objects.filter(session=current_session) if current_session else ClassArm.objects.all()

    # Restricted view for Students/Parents: Only show their own class in the dropdown
    if student_profile:
        # Get enrollment for the session being viewed
        view_session_id = session_id or (current_session.id if current_session else None)
        if view_session_id:
            enrolled_arms = student_profile.enrollments.filter(session_id=view_session_id).values_list('class_arm_id', flat=True)
            available_class_arms = available_class_arms.filter(id__in=enrolled_arms)
        else:
            available_class_arms = available_class_arms.none()

    return render(request, 'schemes/scheme_list.html', {
        'schemes': schemes,
        'page_title': 'Schemes of Work',
        'available_sessions': available_sessions,
        'available_terms': available_terms,
        'available_class_arms': available_class_arms,
        'selected_session': session_id,
        'selected_term': term_id,
        'selected_class_arm': class_arm_id,
        'student_id': student_id,
    })

@login_required
@admin_staff_required
def scheme_create(request):
    if request.method == 'POST':
        form = SchemeOfWorkForm(request.POST, request.FILES)
        if form.is_valid():
            scheme = form.save(commit=False)
            scheme.uploaded_by = request.user
            scheme.save()
            messages.success(request, 'Scheme of Work uploaded successfully.')
            return redirect('schemes:scheme_list')
    else:
        form = SchemeOfWorkForm()
    
    return render(request, 'schemes/scheme_form.html', {
        'form': form,
        'page_title': 'Upload Scheme of Work',
        'is_edit': False
    })

@login_required
@admin_staff_required
def scheme_edit(request, pk):
    scheme = get_object_or_404(SchemeOfWork, pk=pk)
    if request.method == 'POST':
        form = SchemeOfWorkForm(request.POST, request.FILES, instance=scheme)
        if form.is_valid():
            form.save()
            messages.success(request, 'Scheme of Work updated successfully.')
            return redirect('schemes:scheme_list')
    else:
        form = SchemeOfWorkForm(instance=scheme)
    
    return render(request, 'schemes/scheme_form.html', {
        'form': form,
        'page_title': f'Edit Scheme — {scheme.subject.name}',
        'is_edit': True
    })

@login_required
@admin_staff_required
def scheme_delete(request, pk):
    scheme = get_object_or_404(SchemeOfWork, pk=pk)
    if request.method == 'POST':
        scheme_name = str(scheme)
        scheme.delete()
        messages.success(request, f'Scheme "{scheme_name}" deleted.')
        return redirect('schemes:scheme_list')
    
    return render(request, 'schemes/scheme_confirm_delete.html', {
        'scheme': scheme,
        'page_title': 'Delete Scheme of Work'
    })

from django.http import JsonResponse
from academics.models import ClassArmSubject

@login_required
def load_subjects(request):
    class_arm_id = request.GET.get('class_arm')
    subjects = ClassArmSubject.objects.filter(class_arm_id=class_arm_id).select_related('subject')
    
    subject_list = [
        {'id': cas.subject.id, 'name': cas.subject.name}
        for cas in subjects
    ]
    return JsonResponse(subject_list, safe=False)
