from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from accounts.decorators import admin_staff_required
from .models import AcademicSession, Term, ClassLevel, ClassArm, Subject, ClassArmSubject, SubjectTeacherAssignment
from django.db.models import Q
from django.core.paginator import Paginator
from .forms import (
    AcademicSessionForm, TermForm, ClassLevelForm,
    ClassArmForm, SubjectForm, SubjectTeacherAssignmentForm,
    SubjectSearchForm
)


# ── ACADEMIC SESSIONS ─────────────────────────────────────────

@login_required
@admin_staff_required
def session_list(request):
    query = request.GET.get('q', '')
    sessions_list = AcademicSession.objects.all().order_by('-start_date')
    
    if query:
        sessions_list = sessions_list.filter(Q(name__icontains=query))
    
    paginator = Paginator(sessions_list, 10)  # Show 10 sessions per page
    page = request.GET.get('page')
    sessions = paginator.get_page(page)
    
    return render(request, 'academics/session_list.html', {
        'sessions': sessions,
        'query': query,
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

from django.core.paginator import Paginator

@login_required
@admin_staff_required
def term_list(request):
    current_session = AcademicSession.get_current()
    selected_session_id = request.GET.get('session')
    terms_list = Term.objects.select_related('session').all().order_by('-session__start_date', 'name')

    if selected_session_id:
        terms_list = terms_list.filter(session_id=selected_session_id)
    elif selected_session_id is None and current_session:
        # Default to current session ONLY on first load (when 'session' param is missing)
        terms_list = terms_list.filter(session=current_session)
        selected_session_id = str(current_session.id)
        
    available_sessions = AcademicSession.objects.all().order_by('-start_date')
    
    paginator = Paginator(terms_list, 10)  # Show 10 terms per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'academics/term_list.html', {
        'page_obj': page_obj,
        'terms': page_obj,  # Keep 'terms' for easy backward compatibility if needed, but we'll use page_obj
        'current_session': current_session,
        'available_sessions': available_sessions,
        'selected_session': selected_session_id,
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
@transaction.atomic
def term_set_current(request, pk):
    term = get_object_or_404(Term, pk=pk)
    
    # 1. Update Global Term Status
    Term.objects.update(is_current=False)
    term.is_current = True
    term.save()
    
    # 2. Professional Sync: Update all active enrollments in this session to the new term
    from students.models import StudentEnrollment
    updated_count = StudentEnrollment.objects.filter(
        session=term.session,
        is_active=True
    ).update(term=term)
    
    messages.success(
        request, 
        f'{term} is now the current term. '
        f'Successfully synchronized {updated_count} student enrollments.'
    )
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
    from collections import defaultdict
    current_session = AcademicSession.get_current()
    sessions = AcademicSession.objects.all().order_by('-start_date')

    selected_session_id = request.GET.get('session')
    if selected_session_id:
        view_session = get_object_or_404(AcademicSession, id=selected_session_id)
    else:
        view_session = current_session

    class_arms = ClassArm.objects.filter(
        session=view_session
    ).select_related(
        'level', 'class_teacher', 'session'
    ).order_by('level__order', 'name') if view_session else ClassArm.objects.none()

    # Group by teacher (mirrors assignment_list grouping)
    grouped = defaultdict(list)
    for arm in class_arms:
        grouped[arm.class_teacher].append(arm)

    # Sort teachers: Assigned first (alphabetical), then Unassigned
    sorted_teachers = sorted(
        [t for t in grouped.keys() if t is not None],
        key=lambda x: x.get_full_name()
    )

    teacher_groups = []
    for teacher in sorted_teachers:
        teacher_groups.append({
            'teacher': teacher,
            'arms': grouped[teacher],
            'count': len(grouped[teacher])
        })
    
    if None in grouped:
        teacher_groups.append({
            'teacher': None,
            'arms': grouped[None],
            'count': len(grouped[None])
        })

    return render(request, 'academics/class_arm_list.html', {
        'teacher_groups': teacher_groups,
        'class_arms': class_arms,
        'current_session': current_session,
        'view_session': view_session,
        'sessions': sessions,
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
    
    # Base queryset for offerings
    offerings = ClassArmSubject.objects.select_related(
        'subject', 'class_level'
    ).order_by('class_level__order', 'arm_name', 'subject__name')
    
    if form.is_valid():
        query = form.cleaned_data.get('query')
        class_level_filter = form.cleaned_data.get('class_level')
        status = form.cleaned_data.get('status')
        
        if query:
            offerings = offerings.filter(
                Q(subject__name__icontains=query) |
                Q(subject__code__icontains=query)
            )
            
        if class_level_filter:
            offerings = offerings.filter(class_level=class_level_filter)
            
        if status:
            if status == 'active':
                offerings = offerings.filter(subject__is_active=True)
            elif status == 'inactive':
                offerings = offerings.filter(subject__is_active=False)
                
    # Group offerings by (class_level, arm_name)
    from collections import defaultdict
    class_groups = defaultdict(list)
    for off in offerings:
        key = (off.class_level, off.arm_name)
        class_groups[key].append(off)
        
    # Convert to list of dicts for template
    class_list = []
    for (level, arm), items in class_groups.items():
        class_list.append({
            'level': level,
            'arm': arm,
            'subjects': items,
            'count': len(items)
        })
        
    class_levels = ClassLevel.objects.all().order_by('order')
    
    return render(request, 'academics/subject_list.html', {
        'class_list': class_list,
        'form': form,
        'class_levels': class_levels,
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
    query = request.GET.get('q', '').strip()
    
    assignments = SubjectTeacherAssignment.objects.select_related(
        'teacher', 'subject', 'class_level'
    ).order_by('teacher__first_name', 'teacher__last_name', 'class_level__order', 'subject__name')

    if query:
        assignments = assignments.filter(
            Q(teacher__first_name__icontains=query) |
            Q(teacher__last_name__icontains=query) |
            Q(subject__name__icontains=query) |
            Q(class_level__name__icontains=query) |
            Q(arm_name__icontains=query)
        ).distinct()

    # Group assignments by teacher for a neater display
    from collections import defaultdict
    grouped_assignments = defaultdict(list)
    for assignment in assignments:
        grouped_assignments[assignment.teacher].append(assignment)

    # Convert to list of dicts for easier template iteration
    teacher_list = []
    for teacher, teacher_assigns in grouped_assignments.items():
        teacher_list.append({
            'teacher': teacher,
            'assignments': teacher_assigns,
            'count': len(teacher_assigns)
        })

    # Paginate the grouped teacher list
    paginator = Paginator(teacher_list, 15)  # 15 teachers per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'academics/assignment_list.html', {
        'page_obj': page_obj,
        'query': query,
        'page_title': 'Subject-Teacher Assignments'
    })

# ---------------- Assignment Views ----------------
@login_required
@admin_staff_required
def assignment_create(request):
    form = SubjectTeacherAssignmentForm(request.POST or None)
    if form.is_valid():
        teacher = form.cleaned_data['teacher']
        selected_offerings = form.cleaned_data['subject_assignments']
        
        created_count = 0
        skipped_count = 0
        
        for offering in selected_offerings:
            # Check if this assignment already exists for this Level/Arm/Subject
            existing = SubjectTeacherAssignment.objects.filter(
                class_level=offering.class_level,
                arm_name=offering.arm_name,
                subject=offering.subject
            ).first()
            
            if existing:
                if existing.teacher != teacher:
                    # Existing assignment to another teacher - we skip for safety
                    skipped_count += 1
                    continue
                else:
                    # Already assigned to this teacher anyway
                    continue
            
            # Create the assignment
            SubjectTeacherAssignment.objects.create(
                teacher=teacher,
                class_level=offering.class_level,
                arm_name=offering.arm_name,
                subject=offering.subject
            )
            created_count += 1
        
        if created_count > 0:
            messages.success(request, f'Successfully assigned {created_count} subjects to {teacher.get_full_name() or teacher.username}.')
        
        if skipped_count > 0:
            messages.warning(request, f'{skipped_count} assignments were skipped because those subjects are already assigned to other teachers in those classes.')
            
        if created_count == 0 and skipped_count == 0:
            messages.info(request, 'No new assignments were created.')
            
        return redirect('academics:assignment_list')
        
    return render(request, 'academics/assignment_form.html', {
        'form': form,
        'page_title': 'Assign Subject Teacher',
        'back_url': 'academics:assignment_list',
    })


@login_required
@admin_staff_required
def assignment_edit(request, pk):
    assignment = get_object_or_404(SubjectTeacherAssignment, pk=pk)
    form = SubjectTeacherAssignmentForm(request.POST or None, instance=assignment)
    if form.is_valid():
        teacher = form.cleaned_data['teacher']
        selected_offerings = form.cleaned_data['subject_assignments']
        
        if selected_offerings:
            # We take the first one for the edit
            offering = selected_offerings[0]
            assignment.teacher = teacher
            assignment.subject = offering.subject
            assignment.class_level = offering.class_level
            assignment.arm_name = offering.arm_name
            assignment.save()
            messages.success(request, 'Assignment updated successfully.')
        else:
            messages.warning(request, 'Please select at least one offering.')
            
        return redirect('academics:assignment_list')
    return render(request, 'academics/assignment_form.html', {
        'form': form,
        'page_title': 'Edit Subject Teacher Assignment',
        'back_url': 'academics:assignment_list',
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
    """API endpoint to fetch subjects available for assignment in a class arm (Level + Arm)"""
    class_arm_id = request.GET.get('class_arm')
    assignment_id = request.GET.get('assignment_id')  # For editing
    
    if not class_arm_id:
        return JsonResponse({'error': 'Missing class_arm parameter'}, status=400)
    
    try:
        # Get the class arm to extract Level and Arm
        class_arm = ClassArm.objects.get(pk=class_arm_id)
        class_level = class_arm.level
        arm_name = class_arm.name
        
        # Get subjects available for this class Level+Arm (via ClassArmSubject relationship)
        available_subjects_for_arm = ClassArmSubject.objects.filter(
            class_level=class_level,
            arm_name=arm_name
        ).values_list('subject_id', flat=True)
        
        # Get subjects already assigned to ANY teacher in this class Level+Arm
        assigned_subject_ids = SubjectTeacherAssignment.objects.filter(
            class_level=class_level,
            arm_name=arm_name
        ).values_list('subject_id', flat=True)
        
        # If editing, exclude the current assignment's subject from the exclusion list
        if assignment_id:
            try:
                current_assignment = SubjectTeacherAssignment.objects.get(pk=assignment_id)
                assigned_subject_ids = [sid for sid in assigned_subject_ids if sid != current_assignment.subject_id]
            except SubjectTeacherAssignment.DoesNotExist:
                pass
        
        # Get subjects that are active and available
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


@login_required
@admin_staff_required
def duplicate_classes(request):
    """View to clone classes from one session to another."""
    sessions = AcademicSession.objects.all().order_by('-start_date')
    current_session = AcademicSession.get_current()

    if request.method == 'POST':
        from_session_id = request.POST.get('from_session')
        to_session_id = request.POST.get('to_session')
        copy_teachers = request.POST.get('copy_teachers') == 'on'

        if from_session_id == to_session_id:
            messages.error(request, 'Source and target sessions must be different.')
            return redirect('academics:duplicate_classes')

        from_session = get_object_or_404(AcademicSession, id=from_session_id)
        to_session = get_object_or_404(AcademicSession, id=to_session_id)

        source_classes = ClassArm.objects.filter(session=from_session)
        created_count = 0
        skipped_count = 0

        for source_class in source_classes:
            # Check if class already exists in target session
            exists = ClassArm.objects.filter(
                level=source_class.level,
                name=source_class.name,
                session=to_session
            ).exists()

            if not exists:
                ClassArm.objects.create(
                    level=source_class.level,
                    name=source_class.name,
                    session=to_session,
                    capacity=source_class.capacity,
                    class_teacher=source_class.class_teacher if copy_teachers else None
                )
                created_count += 1
            else:
                skipped_count += 1

        if created_count > 0:
            messages.success(request, f'Successfully created {created_count} classes in {to_session.name}.')
        if skipped_count > 0:
            messages.info(request, f'{skipped_count} classes were skipped because they already exist.')
            
        return redirect('academics:class_arm_list')

    return render(request, 'academics/duplicate_classes.html', {
        'sessions': sessions,
        'current_session': current_session,
        'page_title': 'Duplicate Classes'
    })


@login_required
@admin_staff_required
def ajax_get_subject_offerings(request):
    """Fetch ClassArmSubject offerings for a given class level, excluding already assigned ones"""
    level_id = request.GET.get('level_id')
    assignment_id = request.GET.get('assignment_id')
    
    if not level_id:
        return JsonResponse({'error': 'Missing level_id'}, status=400)
    
    # 1. Fetch all offerings for this level
    offerings = ClassArmSubject.objects.filter(
        class_level_id=level_id
    ).select_related('subject', 'class_level').order_by('arm_name', 'subject__name')
    
    # 2. Find which ones are already assigned
    assigned_qs = SubjectTeacherAssignment.objects.filter(class_level_id=level_id)
    if assignment_id:
        assigned_qs = assigned_qs.exclude(pk=assignment_id)
        
    assigned_combinations = set(
        assigned_qs.values_list('class_level_id', 'arm_name', 'subject_id')
    )
    
    # 3. Filter out the assigned ones
    results = []
    for o in offerings:
        comb = (o.class_level_id, o.arm_name, o.subject_id)
        if comb not in assigned_combinations:
            results.append({
                'id': o.pk,
                'label': f"{o.subject.name} ({o.class_level.name} {o.arm_name})"
            })
    
    return JsonResponse({
        'success': True,
        'offerings': results
    })


@login_required
@admin_staff_required
def ajax_get_arms_by_level(request):
    """Fetch unique arm names for a given class level in the current session"""
    level_id = request.GET.get('level_id')
    if not level_id:
        return JsonResponse({'error': 'Missing level_id'}, status=400)
    
    current_session = AcademicSession.get_current()
    if not current_session:
        return JsonResponse({'error': 'No current session active'}, status=400)
        
    # Get unique arm names for this level in current session
    arm_names = ClassArm.objects.filter(
        level_id=level_id,
        session=current_session
    ).values_list('name', flat=True).distinct().order_by('name')
    
    return JsonResponse({
        'success': True,
        'arms': list(arm_names)
    })
