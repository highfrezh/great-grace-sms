from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction, IntegrityError
from accounts.decorators import (
    admin_staff_required, teaching_staff_required, examiner_required,
    subject_teacher_required
)
from academics.models import AcademicSession, Term, SubjectTeacherAssignment, Subject, ClassArm
from students.models import Student, StudentEnrollment
from staff.models import StaffProfile
from .models import (
    Exam, ObjectiveQuestion, TheoryQuestion, ExamSubmission,
    StudentAnswer, TheoryScore, ExamResult, ExamDeadlinePenalty,
    ExamConfiguration
)
from .forms import (
    ExamForm, TeacherExamForm, QuestionForm, TheoryQuestionForm,
    VettingForm, CAScoreForm, ExamConfigurationForm
)
import random


# ── DECORATORS ─────────────────────────────────────────────

def principal_or_vice_principal_required(view_func):
    """Check if user is Principal or Vice Principal"""
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_principal or request.user.is_vice_principal):
            messages.error(request, 'Only principals can access this page.')
            return redirect('accounts:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


# ── EXAM CONFIGURATION (Principal/Vice Principal) ────────────

@login_required
@principal_or_vice_principal_required
def exam_configuration_list(request):
    """List all exam configurations"""
    configs = ExamConfiguration.objects.select_related(
        'session', 'term', 'configured_by'
    ).order_by('-configured_at')
    
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    current_config = None
    
    if current_session and current_term:
        current_config = ExamConfiguration.objects.filter(
            session=current_session,
            term=current_term
        ).first()
    
    return render(request, 'examinations/exam_config_list.html', {
        'configs': configs,
        'current_config': current_config,
        'current_session': current_session,
        'current_term': current_term,
        'page_title': 'Exam Configuration'
    })


@login_required
@principal_or_vice_principal_required
def exam_configuration_create(request):
    """Create new exam configuration"""
    if request.method == 'POST':
        form = ExamConfigurationForm(request.POST)
        if form.is_valid():
            config = form.save(commit=False)
            config.configured_by = request.user
            config.save()
            messages.success(
                request,
                f'Exam configuration for {config.session} - {config.term} created successfully.'
            )
            return redirect('examinations:exam_config_list')
    else:
        form = ExamConfigurationForm()
    
    return render(request, 'examinations/exam_config_form.html', {
        'form': form,
        'page_title': 'Create Exam Configuration',
    })


@login_required
@principal_or_vice_principal_required
def exam_configuration_edit(request, pk):
    """Edit exam configuration"""
    config = get_object_or_404(ExamConfiguration, pk=pk)
    
    if request.method == 'POST':
        form = ExamConfigurationForm(request.POST, instance=config)
        if form.is_valid():
            updated_config = form.save(commit=False)
            updated_config.configured_by = request.user
            updated_config.save()
            messages.success(
                request,
                f'Exam configuration updated successfully.'
            )
            return redirect('examinations:exam_config_list')
    else:
        form = ExamConfigurationForm(instance=config)
    
    return render(request, 'examinations/exam_config_form.html', {
        'form': form,
        'config': config,
        'page_title': f'Edit Configuration — {config.session}',
    })


@login_required
@principal_or_vice_principal_required
def exam_configuration_detail(request, pk):
    """View exam configuration details"""
    config = get_object_or_404(ExamConfiguration, pk=pk)
    
    return render(request, 'examinations/exam_config_detail.html', {
        'config': config,
        'page_title': f'Configuration Details — {config.session}'
    })


# ── EXAM MANAGEMENT ───────────────────────────────────────────

@login_required
@teaching_staff_required
def exam_list(request):
    user = request.user
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()

    if user.is_admin_staff or user.is_superuser:
        exams = Exam.objects.filter(
            session=current_session,
            term=current_term
        ).select_related(
            'subject', 'class_arm', 'created_by'
        )
    elif user.is_examiner and not user.is_subject_teacher:
        # Examiner sees exams pending vetting
        exams = Exam.objects.filter(
            session=current_session,
            term=current_term,
            status__in=[
                Exam.Status.PENDING_VETTING,
                Exam.Status.VETTED
            ]
        ).select_related('subject', 'class_arm', 'created_by')
    else:
        # Subject teacher sees their own exams
        exams = Exam.objects.filter(
            session=current_session,
            term=current_term,
            created_by=user
        ).select_related('subject', 'class_arm')

    # Status filter
    status_filter = request.GET.get('status', '')
    if status_filter:
        exams = exams.filter(status=status_filter)

    return render(request, 'examinations/exam_list.html', {
        'exams': exams,
        'current_session': current_session,
        'current_term': current_term,
        'status_filter': status_filter,
        'status_choices': Exam.Status.choices,
        'page_title': 'Examinations'
    })


@login_required
@teaching_staff_required
def exam_create(request):
    form = ExamForm(
        request.POST or None,
        user=request.user
    )
    if form.is_valid():
        exam = form.save(commit=False)
        exam.created_by = request.user
        exam.save()
        messages.success(
            request,
            f'Exam "{exam.title}" created. Now add your questions.'
        )
        return redirect('examinations:question_list', exam_pk=exam.pk)
    return render(request, 'examinations/exam_form.html', {
        'form': form,
        'page_title': 'Create Exam',
        'back_url': 'examinations:exam_list'
    })


@login_required
@teaching_staff_required
def exam_detail(request, pk):
    exam = get_object_or_404(
        Exam.objects.select_related(
            'subject', 'class_arm', 'session', 'term',
            'created_by', 'vetted_by', 'approved_by'
        ).prefetch_related('questions', 'theory_questions'),
        pk=pk
    )
    submissions = ExamSubmission.objects.filter(
        exam=exam
    ).select_related('student').order_by('-started_at')

    return render(request, 'examinations/exam_detail.html', {
        'exam': exam,
        'submissions': submissions,
        'page_title': exam.title
    })


@login_required
@teaching_staff_required
def exam_edit(request, pk):
    exam = get_object_or_404(Exam, pk=pk)

    if exam.status not in [Exam.Status.DRAFT, Exam.Status.PENDING_VETTING]:
        messages.error(
            request,
            'Cannot edit an exam that has been vetted or approved.'
        )
        return redirect('examinations:exam_detail', pk=pk)

    form = ExamForm(
        request.POST or None,
        instance=exam,
        user=request.user
    )
    if form.is_valid():
        form.save()
        messages.success(request, 'Exam updated successfully.')
        return redirect('examinations:exam_detail', pk=pk)
    return render(request, 'examinations/exam_form.html', {
        'form': form,
        'exam': exam,
        'page_title': f'Edit — {exam.title}',
        'back_url': 'examinations:exam_list'
    })


@login_required
@teaching_staff_required
def exam_delete(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    if request.method == 'POST':
        if exam.status in [Exam.Status.ACTIVE, Exam.Status.CLOSED]:
            messages.error(
                request,
                'Cannot delete an active or closed exam.'
            )
            return redirect('examinations:exam_detail', pk=pk)
        exam.delete()
        messages.success(request, 'Exam deleted successfully.')
    return redirect('examinations:exam_list')


@login_required
@teaching_staff_required
def exam_submit_vetting(request, pk):
    exam = get_object_or_404(Exam, pk=pk, created_by=request.user)
    if request.method == 'POST':
        if exam.question_count == 0:
            messages.error(
                request,
                'Cannot submit for vetting — no CBT questions added yet.'
            )
            return redirect('examinations:exam_detail', pk=pk)
        exam.status = Exam.Status.PENDING_VETTING
        exam.save()

        # Check deadline penalty
        if exam.submission_deadline:
            if timezone.now() > exam.submission_deadline:
                ExamDeadlinePenalty.objects.get_or_create(
                    exam=exam,
                    teacher=request.user,
                    defaults={
                        'deadline': exam.submission_deadline,
                        'note': 'Submitted after deadline'
                    }
                )
                exam.deadline_penalty_logged = True
                exam.save()
                messages.warning(
                    request,
                    'Exam submitted for vetting but deadline was missed. '
                    'A penalty has been logged.'
                )
            else:
                messages.success(
                    request, 'Exam submitted for vetting.'
                )
        else:
            messages.success(request, 'Exam submitted for vetting.')
    return redirect('examinations:exam_detail', pk=pk)


@login_required
@examiner_required
def exam_vet(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    if not exam.can_be_vetted:
        messages.error(request, 'This exam cannot be vetted at this stage.')
        return redirect('examinations:exam_detail', pk=pk)

    form = VettingForm(request.POST or None)
    if form.is_valid():
        action = form.cleaned_data['action']
        comment = form.cleaned_data.get('comment', '')

        exam.vetted_by = request.user
        exam.vetted_at = timezone.now()
        exam.vetting_comment = comment

        if action == 'approve':
            exam.status = Exam.Status.VETTED
            messages.success(
                request, 'Exam vetted and passed to admin for approval.'
            )
        else:
            exam.status = Exam.Status.DRAFT
            messages.warning(
                request,
                f'Exam rejected and returned to teacher. Reason: {comment}'
            )
        exam.save()
        return redirect('examinations:exam_detail', pk=pk)

    return render(request, 'examinations/exam_vet.html', {
        'exam': exam,
        'form': form,
        'page_title': f'Vet Exam — {exam.title}'
    })


@login_required
@admin_staff_required
def exam_approve(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    if not exam.can_be_approved:
        messages.error(
            request, 'This exam must be vetted before approval.'
        )
        return redirect('examinations:exam_detail', pk=pk)
    if request.method == 'POST':
        exam.status = Exam.Status.APPROVED
        exam.approved_by = request.user
        exam.approved_at = timezone.now()
        exam.save()
        messages.success(
            request,
            'Exam approved. You can now activate it for students.'
        )
    return redirect('examinations:exam_detail', pk=pk)


@login_required
@admin_staff_required
def exam_activate(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    if not exam.can_be_activated:
        messages.error(
            request, 'Exam must be approved before activation.'
        )
        return redirect('examinations:exam_detail', pk=pk)
    if request.method == 'POST':
        exam.status = Exam.Status.ACTIVE
        exam.save()
        messages.success(
            request,
            f'Exam "{exam.title}" is now LIVE for students.'
        )
    return redirect('examinations:exam_detail', pk=pk)


@login_required
@admin_staff_required
def exam_close(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    if request.method == 'POST':
        exam.status = Exam.Status.CLOSED
        exam.save()
        messages.success(request, 'Exam closed successfully.')
    return redirect('examinations:exam_detail', pk=pk)


@login_required
@teaching_staff_required
def exam_preview(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    questions = list(exam.questions.all())
    return render(request, 'examinations/exam_preview.html', {
        'exam': exam,
        'questions': questions,
        'page_title': f'Preview — {exam.title}'
    })


# ── CBT QUESTIONS ─────────────────────────────────────────────

@login_required
@teaching_staff_required
def question_list(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)
    questions = exam.questions.all()
    return render(request, 'examinations/question_list.html', {
        'exam': exam,
        'questions': questions,
        'page_title': f'CBT Questions — {exam.title}'
    })


@login_required
@teaching_staff_required
def question_create(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)
    form = QuestionForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        question = form.save(commit=False)
        question.exam = exam
        if not question.order:
            question.order = exam.question_count + 1
        question.save()
        messages.success(request, 'Question added successfully.')
        if 'add_another' in request.POST:
            return redirect('examinations:question_create', exam_pk=exam_pk)
        return redirect('examinations:question_list', exam_pk=exam_pk)
    return render(request, 'examinations/question_form.html', {
        'form': form,
        'exam': exam,
        'page_title': 'Add Question'
    })


@login_required
@teaching_staff_required
def question_edit(request, exam_pk, pk):
    exam = get_object_or_404(Exam, pk=exam_pk)
    question = get_object_or_404(Question, pk=pk, exam=exam)
    form = QuestionForm(
        request.POST or None,
        request.FILES or None,
        instance=question
    )
    if form.is_valid():
        form.save()
        messages.success(request, 'Question updated.')
        return redirect('examinations:question_list', exam_pk=exam_pk)
    return render(request, 'examinations/question_form.html', {
        'form': form,
        'exam': exam,
        'question': question,
        'page_title': 'Edit Question'
    })


@login_required
@teaching_staff_required
def question_delete(request, exam_pk, pk):
    exam = get_object_or_404(Exam, pk=exam_pk)
    question = get_object_or_404(Question, pk=pk, exam=exam)
    if request.method == 'POST':
        question.delete()
        messages.success(request, 'Question deleted.')
    return redirect('examinations:question_list', exam_pk=exam_pk)


# ── BULK QUESTION CREATION (Subject Teachers) ──────────────────

@login_required
@subject_teacher_required

# ── THEORY QUESTIONS ──────────────────────────────────────────

@login_required
@teaching_staff_required
def theory_question_list(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)
    questions = exam.theory_questions.all()
    return render(request, 'examinations/theory_question_list.html', {
        'exam': exam,
        'questions': questions,
        'page_title': f'Theory Questions — {exam.title}'
    })


@login_required
@teaching_staff_required
def theory_question_create(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)
    form = TheoryQuestionForm(request.POST or None)
    if form.is_valid():
        question = form.save(commit=False)
        question.exam = exam
        if not question.order:
            question.order = exam.theory_question_count + 1
        question.save()
        messages.success(request, 'Theory question added.')
        if 'add_another' in request.POST:
            return redirect(
                'examinations:theory_question_create', exam_pk=exam_pk
            )
        return redirect(
            'examinations:theory_question_list', exam_pk=exam_pk
        )
    return render(request, 'examinations/theory_question_form.html', {
        'form': form,
        'exam': exam,
        'page_title': 'Add Theory Question'
    })


@login_required
@teaching_staff_required
def theory_question_edit(request, exam_pk, pk):
    exam = get_object_or_404(Exam, pk=exam_pk)
    question = get_object_or_404(TheoryQuestion, pk=pk, exam=exam)
    form = TheoryQuestionForm(request.POST or None, instance=question)
    if form.is_valid():
        form.save()
        messages.success(request, 'Theory question updated.')
        return redirect(
            'examinations:theory_question_list', exam_pk=exam_pk
        )
    return render(request, 'examinations/theory_question_form.html', {
        'form': form,
        'exam': exam,
        'question': question,
        'page_title': 'Edit Theory Question'
    })


@login_required
@teaching_staff_required
def theory_question_delete(request, exam_pk, pk):
    exam = get_object_or_404(Exam, pk=exam_pk)
    question = get_object_or_404(TheoryQuestion, pk=pk, exam=exam)
    if request.method == 'POST':
        question.delete()
        messages.success(request, 'Theory question deleted.')
    return redirect(
        'examinations:theory_question_list', exam_pk=exam_pk
    )


# ── CBT EXAM TAKING ───────────────────────────────────────────

@login_required
def exam_take(request, pk):
    exam = get_object_or_404(Exam, pk=pk, status=Exam.Status.ACTIVE)

    # Get student profile
    try:
        student = request.user.student_profile
    except Exception:
        messages.error(request, 'Student profile not found.')
        return redirect('accounts:dashboard')

    # Check enrollment
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    enrolled = StudentEnrollment.objects.filter(
        student=student,
        class_arm=exam.class_arm,
        session=current_session,
        is_active=True
    ).exists()

    if not enrolled:
        messages.error(
            request, 'You are not enrolled in this class.'
        )
        return redirect('accounts:dashboard')

    # Get or create submission
    submission, created = ExamSubmission.objects.get_or_create(
        exam=exam,
        student=student,
        defaults={
            'status': ExamSubmission.SubmissionStatus.IN_PROGRESS,
            'time_remaining_seconds': exam.duration_minutes * 60
        }
    )

    # Already submitted
    if submission.is_complete:
        return redirect('examinations:exam_result_student', pk=pk)

    # Get questions
    questions = list(exam.questions.all())
    if exam.randomize_questions:
        # Use student id as seed for consistent order per student
        rng = random.Random(submission.id)
        rng.shuffle(questions)

    # Get existing answers
    existing_answers = {
        a.question_id: a.selected_option
        for a in submission.answers.all()
    }

    return render(request, 'examinations/exam_take.html', {
        'exam': exam,
        'submission': submission,
        'questions': questions,
        'existing_answers': existing_answers,
        'time_remaining': submission.time_remaining_seconds,
        'page_title': exam.title
    })


@login_required
@require_POST
def exam_autosave(request, pk):
    """Auto-save student answers every 30 seconds via AJAX"""
    exam = get_object_or_404(Exam, pk=pk)
    try:
        student = request.user.student_profile
    except Exception:
        return JsonResponse({'status': 'error'}, status=400)

    submission = get_object_or_404(
        ExamSubmission, exam=exam, student=student
    )

    if submission.is_complete:
        return JsonResponse({'status': 'already_submitted'})

    # Save answers
    for key, value in request.POST.items():
        if key.startswith('answer_'):
            question_id = int(key.replace('answer_', ''))
            StudentAnswer.objects.update_or_create(
                submission=submission,
                question_id=question_id,
                defaults={'selected_option': value}
            )

    # Save remaining time
    time_remaining = request.POST.get('time_remaining')
    if time_remaining:
        submission.time_remaining_seconds = int(time_remaining)
        submission.save()

    return JsonResponse({'status': 'saved'})


@login_required
@require_POST
@transaction.atomic
def exam_submit(request, pk):
    """Final submission of CBT exam"""
    exam = get_object_or_404(Exam, pk=pk)
    try:
        student = request.user.student_profile
    except Exception:
        messages.error(request, 'Student profile not found.')
        return redirect('accounts:dashboard')

    submission = get_object_or_404(
        ExamSubmission, exam=exam, student=student
    )

    if submission.is_complete:
        return redirect('examinations:exam_result_student', pk=pk)

    # Save all answers
    for key, value in request.POST.items():
        if key.startswith('answer_'):
            question_id = int(key.replace('answer_', ''))
            StudentAnswer.objects.update_or_create(
                submission=submission,
                question_id=question_id,
                defaults={'selected_option': value}
            )

    # Check malpractice flags
    auto_submit_reason = request.POST.get('auto_submit_reason', '')
    tab_switches = int(request.POST.get('tab_switches', 0))
    fullscreen_exits = int(request.POST.get('fullscreen_exits', 0))

    submission.tab_switch_count = tab_switches
    submission.fullscreen_exit_count = fullscreen_exits
    submission.auto_submitted_reason = auto_submit_reason

    # Calculate OBJ score
    answers = submission.answers.select_related('question')
    obj_score = sum(
        q.question.marks for q in answers if q.is_correct
    )
    submission.obj_score = obj_score

    # Mark as submitted
    if auto_submit_reason:
        submission.status = ExamSubmission.SubmissionStatus.AUTO_SUBMITTED
    else:
        submission.status = ExamSubmission.SubmissionStatus.SUBMITTED

    submission.submitted_at = timezone.now()
    submission.save()

    # Create or update ExamResult with OBJ score
    result, _ = ExamResult.objects.get_or_create(
        exam=exam,
        student=student,
        defaults={'submission': submission}
    )
    result.obj_score = obj_score
    result.submission = submission
    result.save()

    messages.success(
        request,
        f'Exam submitted! Your OBJ score: {obj_score}/{exam.obj_marks}'
    )
    return redirect('examinations:exam_result_student', pk=pk)


@login_required
def exam_result_student(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    try:
        student = request.user.student_profile
    except Exception:
        return redirect('accounts:dashboard')

    submission = get_object_or_404(
        ExamSubmission, exam=exam, student=student
    )
    answers = submission.answers.select_related(
        'question'
    ).order_by('question__order')

    result = ExamResult.objects.filter(
        exam=exam, student=student
    ).first()

    return render(request, 'examinations/exam_result_student.html', {
        'exam': exam,
        'submission': submission,
        'answers': answers,
        'result': result,
        'page_title': f'Result — {exam.title}'
    })


# ── THEORY & CA SCORE ENTRY ───────────────────────────────────

@login_required
@teaching_staff_required
def theory_score_entry(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    submissions = ExamSubmission.objects.filter(
        exam=exam,
        status__in=[
            ExamSubmission.SubmissionStatus.SUBMITTED,
            ExamSubmission.SubmissionStatus.AUTO_SUBMITTED
        ]
    ).select_related('student').order_by(
        'student__last_name', 'student__first_name'
    )
    theory_questions = exam.theory_questions.all()

    return render(request, 'examinations/theory_score_entry.html', {
        'exam': exam,
        'submissions': submissions,
        'theory_questions': theory_questions,
        'page_title': f'Theory Scores — {exam.title}'
    })


# ── SUBJECT TEACHER EXAM CREATION WORKFLOW ────────────────────

@login_required
@subject_teacher_required
def teacher_exam_list(request):
    """List exams created by current teacher"""
    try:
        staff_profile = StaffProfile.objects.get(user=request.user)
    except StaffProfile.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('accounts:dashboard')
    
    exams = Exam.objects.filter(
        teacher=staff_profile
    ).select_related(
        'subject', 'class_arm', 'session', 'term'
    ).order_by('-created_at')
    
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    
    # Count exams by status
    draft_count = exams.filter(status=Exam.ExamStatus.DRAFT).count()
    awaiting_approval_count = exams.filter(status=Exam.ExamStatus.AWAITING_APPROVAL).count()
    approved_count = exams.filter(status=Exam.ExamStatus.APPROVED).count()
    
    # Count total questions across all exams
    total_questions = ObjectiveQuestion.objects.filter(exam__in=exams).count()
    
    # Add completion percentage to each exam
    exams_with_completion = []
    for exam in exams:
        has_objectives = exam.objectives.exists()
        has_theory = bool(exam.theory_attachment)
        
        if has_objectives and has_theory:
            completion = 100
        elif has_objectives or has_theory:
            completion = 50
        else:
            completion = 0
        
        # Store completion as an attribute on the exam object
        exam.completion_percentage = completion
        exams_with_completion.append(exam)
    
    return render(request, 'examinations/teacher_exam_list.html', {
        'exams': exams_with_completion,
        'page_title': 'My Exams',
        'current_session': current_session,
        'current_term': current_term,
        'draft_count': draft_count,
        'awaiting_approval_count': awaiting_approval_count,
        'approved_count': approved_count,
        'total_questions': total_questions,
    })


@login_required
@subject_teacher_required
def teacher_exam_create(request):
    """Create exam for assigned subject/class"""
    try:
        staff_profile = StaffProfile.objects.get(user=request.user)
    except StaffProfile.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('accounts:dashboard')
    
    # Get teacher's assigned subjects/classes
    assignments = SubjectTeacherAssignment.objects.filter(
        teacher=request.user
    ).select_related('subject', 'class_arm').distinct('subject', 'class_arm')
    
    form = TeacherExamForm(request.POST or None, teacher=request.user)
    
    if form.is_valid():
        try:
            exam = form.save(commit=False)
            exam.teacher = staff_profile
            exam.save()
            messages.success(request, f'Exam "{exam.title}" created successfully.')
            return redirect('examinations:teacher_exam_detail', pk=exam.pk)
        except IntegrityError:
            messages.error(
                request, 
                'An exam already exists for this subject, class, session, and term. '
                'You can only create one exam per subject-class-session-term combination.'
            )
            form = TeacherExamForm(request.POST)
    
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    
    return render(request, 'examinations/teacher_exam_create.html', {
        'form': form,
        'assignments': assignments,
        'page_title': 'Create New Exam',
        'current_session': current_session,
        'current_term': current_term,
    })


@login_required
@subject_teacher_required
def get_available_subjects(request):
    """API endpoint to get subjects available for a class (excluding already created exams)"""
    class_arm_id = request.GET.get('class_id')
    
    if not class_arm_id:
        return JsonResponse({'subjects': []})
    
    try:
        staff_profile = StaffProfile.objects.get(user=request.user)
    except StaffProfile.DoesNotExist:
        return JsonResponse({'subjects': []})
    
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    
    # Get teacher's assigned subjects for this class
    from academics.models import SubjectTeacherAssignment
    assignments = SubjectTeacherAssignment.objects.filter(
        teacher=request.user,
        class_arm_id=class_arm_id
    ).select_related('subject')
    
    assigned_subject_ids = assignments.values_list('subject_id', flat=True).distinct()
    
    # Get subjects that don't have exams for this class in current session/term
    existing_exams = Exam.objects.filter(
        class_arm_id=class_arm_id,
        session=current_session,
        term=current_term
    ).values_list('subject_id', flat=True).distinct()
    
    # Filter subjects: assigned to teacher AND no exam exists for this class yet
    available_subjects = Subject.objects.filter(
        id__in=assigned_subject_ids
    ).exclude(
        id__in=existing_exams
    ).values('id', 'name')
    
    return JsonResponse({
        'subjects': list(available_subjects)
    })


@login_required
@subject_teacher_required
def teacher_exam_detail(request, pk):
    """Display exam details with questions count and theory file status"""
    try:
        staff_profile = StaffProfile.objects.get(user=request.user)
    except StaffProfile.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('accounts:dashboard')
    
    exam = get_object_or_404(
        Exam.objects.select_related('class_arm', 'class_arm__level', 'subject', 'session', 'term'),
        pk=pk, teacher=staff_profile
    )
    objective_questions = exam.objectives.all()
    
    return render(request, 'examinations/teacher_exam_detail.html', {
        'exam': exam,
        'objective_questions': objective_questions,
        'objective_count': objective_questions.count(),
        'has_theory_file': bool(exam.theory_attachment),
        'page_title': f'Exam: {exam.title}'
    })


@login_required
@subject_teacher_required
def teacher_exam_edit(request, pk):
    """Edit exam details and upload theory file"""
    try:
        staff_profile = StaffProfile.objects.get(user=request.user)
    except StaffProfile.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('accounts:dashboard')
    
    exam = get_object_or_404(Exam, pk=pk, teacher=staff_profile)
    
    # Check if exam can be edited (must be in DRAFT status)
    if exam.status != Exam.ExamStatus.DRAFT:
        messages.error(
            request,
            f'Cannot edit exam. It is currently in "{exam.get_status_display()}" status. '
            'You can only edit exams in draft status.'
        )
        return redirect('examinations:teacher_exam_detail', pk=exam.pk)
    
    form = TeacherExamForm(request.POST or None, request.FILES or None, instance=exam)
    
    if form.is_valid():
        form.save()
        messages.success(request, 'Exam updated successfully.')
        return redirect('examinations:teacher_exam_detail', pk=exam.pk)
    
    return render(request, 'examinations/teacher_exam_edit.html', {
        'form': form,
        'exam': exam,
        'page_title': f'Edit Exam: {exam.title}'
    })


@login_required
@subject_teacher_required
@require_POST
def teacher_exam_publish(request, pk):
    """Publish exam created by current teacher for examiner review"""
    try:
        staff_profile = StaffProfile.objects.get(user=request.user)
    except StaffProfile.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('accounts:dashboard')
    
    exam = get_object_or_404(Exam, pk=pk, teacher=staff_profile)
    
    # Check if exam is already published/awaiting approval/approved
    if exam.status != Exam.ExamStatus.DRAFT:
        messages.warning(request, f'Exam is already in {exam.get_status_display()} status.')
        return redirect('examinations:teacher_exam_detail', pk=exam.pk)
    
    # Check prerequisites
    if exam.objectives.count() == 0:
        messages.error(request, 'Cannot publish exam without objective questions.')
        return redirect('examinations:teacher_exam_detail', pk=exam.pk)
    
    if not exam.theory_attachment:
        messages.error(request, 'Cannot publish exam without theory file.')
        return redirect('examinations:teacher_exam_detail', pk=exam.pk)
    
    # Publish the exam - change status to AWAITING_APPROVAL
    exam.publish()
    messages.success(request, f'Exam "{exam.title}" has been published for examiner approval!')
    return redirect('examinations:teacher_exam_detail', pk=exam.pk)


@login_required
@subject_teacher_required
@require_POST
def teacher_exam_delete(request, pk):
    """Delete exam created by current teacher"""
    try:
        staff_profile = StaffProfile.objects.get(user=request.user)
    except StaffProfile.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('accounts:dashboard')
    
    exam = get_object_or_404(Exam, pk=pk, teacher=staff_profile)
    
    # Only allow deletion if exam is in DRAFT status
    if exam.status != Exam.ExamStatus.DRAFT:
        messages.error(request, 'Cannot delete an exam that has been published. Contact the examiner to reject it first.')
        return redirect('examinations:teacher_exam_detail', pk=exam.pk)
    
    exam_title = exam.title
    exam.delete()
    messages.success(request, f'Exam "{exam_title}" has been deleted successfully.')
    return redirect('examinations:teacher_exam_list')


@login_required
@subject_teacher_required
def teacher_add_questions(request, exam_pk):
    """Add multiple objective questions to exam"""
    try:
        staff_profile = StaffProfile.objects.get(user=request.user)
    except StaffProfile.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('accounts:dashboard')
    
    exam = get_object_or_404(Exam, pk=exam_pk, teacher=staff_profile)
    
    if request.method == 'POST':
        questions_added = 0
        errors = []
        
        # Dynamic form field parsing for question_{index}_field_name
        question_indices = set()
        for key in request.POST.keys():
            if key.startswith('question_') and '_text' in key:
                idx = key.split('_')[1]
                question_indices.add(int(idx))
        
        for idx in sorted(question_indices):
            question_text = request.POST.get(f'question_{idx}_text', '').strip()
            option_a = request.POST.get(f'question_{idx}_option_a', '').strip()
            option_b = request.POST.get(f'question_{idx}_option_b', '').strip()
            option_c = request.POST.get(f'question_{idx}_option_c', '').strip()
            option_d = request.POST.get(f'question_{idx}_option_d', '').strip()
            correct_option = request.POST.get(f'question_{idx}_correct_option', '').strip()
            
            # Validate required fields
            if not all([question_text, option_a, option_b, option_c, option_d, correct_option]):
                errors.append(f'Question {idx + 1}: All fields are required.')
                continue
            
            if correct_option not in ['A', 'B', 'C', 'D']:
                errors.append(f'Question {idx + 1}: Invalid correct option.')
                continue
            
            try:
                # Handle question image
                question_image = None
                image_key = f'question_{idx}_image'
                if image_key in request.FILES:
                    question_image = request.FILES[image_key]
                
                question = ObjectiveQuestion.objects.create(
                    exam=exam,
                    question_text=question_text,
                    question_image=question_image,
                    option_a=option_a,
                    option_b=option_b,
                    option_c=option_c,
                    option_d=option_d,
                    correct_option=correct_option
                )
                questions_added += 1
            except Exception as e:
                errors.append(f'Question {idx + 1}: Error creating question - {str(e)}')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        
        if questions_added > 0:
            messages.success(request, f'{questions_added} question(s) added successfully.')
            return redirect('examinations:teacher_exam_detail', pk=exam.pk)
    
    # GET request - show form
    return render(request, 'examinations/teacher_add_questions.html', {
        'exam': exam,
        'page_title': f'Add Questions to {exam.title}',
        'num_questions': 5  # Default number of question forms to display
    })


@login_required
@teaching_staff_required
def teacher_question_edit(request, exam_pk, pk):
    """Allow teachers to edit their own objective questions"""
    try:
        staff_profile = StaffProfile.objects.get(user=request.user)
    except StaffProfile.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('accounts:dashboard')
    
    # Verify the exam belongs to the teacher
    exam = get_object_or_404(Exam, pk=exam_pk, teacher=staff_profile)
    question = get_object_or_404(ObjectiveQuestion, pk=pk, exam=exam)
    
    if request.method == 'POST':
        question_text = request.POST.get('question_text', '').strip()
        option_a = request.POST.get('option_a', '').strip()
        option_b = request.POST.get('option_b', '').strip()
        option_c = request.POST.get('option_c', '').strip()
        option_d = request.POST.get('option_d', '').strip()
        correct_option = request.POST.get('correct_option', '').strip()
        
        # Validate
        if not all([question_text, option_a, option_b, option_c, option_d, correct_option]):
            messages.error(request, 'All fields are required.')
        elif correct_option not in ['A', 'B', 'C', 'D']:
            messages.error(request, 'Invalid correct option.')
        else:
            try:
                question.question_text = question_text
                question.option_a = option_a
                question.option_b = option_b
                question.option_c = option_c
                question.option_d = option_d
                question.correct_option = correct_option
                
                # Handle image upload/replacement
                if 'question_image' in request.FILES:
                    # Delete old image if it exists
                    if question.question_image:
                        question.question_image.delete(save=False)
                    question.question_image = request.FILES['question_image']
                elif request.POST.get('remove_image') == 'on':
                    if question.question_image:
                        question.question_image.delete(save=False)
                    question.question_image = None
                
                question.save()
                messages.success(request, 'Question updated successfully.')
                return redirect('examinations:teacher_exam_detail', pk=exam.pk)
            except Exception as e:
                messages.error(request, f'Error updating question: {str(e)}')
    
    return render(request, 'examinations/teacher_question_form.html', {
        'exam': exam,
        'question': question,
        'page_title': f'Edit Question - {exam.title}'
    })


@login_required
@teaching_staff_required
@require_POST
def teacher_question_delete(request, exam_pk, pk):
    """Allow teachers to delete their own objective questions"""
    try:
        staff_profile = StaffProfile.objects.get(user=request.user)
    except StaffProfile.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('accounts:dashboard')
    
    # Verify the exam belongs to the teacher
    exam = get_object_or_404(Exam, pk=exam_pk, teacher=staff_profile)
    question = get_object_or_404(ObjectiveQuestion, pk=pk, exam=exam)
    
    try:
        question.delete()
        messages.success(request, 'Question deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting question: {str(e)}')
    
    return redirect('examinations:teacher_exam_detail', pk=exam.pk)


@teaching_staff_required
@require_POST
@transaction.atomic
def theory_score_bulk(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    theory_questions = exam.theory_questions.all()
    submissions = ExamSubmission.objects.filter(exam=exam)

    for submission in submissions:
        total_theory = 0
        for tq in theory_questions:
            score_key = f'score_{submission.id}_{tq.id}'
            score_val = request.POST.get(score_key, 0)
            try:
                score = float(score_val)
                score = min(score, tq.max_marks)
            except (ValueError, TypeError):
                score = 0

            TheoryScore.objects.update_or_create(
                submission=submission,
                theory_question=tq,
                defaults={
                    'score': score,
                    'marked_by': request.user
                }
            )
            total_theory += score

        # Update result
        result, _ = ExamResult.objects.get_or_create(
            exam=exam,
            student=submission.student,
            defaults={'submission': submission}
        )
        result.theory_score = total_theory
        result.obj_score = submission.obj_score or 0
        result.save()

    messages.success(request, 'Theory scores saved successfully.')
    return redirect('examinations:theory_score_entry', pk=pk)


@login_required
@teaching_staff_required
def ca_score_entry(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()

    students = Student.objects.filter(
        is_active=True,
        enrollments__class_arm=exam.class_arm,
        enrollments__session=current_session,
        enrollments__is_active=True
    ).order_by('last_name', 'first_name').distinct()

    form = CAScoreForm(
        request.POST or None,
        students=students,
        exam=exam
    )

    if request.method == 'POST' and form.is_valid():
        for student in students:
            ca1 = form.cleaned_data.get(f'ca1_{student.id}') or 0
            ca2 = form.cleaned_data.get(f'ca2_{student.id}') or 0

            result, _ = ExamResult.objects.get_or_create(
                exam=exam,
                student=student
            )
            result.ca1_score = ca1
            result.ca2_score = ca2
            result.last_modified_by = request.user
            result.save()

        messages.success(request, 'CA scores saved successfully.')
        return redirect('examinations:ca_score_entry', pk=pk)

    # Get existing CA scores
    existing_results = {
        r.student_id: r
        for r in ExamResult.objects.filter(exam=exam)
    }

    return render(request, 'examinations/ca_score_entry.html', {
        'exam': exam,
        'students': students,
        'form': form,
        'existing_results': existing_results,
        'page_title': f'CA Scores — {exam.title}'
    })


# ── RESULTS ───────────────────────────────────────────────────

@login_required
@teaching_staff_required
def exam_results(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    results = ExamResult.objects.filter(
        exam=exam
    ).select_related('student', 'submission').order_by('-total_score')

    return render(request, 'examinations/exam_results.html', {
        'exam': exam,
        'results': results,
        'page_title': f'Results — {exam.title}'
    })


@login_required
@admin_staff_required
@require_POST
def exam_publish_results(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    ExamResult.objects.filter(exam=exam).update(
        is_published=True,
        published_by=request.user,
        published_at=timezone.now()
    )
    messages.success(
        request,
        f'Results for "{exam.title}" published successfully.'
    )
    return redirect('examinations:exam_results', pk=pk)


# ── EXAMINER DASHBOARD (Examiner/VP/Principal) ────────────

def exam_committee_required(view_func):
    """Check if user is in exam committee (Examiner, VP, or Principal)"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_exam_committee:
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('accounts:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@examiner_required
def examiner_dashboard(request):
    """Show examiner dashboard with exams awaiting approval"""
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    
    # Get filter parameters
    selected_class_id = request.GET.get('class_filter')
    selected_status = request.GET.get('status_filter')
    
    # Base queryset - exams AWAITING_APPROVAL (for main display and stats)
    awaiting_exams = Exam.objects.filter(
        session=current_session,
        term=current_term,
        status=Exam.ExamStatus.AWAITING_APPROVAL
    ).select_related('subject', 'class_arm', 'teacher')
    
    # Get all exams regardless of status for overall stats
    all_exams_queryset = Exam.objects.filter(
        session=current_session,
        term=current_term
    )
    
    # Calculate overall stats
    total_exams = all_exams_queryset.count()
    awaiting_approval = awaiting_exams.count()
    approved_exams = all_exams_queryset.filter(status=Exam.ExamStatus.APPROVED).count()
    draft_exams = all_exams_queryset.filter(status=Exam.ExamStatus.DRAFT).count()
    rejected_exams = all_exams_queryset.filter(
        status=Exam.ExamStatus.DRAFT,
        rejection_reason__isnull=False
    ).count()
    
    # Total submitted questions in exams awaiting approval
    total_awaiting_questions = ObjectiveQuestion.objects.filter(
        exam__in=awaiting_exams
    ).count()
    
    # Get all class arms that have exams awaiting approval
    class_arms = ClassArm.objects.filter(
        exams__in=awaiting_exams
    ).distinct().order_by('level__name', 'name')
    
    # Get classe arms with stats
    class_arms_with_stats = []
    for class_arm in class_arms:
        class_exams = awaiting_exams.filter(class_arm=class_arm)
        
        exam_count = class_exams.count()
        total_questions = ObjectiveQuestion.objects.filter(
            exam__in=class_exams
        ).count()
        
        class_arms_with_stats.append({
            'id': class_arm.id,
            'pk': class_arm.pk,
            'level': class_arm.level,
            'name': class_arm.name,
            'level_name': class_arm.level.name if class_arm.level else '',
            'class_name': class_arm.name,  
            'exam_count': exam_count,
            'total_questions': total_questions,
            'exams': list(class_exams)
        })
    
    # Get all class arms for filter dropdown
    all_class_arms = ClassArm.objects.all().order_by('level__name', 'name')
    
    # Get selected class for display
    selected_class_arm = None
    if selected_class_id:
        try:
            selected_class_arm = ClassArm.objects.get(pk=selected_class_id)
        except ClassArm.DoesNotExist:
            pass
    
    # Prepare list of exams to display
    # If a status filter is selected, use all exams; otherwise filter by status
    if selected_status:
        # When status filter is used, show all exams for filtering
        base_queryset = all_exams_queryset
    else:
        # When no status filter, show only exams awaiting approval
        base_queryset = awaiting_exams
    
    # Apply class filter if selected
    if selected_class_id:
        exams_list = list(base_queryset.filter(
            class_arm_id=selected_class_id
        ).select_related('subject', 'class_arm', 'teacher').order_by('-created_at'))
    else:
        exams_list = list(base_queryset.select_related('subject', 'class_arm', 'teacher').order_by('-created_at'))
    
    # Apply status filter if selected
    if selected_status:
        if selected_status == 'AWAITING_APPROVAL':
            exams_list = [e for e in exams_list if e.status == 'AWAITING_APPROVAL']
        elif selected_status == 'APPROVED':
            exams_list = [e for e in exams_list if e.status == 'APPROVED']
        elif selected_status == 'REJECTED':
            exams_list = [e for e in exams_list if e.status == 'DRAFT' and e.rejection_reason]
    
    context = {
        'page_title': 'Exam Approval Dashboard',
        'current_session': current_session,
        'current_term': current_term,
        'class_arms': class_arms_with_stats,
        'all_class_arms': all_class_arms,
        'total_exams': total_exams,
        'awaiting_approval': awaiting_approval,
        'approved_exams': approved_exams,
        'draft_exams': draft_exams,
        'rejected_exams': rejected_exams,
        'total_awaiting_questions': total_awaiting_questions,
        'exams_list': exams_list,
        'selected_class_id': selected_class_id,
        'selected_class_arm': selected_class_arm,
        'selected_status': selected_status,
    }
    return render(request, 'examinations/examiner_dashboard.html', context)

@login_required
@examiner_required
def examiner_class_subjects(request, class_arm_id):
    """Show all exams for a class awaiting approval"""
    class_arm = get_object_or_404(ClassArm, pk=class_arm_id)
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    
    # Get exams awaiting approval for this class
    exams = Exam.objects.filter(
        class_arm=class_arm,
        session=current_session,
        term=current_term,
        status=Exam.ExamStatus.AWAITING_APPROVAL
    ).select_related('subject', 'teacher').order_by('-created_at')
    
    # Get all unique subjects taught in this class
    from academics.models import Subject
    subjects = Subject.objects.filter(
        teacher_assignments__class_arm=class_arm
    ).distinct().order_by('name')
    
    # Organize data by subject
    subject_data = []
    for subject in subjects:
        subject_exams = exams.filter(subject=subject)
        # Get all teachers for this subject-class combination
        teachers_assignments = SubjectTeacherAssignment.objects.filter(
            subject=subject,
            class_arm=class_arm
        ).select_related('teacher')
        teachers = [assignment.teacher for assignment in teachers_assignments]
        
        subject_data.append({
            'subject': subject,
            'teachers': teachers,
            'exams': subject_exams
        })
    
    context = {
        'page_title': f'Exams Awaiting Approval — {class_arm}',
        'class_arm': class_arm,
        'current_session': current_session,
        'current_term': current_term,
        'subject_data': subject_data,
        'exams': exams,
    }
    return render(request, 'examinations/examiner_class_subjects.html', context)


@login_required
@examiner_required
def examiner_exam_review(request, exam_id):
    """Review and approve/reject an exam's questions"""
    exam = get_object_or_404(Exam, pk=exam_id)
    objectives = exam.objectives.all().order_by('id')
    theory_questions = exam.theory_questions.all().order_by('order', 'id')
    
    if request.method == 'POST':
        # Only allow approval/rejection actions for awaiting approval exams
        if exam.status != Exam.ExamStatus.AWAITING_APPROVAL:
            messages.error(request, 'You can only approve or reject exams that are awaiting approval.')
            return redirect('examinations:examiner_dashboard')
        
        action = request.POST.get('action', '').upper()
        reason = request.POST.get('reason', '').strip() if action == 'REJECT' else ''
        
        if action == 'APPROVE':
            if exam.approve(request.user):
                messages.success(
                    request,
                    f'Exam "{exam.title}" has been approved successfully.'
                )
            else:
                messages.error(request, 'Could not approve exam. Please try again.')
        elif action == 'REJECT':
            if not reason:
                messages.error(request, 'You must provide a rejection reason.')
                return render(request, 'examinations/examiner_exam_review.html', {
                    'page_title': f'Review Exam — {exam.title}',
                    'exam': exam,
                    'objectives': objectives,
                    'theory_questions': theory_questions,
                    'teacher_name': exam.teacher.user.get_full_name() if exam.teacher else 'Unknown',
                })
            if exam.reject(request.user, reason):
                messages.success(
                    request,
                    f'Exam "{exam.title}" has been rejected and returned to teacher for revision.'
                )
            else:
                messages.error(request, 'Could not reject exam. Please try again.')
        else:
            messages.error(request, 'Invalid action.')
            return render(request, 'examinations/examiner_exam_review.html', {
                'page_title': f'Review Exam — {exam.title}',
                'exam': exam,
                'objectives': objectives,
                'theory_questions': theory_questions,
                'teacher_name': exam.teacher.user.get_full_name() if exam.teacher else 'Unknown',
            })
        
        return redirect('examinations:examiner_dashboard')
    
    context = {
        'page_title': f'Review Exam — {exam.title}',
        'exam': exam,
        'objectives': objectives,
        'theory_questions': theory_questions,
        'teacher_name': exam.teacher.user.get_full_name() if exam.teacher else 'Unknown',
    }
    return render(request, 'examinations/examiner_exam_review.html', context)