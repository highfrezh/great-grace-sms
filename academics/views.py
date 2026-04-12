from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from accounts.decorators import admin_staff_required
from .models import AcademicSession, Term, ClassLevel, ClassArm, Subject, ClassArmSubject, SubjectTeacherAssignment
from .forms import (
    AcademicSessionForm, TermForm, ClassLevelForm,
    ClassArmForm, SubjectForm, SubjectTeacherAssignmentForm,
    SubjectSearchForm
)


# ── ACADEMIC SESSIONS ─────────────────────────────────────────

@login_required
@admin_staff_required
def session_list(request):
    sessions = AcademicSession.objects.all()
    return render(request, 'academics/session_list.html', {
        'sessions': sessions,
        'page_title': 'Academic Sessions'
    })


@login_required
@admin_staff_required
def session_create(request):
    form = AcademicSessionForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Academic session created successfully.')
        return redirect('academics:session_list')
    return render(request, 'academics/form.html', {
        'form': form,
        'page_title': 'Create Academic Session',
        'back_url': 'academics:session_list'
    })


@login_required
@admin_staff_required
def session_edit(request, pk):
    session = get_object_or_404(AcademicSession, pk=pk)
    form = AcademicSessionForm(request.POST or None, instance=session)
    if form.is_valid():
        form.save()
        messages.success(request, 'Academic session updated successfully.')
        return redirect('academics:session_list')
    return render(request, 'academics/form.html', {
        'form': form,
        'page_title': f'Edit Session — {session.name}',
        'back_url': 'academics:session_list'
    })


@login_required
@admin_staff_required
def session_set_current(request, pk):
    session = get_object_or_404(AcademicSession, pk=pk)
    AcademicSession.objects.update(is_current=False)
    session.is_current = True
    session.save()
    messages.success(request, f'{session.name} is now the current session.')
    return redirect('academics:session_list')

@login_required
@admin_staff_required
def session_delete(request, pk):
    session = get_object_or_404(AcademicSession, pk=pk)

    # Prevent deleting current session
    if session.is_current:
        messages.error(request, 'Cannot delete the current active session.')
        return redirect('academics:session_list')

    if request.method == 'POST':
        name = session.name
        session.delete()
        messages.success(request, f'Session {name} deleted successfully.')
        return redirect('academics:session_list')

    return redirect('academics:session_list')


# ── TERMS ─────────────────────────────────────────────────────

@login_required
@admin_staff_required
def term_list(request):
    current_session = AcademicSession.get_current()
    terms = Term.objects.select_related('session').all().order_by('-session__start_date', 'name')
    return render(request, 'academics/term_list.html', {
        'terms': terms,
        'current_session': current_session,
        'page_title': 'Terms'
    })


@login_required
@admin_staff_required
def term_create(request):
    form = TermForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Term created successfully.')
        return redirect('academics:term_list')
    return render(request, 'academics/form.html', {
        'form': form,
        'page_title': 'Create Term',
        'back_url': 'academics:term_list'
    })


@login_required
@admin_staff_required
def term_edit(request, pk):
    term = get_object_or_404(Term, pk=pk)
    form = TermForm(request.POST or None, instance=term)
    if form.is_valid():
        form.save()
        messages.success(request, 'Term updated successfully.')
        return redirect('academics:term_list')
    return render(request, 'academics/form.html', {
        'form': form,
        'page_title': f'Edit — {term}',
        'back_url': 'academics:term_list'
    })


@login_required
@admin_staff_required
def term_set_current(request, pk):
    term = get_object_or_404(Term, pk=pk)
    Term.objects.update(is_current=False)
    term.is_current = True
    term.save()
    messages.success(request, f'{term} is now the current term.')
    return redirect('academics:term_list')


# ── CLASS LEVELS ──────────────────────────────────────────────

@login_required
@admin_staff_required
def class_level_list(request):
    class_levels = ClassLevel.objects.all()
    return render(request, 'academics/class_level_list.html', {
        'class_levels': class_levels,
        'page_title': 'Class Levels'
    })


@login_required
@admin_staff_required
def class_level_create(request):
    form = ClassLevelForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Class level created successfully.')
        return redirect('academics:class_level_list')
    return render(request, 'academics/form.html', {
        'form': form,
        'page_title': 'Create Class Level',
        'back_url': 'academics:class_level_list'
    })


@login_required
@admin_staff_required
def class_level_edit(request, pk):
    class_level = get_object_or_404(ClassLevel, pk=pk)
    form = ClassLevelForm(request.POST or None, instance=class_level)
    if form.is_valid():
        form.save()
        messages.success(request, 'Class level updated successfully.')
        return redirect('academics:class_level_list')
    return render(request, 'academics/form.html', {
        'form': form,
        'page_title': f'Edit — {class_level.name}',
        'back_url': 'academics:class_level_list'
    })


