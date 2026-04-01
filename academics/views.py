from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from accounts.decorators import admin_staff_required
from .models import AcademicSession, Term, ClassLevel, ClassArm, Subject
from .forms import (
    AcademicSessionForm, TermForm, ClassLevelForm,
    ClassArmForm, SubjectForm
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
    terms = Term.objects.filter(
        session=current_session
    ) if current_session else Term.objects.all()
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
        form.save()
        messages.success(request, 'Class updated successfully.')
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
    subjects = Subject.objects.all()
    return render(request, 'academics/subject_list.html', {
        'subjects': subjects,
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
        form.save()
        messages.success(request, 'Subject updated successfully.')
        return redirect('academics:subject_list')
    return render(request, 'academics/form.html', {
        'form': form,
        'page_title': f'Edit — {subject.name}',
        'back_url': 'academics:subject_list'
    })