# ── CLASS ARMS ────────────────────────────────────────────────

@login_required
@admin_staff_required
def class_arm_list(request):
    current_session = AcademicSession.get_current()
    class_arms = ClassArm.objects.filter(
        session=current_session
    ).select_related(
        'level', 'class_teacher', 'session'
    ) if current_session else ClassArm.objects.none()
    return render(request, 'academics/class_arm_list.html', {
        'class_arms': class_arms,
        'current_session': current_session,
        'page_title': 'Classes'
    })


@login_required
@admin_staff_required
def class_arm_create(request):
    form = ClassArmForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Class created successfully.')
        return redirect('academics:class_arm_list')
    return render(request, 'academics/form.html', {
        'form': form,
        'page_title': 'Create Class',
        'back_url': 'academics:class_arm_list'
    })


@login_required
@admin_staff_required
def class_arm_edit(request, pk):
    class_arm = get_object_or_404(ClassArm, pk=pk)
    form = ClassArmForm(request.POST or None, instance=class_arm)
    if form.is_valid():
        if form.has_changed():
            form.save()
            messages.success(request, 'Class updated successfully.')
        else:
            messages.info(request, 'No changes were made.')
        return redirect('academics:class_arm_list')
    return render(request, 'academics/form.html', {
        'form': form,
        'page_title': f'Edit — {class_arm}',
        'back_url': 'academics:class_arm_list'
    })


# ── SUBJECTS ──────────────────────────────────────────────────

@login_required
@admin_staff_required
def subject_list(request):
    form = SubjectSearchForm(request.GET or None)
    subjects = Subject.objects.all().prefetch_related('class_arms__class_arm')
    
    if form.is_valid():
        query = form.cleaned_data.get('query')
        class_arm = form.cleaned_data.get('class_arm')
        status = form.cleaned_data.get('status')
        
        if query:
            from django.db.models import Q
            subjects = subjects.filter(
                Q(name__icontains=query) |
                Q(code__icontains=query)
            )
            
        if class_arm:
            subjects = subjects.filter(class_arms__class_arm=class_arm)
            
        if status:
            if status == 'active':
                subjects = subjects.filter(is_active=True)
            elif status == 'inactive':
                subjects = subjects.filter(is_active=False)
                
    subjects = subjects.distinct()
    
    current_session = AcademicSession.get_current()
    class_arms = ClassArm.objects.filter(session=current_session).select_related('level').order_by('level__order', 'name') if current_session else ClassArm.objects.none()
    
    return render(request, 'academics/subject_list.html', {
        'subjects': subjects,
        'form': form,
        'class_arms': class_arms,
        'page_title': 'Subjects'
    })


@login_required
@admin_staff_required
def subject_create(request):
    form = SubjectForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Subject created successfully.')
        return redirect('academics:subject_list')
    return render(request, 'academics/form.html', {
        'form': form,
        'page_title': 'Create Subject',
        'back_url': 'academics:subject_list'
    })


@login_required
@admin_staff_required
def subject_edit(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    form = SubjectForm(request.POST or None, instance=subject)
    if form.is_valid():
        if form.has_changed():
            form.save()
            messages.success(request, 'Subject updated successfully.')
        else:
            messages.info(request, 'No changes were made.')
        return redirect('academics:subject_list')
    return render(request, 'academics/form.html', {
        'form': form,
        'page_title': f'Edit — {subject.name}',
        'back_url': 'academics:subject_list'
    })


@login_required
@admin_staff_required
def term_delete(request, pk):
    term = get_object_or_404(Term, pk=pk)
    if term.is_current:
        messages.error(request, 'Cannot delete the current active term.')
        return redirect('academics:term_list')
    if request.method == 'POST':
        term.delete()
        messages.success(request, 'Term deleted successfully.')
    return redirect('academics:term_list')


@login_required
@admin_staff_required
def class_level_delete(request, pk):
    level = get_object_or_404(ClassLevel, pk=pk)
    if request.method == 'POST':
        name = level.name
        level.delete()
        messages.success(request, f'Class level {name} deleted successfully.')
    return redirect('academics:class_level_list')


@login_required
@admin_staff_required
def class_arm_delete(request, pk):
    arm = get_object_or_404(ClassArm, pk=pk)
    if request.method == 'POST':
        name = arm.full_name
        arm.delete()
        messages.success(request, f'Class {name} deleted successfully.')
    return redirect('academics:class_arm_list')


@login_required
@admin_staff_required
def subject_delete(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        name = subject.name
        subject.delete()
        messages.success(request, f'Subject {name} deleted successfully.')
    return redirect('academics:subject_list')


@login_required
@admin_staff_required
def subject_toggle(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    subject.is_active = not subject.is_active
    subject.save()
    status = 'activated' if subject.is_active else 'deactivated'
    messages.success(request, f'{subject.name} {status} successfully.')
    return redirect('academics:subject_list')


from .models import SubjectTeacherAssignment
from .forms import SubjectTeacherAssignmentForm

@login_required
@admin_staff_required
def assignment_list(request):
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    assignments = SubjectTeacherAssignment.objects.filter(
        session=current_session,
        term=current_term
    ).select_related(
        'teacher', 'subject', 'class_arm', 'session', 'term'
    ).order_by('class_arm__level__order', 'class_arm__name', 'subject__name')

    return render(request, 'academics/assignment_list.html', {
        'assignments': assignments,
        'current_session': current_session,
        'current_term': current_term,
        'page_title': 'Subject-Teacher Assignments'
    })

# ---------------- Assignment Views ----------------
@login_required
@admin_staff_required
def assignment_create(request):
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    form = SubjectTeacherAssignmentForm(request.POST or None)
    if form.is_valid():
        try:
            form.save()
            messages.success(request, 'Assignment created successfully.')
            return redirect('academics:assignment_list')
        except IntegrityError:
            messages.error(request, 'This teacher is already assigned to this subject in the selected class for the current session and term.')
    return render(request, 'academics/assignment_form.html', {
        'form': form,
        'page_title': 'Assign Subject Teacher',
        'back_url': 'academics:assignment_list',
        'current_session': current_session,
        'current_term': current_term,
        'session_info': f'for {current_session} - {current_term}'
    })


@login_required
@admin_staff_required
def assignment_edit(request, pk):
    assignment = get_object_or_404(SubjectTeacherAssignment, pk=pk)
    form = SubjectTeacherAssignmentForm(request.POST or None, instance=assignment)
    if form.is_valid():
        if form.has_changed():
            form.save()
            messages.success(request, 'Assignment updated successfully.')
        else:
            messages.info(request, 'No changes were made.')
        return redirect('academics:assignment_list')
    return render(request, 'academics/assignment_form.html', {
        'form': form,
        'page_title': 'Edit Subject Teacher Assignment',
        'back_url': 'academics:assignment_list',
        'current_session': assignment.session,
        'current_term': assignment.term,
        'session_info': f'for {assignment.session} - {assignment.term}'
    })


@login_required
@admin_staff_required
def assignment_delete(request, pk):
    assignment = get_object_or_404(SubjectTeacherAssignment, pk=pk)
    if request.method == 'POST':
        assignment.delete()
        messages.success(request, 'Assignment removed successfully.')
    return redirect('academics:assignment_list')


@login_required
@admin_staff_required
def ajax_available_subjects(request):
    """API endpoint to fetch subjects available for assignment in a class arm"""
    class_arm_id = request.GET.get('class_arm')
    assignment_id = request.GET.get('assignment_id')  # For editing
    
    if not class_arm_id:
        return JsonResponse({'error': 'Missing class_arm parameter'}, status=400)
    
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    
    if not current_session or not current_term:
        return JsonResponse({'error': 'No active session/term'}, status=400)
    
    try:
        # Get the class arm
        class_arm = ClassArm.objects.get(pk=class_arm_id)
        
        # Get subjects available for this class arm (via ClassArmSubject relationship)
        available_subjects_for_arm = ClassArmSubject.objects.filter(
            class_arm=class_arm
        ).values_list('subject_id', flat=True)
        
        # Get subjects already assigned to ANY teacher in this class
        assigned_subject_ids = SubjectTeacherAssignment.objects.filter(
            class_arm_id=class_arm_id,
            session=current_session,
            term=current_term
        ).values_list('subject_id', flat=True)
        
        # If editing, exclude the current assignment's subject from the exclusion list
        if assignment_id:
            try:
                current_assignment = SubjectTeacherAssignment.objects.get(pk=assignment_id)
                assigned_subject_ids = [sid for sid in assigned_subject_ids if sid != current_assignment.subject_id]
            except SubjectTeacherAssignment.DoesNotExist:
                pass
        
        # Get subjects that are:
        # 1. Available for this class arm
        # 2. Not already assigned to any teacher
        # 3. Active
        available_subjects = Subject.objects.filter(
            id__in=available_subjects_for_arm,
            is_active=True
        ).exclude(
            id__in=assigned_subject_ids
        ).values('id', 'name', 'code').order_by('name')
        
        return JsonResponse({
            'success': True,
            'subjects': list(available_subjects)
        })
    except ClassArm.DoesNotExist:
        return JsonResponse({'error': 'Invalid class arm'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
