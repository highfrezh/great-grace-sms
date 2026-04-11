from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
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
    ExamConfiguration, MalpracticeViolation
)
from .forms import (
    ExamForm, TeacherExamForm, QuestionForm, TheoryQuestionForm,
    VettingForm, CAScoreForm, ExamConfigurationForm
)
from results.models import ReportCard, ResultAuditLog
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
            'subject', 'created_by'
        ).prefetch_related('class_arms')
    elif user.is_examiner and not user.is_subject_teacher:
        # Examiner sees exams pending vetting
        exams = Exam.objects.filter(
            session=current_session,
            term=current_term,
            status__in=[
                Exam.Status.PENDING_VETTING,
                Exam.Status.VETTED
            ]
        ).select_related('subject', 'created_by').prefetch_related('class_arms')
    else:
        # Subject teacher sees their own exams
        exams = Exam.objects.filter(
            session=current_session,
            term=current_term,
            created_by=user
        ).select_related('subject').prefetch_related('class_arms')

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
        'subject', 'session', 'term',
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
    exam = get_object_or_404(Exam, pk=pk, status=Exam.ExamStatus.APPROVED)

    # Get student profile
    try:
        student = request.user.student_profile
    except Exception:
        messages.error(request, 'Student profile not found.')
        return redirect('accounts:dashboard')

    # Check enrollment - student must be in one of the exam's class arms
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    enrolled = StudentEnrollment.objects.filter(
        student=student,
        class_arm__in=exam.class_arms.all(),
        session=current_session,
        is_active=True
    ).exists()

    if not enrolled:
        messages.error(
            request, 'You are not enrolled in this class.'
        )
        return redirect('accounts:dashboard')

    # Check schedule
    now = timezone.now()
    if exam.scheduled_start_datetime and now < exam.scheduled_start_datetime:
        messages.error(
            request, 
            f'This exam is scheduled to start on {exam.scheduled_start_datetime.strftime("%b %d, %Y at %I:%M %p")}.'
        )
        return redirect('students:student_dashboard')
    
    if exam.scheduled_end_datetime and now > exam.scheduled_end_datetime:
        # Check if they already have an in-progress submission they can resume
        has_active_submission = ExamSubmission.objects.filter(
            exam=exam,
            student=student,
            status=ExamSubmission.SubmissionStatus.IN_PROGRESS
        ).exists()

        if not has_active_submission:
            messages.error(request, 'This exam has ended and is no longer available.')
            return redirect('students:student_dashboard')

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

    # Calculate remaining time on resume (account for elapsed time with 5-min grace period)
    if not created:
        # Use last_autosave_at as reference if available, otherwise started_at
        reference_time = submission.last_autosave_at or submission.started_at
        time_away = (timezone.now() - reference_time).total_seconds()
        
        # Apply 5-minute (300s) grace period
        penalty = max(0, int(time_away) - 300)
        
        if penalty > 0:
            # Deduct penalty from the LAST SAVED remaining time
            if submission.time_remaining_seconds is not None:
                submission.time_remaining_seconds = max(0, submission.time_remaining_seconds - penalty)
            else:
                # Fallback calculation if somehow time_remaining_seconds was null
                total_seconds = exam.duration_minutes * 60
                submission.time_remaining_seconds = max(0, total_seconds - int(time_away))
        
        submission.save()

    # Get questions
    questions = list(exam.objectives.all())
    if hasattr(exam, 'randomize_questions') and exam.randomize_questions:
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
        'exam_duration_minutes': exam.duration_minutes,
        'page_title': exam.title
    })


@login_required
@require_POST
@csrf_exempt
@transaction.atomic
def exam_autosave(request, pk):
    """Auto-save student answers every 30 seconds via AJAX"""
    exam = get_object_or_404(Exam, pk=pk)
    try:
        student = request.user.student_profile
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Student profile not found'}, status=400)

    submission = get_object_or_404(
        ExamSubmission, exam=exam, student=student
    )

    if submission.is_complete:
        return JsonResponse({'status': 'already_submitted', 'message': 'Exam already submitted'})

    # Save answers
    answer_count = 0
    for key, value in request.POST.items():
        if key.startswith('answer_'):
            question_id = int(key.replace('answer_', ''))
            StudentAnswer.objects.update_or_create(
                submission=submission,
                question_id=question_id,
                defaults={'selected_option': value}
            )
            answer_count += 1

    # Save remaining time
    time_remaining = request.POST.get('time_remaining')
    if time_remaining:
        submission.time_remaining_seconds = max(0, int(time_remaining))
    
    # Update last autosave time
    submission.last_autosave_at = timezone.now()
    submission.save()

    return JsonResponse({
        'status': 'saved',
        'message': f'Saved {answer_count} answers',
        'answers_saved': answer_count,
        'time_remaining': submission.time_remaining_seconds,
        'last_autosave': submission.last_autosave_at.isoformat()
    })


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
    correct_count = submission.answers.filter(is_correct=True).count()
    obj_score = correct_count * float(exam.marks_per_objective)
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
        f'Exam submitted successfully! View your detailed report below.'
    )
    return redirect('examinations:exam_submission_report', pk=pk)


@login_required
def exam_timer_status(request, pk):
    """Get current timer status for the exam (AJAX endpoint)"""
    exam = get_object_or_404(Exam, pk=pk)
    try:
        student = request.user.student_profile
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Student profile not found'}, status=400)

    submission = get_object_or_404(
        ExamSubmission, exam=exam, student=student
    )

    if submission.is_complete:
        return JsonResponse({
            'status': 'already_submitted',
            'is_complete': True,
            'time_remaining': 0,
            'message': 'Exam already submitted'
        })

    # Calculate actual remaining time with 5-min grace period logic
    reference_time = submission.last_autosave_at or submission.started_at
    time_away = (timezone.now() - reference_time).total_seconds()
    
    # Apply 5-minute (300s) grace period
    penalty = max(0, int(time_away) - 300)
    
    if submission.time_remaining_seconds is not None:
        # Penalty is only applied to the last known saved time
        calculated_remaining = max(0, submission.time_remaining_seconds - penalty)
    else:
        # Fallback to absolute wall-clock if no autosave exists yet
        total_seconds = exam.duration_minutes * 60
        calculated_remaining = max(0, total_seconds - int(time_away))

    return JsonResponse({
        'status': 'ok',
        'is_complete': False,
        'time_remaining': calculated_remaining,
        'exam_duration': exam.duration_minutes * 60,
        'started_at': submission.started_at.isoformat(),
        'last_autosave_at': submission.last_autosave_at.isoformat() if submission.last_autosave_at else None,
        'tab_switch_count': submission.tab_switch_count,
        'fullscreen_exit_count': submission.fullscreen_exit_count
    })


@login_required
@require_POST
@csrf_exempt
@transaction.atomic
def exam_auto_submit(request, pk):
    """Auto-submit exam when timer hits zero"""
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

    # Save any final answers
    for key, value in request.POST.items():
        if key.startswith('answer_'):
            question_id = int(key.replace('answer_', ''))
            StudentAnswer.objects.update_or_create(
                submission=submission,
                question_id=question_id,
                defaults={'selected_option': value}
            )

    # Log final malpractice data
    tab_switches = int(request.POST.get('tab_switches', 0))
    fullscreen_exits = int(request.POST.get('fullscreen_exits', 0))
    
    submission.tab_switch_count = max(submission.tab_switch_count, tab_switches)
    submission.fullscreen_exit_count = max(submission.fullscreen_exit_count, fullscreen_exits)
    submission.auto_submitted_reason = 'TIME_UP'

    # Calculate OBJ score
    correct_count = submission.answers.filter(is_correct=True).count()
    obj_score = correct_count * float(exam.marks_per_objective)
    
    submission.obj_score = obj_score
    submission.status = ExamSubmission.SubmissionStatus.AUTO_SUBMITTED
    submission.submitted_at = timezone.now()
    submission.save()

    # Create exam result
    result, _ = ExamResult.objects.get_or_create(
        exam=exam,
        student=student,
        defaults={'submission': submission}
    )
    result.obj_score = obj_score
    result.submission = submission
    result.save()

    return JsonResponse({
        'status': 'auto_submitted',
        'message': 'Exam auto-submitted due to timeout',
        'score': float(obj_score),
        'redirect_url': reverse('examinations:exam_submission_report', args=[pk])
    })


@login_required
def exam_result_student(request, pk):
    return redirect('examinations:exam_submission_report', pk=pk)


@login_required
def exam_submission_report(request, pk):
    """Detailed report for student immediately after submission"""
    exam = get_object_or_404(Exam, pk=pk)
    try:
        student = request.user.student_profile
    except Exception:
        return redirect('accounts:dashboard')

    submission = get_object_or_404(
        ExamSubmission, exam=exam, student=student
    )

    if not submission.is_complete:
        # Check if time is actually up (Safety break for loop)
        elapsed_seconds = (timezone.now() - submission.started_at).total_seconds()
        total_seconds = exam.duration_minutes * 60
        if elapsed_seconds >= total_seconds:
            # Auto-finalize it now if it wasn't already
            submission.status = ExamSubmission.SubmissionStatus.AUTO_SUBMITTED
            submission.submitted_at = timezone.now()
            submission.auto_submitted_reason = 'TIME_UP (Safety Finalize)'
            submission.save()
            messages.info(request, "Your exam time has expired. Results have been automatically compiled.")
        else:
            messages.warning(request, "You must complete the exam to see the report.")
            return redirect('examinations:exam_take', pk=pk)

    # Calculate statistics
    total_questions = exam.objectives.count()
    answers = submission.answers.select_related('question')
    answered_count = answers.count()
    
    # Calculate correct/wrong
    correct_count = 0
    for answer in answers:
        if answer.selected_option == answer.question.correct_option:
            correct_count += 1
    
    wrong_count = answered_count - correct_count
    unanswered_count = total_questions - answered_count

    # Get Exam Configuration for scaling
    from .models import ExamConfiguration
    config = ExamConfiguration.objects.filter(
        session=exam.session, 
        term=exam.term
    ).first()
    
    max_obj_marks = config.obj_marks if config else 100
    
    # If obj_score is already saved, use it, otherwise calculate it
    if submission.obj_score is not None:
        final_score = submission.obj_score
    else:
        final_score = (correct_count / total_questions * max_obj_marks) if total_questions > 0 else 0

    return render(request, 'examinations/exam_report.html', {
        'exam': exam,
        'submission': submission,
        'total_questions': total_questions,
        'answered_count': answered_count,
        'correct_count': correct_count,
        'wrong_count': wrong_count,
        'unanswered_count': unanswered_count,
        'final_score': round(final_score, 2),
        'max_obj_marks': max_obj_marks,
        'page_title': f'Exam Report — {exam.subject.name}'
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

    # Check if results are already published for these students
    # We check if at least one report card is published for this class/session/term
    is_locked = ReportCard.objects.filter(
        class_arm__in=exam.class_arms.all(),
        session=exam.session,
        term=exam.term,
        is_published=True
    ).exists()

    if is_locked:
        messages.warning(request, "Some or all results for this class are already published and locked. You will not be able to save new scores.")

    return render(request, 'examinations/theory_score_entry.html', {
        'exam': exam,
        'submissions': submissions,
        'theory_questions': theory_questions,
        'is_locked': is_locked,
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
        'subject', 'session', 'term'
    ).prefetch_related('class_arms').order_by('-created_at')
    
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
    ).select_related('subject', 'class_arm')
    
    form = TeacherExamForm(request.POST or None, teacher=request.user)
    
    if form.is_valid():
        try:
            with transaction.atomic():
                # Extract form data
                title = form.cleaned_data['title']
                subject = form.cleaned_data['subject']
                session = form.cleaned_data['session']
                term = form.cleaned_data['term']
                duration_minutes = form.cleaned_data['duration_minutes']
                theory_attachment = form.cleaned_data.get('theory_attachment')
                randomize_questions = form.cleaned_data.get('randomize_questions', True)
                
                # Get all class_arms for this subject from teacher's assignments
                assignments = SubjectTeacherAssignment.objects.filter(
                    teacher=request.user,
                    subject=subject
                ).values_list('class_arm', flat=True).distinct()
                
                class_arms = ClassArm.objects.filter(id__in=assignments)
                
                if not class_arms.exists():
                    messages.error(request, f'No classes found for {subject}. Check your subject-class assignments.')
                    form = TeacherExamForm(teacher=request.user)
                    return render(request, 'examinations/teacher_exam_create.html', {
                        'form': form,
                        'assignments': assignments,
                        'page_title': 'Create New Exam',
                        'current_session': current_session,
                        'current_term': current_term,
                    })
                
                # Create ONE exam with all class_arms
                exam = Exam(
                    title=title,
                    subject=subject,
                    teacher=staff_profile,
                    session=session,
                    term=term,
                    duration_minutes=duration_minutes,
                    theory_attachment=theory_attachment,
                    randomize_questions=randomize_questions
                )
                exam.save()
                
                # Add all class_arms to the exam
                exam.class_arms.set(class_arms)
                
                # Show success message with class count
                class_count = class_arms.count()
                class_names = ', '.join(str(ca) for ca in class_arms)
                messages.success(
                    request, 
                    f'Exam "{title}" created successfully for {class_count} class{"es" if class_count > 1 else ""}: {class_names}'
                )
                return redirect('examinations:teacher_exam_detail', pk=exam.pk)
        except IntegrityError as e:
            messages.error(
                request, 
                'An error occurred while creating the exam. The exam may already exist for this subject-session-term combination.'
            )
            form = TeacherExamForm(request.POST, teacher=request.user)
    
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
        Exam.objects.select_related('subject', 'session', 'term').prefetch_related('class_arms'),
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
        # Check if student's report card is already published
        report_card = ReportCard.objects.filter(
            student=submission.student,
            session=exam.session,
            term=exam.term
        ).first()

        if report_card and report_card.is_published:
            # Skip this student if locked
            continue

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
        enrollments__class_arm__in=exam.class_arms.all(),
        enrollments__session=current_session,
        enrollments__is_active=True
    ).order_by('last_name', 'first_name').distinct()

    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        if student_id:
            student = get_object_or_404(Student, pk=student_id)
            
            # Check if student's report card is already published
            report_card = ReportCard.objects.filter(
                student=student,
                session=exam.session,
                term=exam.term
            ).first()
            
            if report_card and report_card.is_published:
                messages.error(request, f"Scores for {student.full_name} are locked because their report card is published.")
                return redirect('examinations:ca_score_entry', pk=pk)

            ca1 = request.POST.get('ca1', 0) or 0
            ca2 = request.POST.get('ca2', 0) or 0
            theory = request.POST.get('theory', 0) or 0
            obj_score = request.POST.get('obj_score', 0) or 0

            result, _ = ExamResult.objects.get_or_create(
                exam=exam,
                student=student
            )
            result.ca1_score = float(ca1)
            result.ca2_score = float(ca2)
            result.theory_score = float(theory)
            result.obj_score = float(obj_score)
            result.last_modified_by = request.user
            
            # Audit Logging
            report_card, _ = ReportCard.objects.get_or_create(
                student=student,
                session=exam.session,
                term=exam.term,
                class_arm=student.enrollments.filter(session=exam.session, is_active=True).first().class_arm
            )
            
            ResultAuditLog.objects.create(
                report_card=report_card,
                modified_by=request.user,
                action=f"Updated Scores for {exam.subject.name}",
                change_details=f"CA1: {ca1}, CA2: {ca2}, Theory: {theory}, CBT: {obj_score}"
            )
            
            result.save()
            messages.success(request, f'Scores updated successfully for {student.full_name}.')
            return redirect('examinations:ca_score_entry', pk=pk)

    # Get existing CA scores
    existing_results = {
        r.student_id: r
        for r in ExamResult.objects.filter(exam=exam)
    }

    return render(request, 'examinations/subject_score_entry.html', {
        'exam': exam,
        'students': students,
        'existing_results': existing_results,
        'page_title': f'Score Entry — {exam.title}'
    })


# ── RESULTS ───────────────────────────────────────────────────

@login_required
@teaching_staff_required
def exam_results(request, pk):
    """Detailed performance report for teachers showing all assigned students"""
    exam = get_object_or_404(Exam, pk=pk)
    
    # Get all students assigned to this exam via class arms
    enrollments = StudentEnrollment.objects.filter(
        class_arm__in=exam.class_arms.all(),
        session=exam.session,
        is_active=True
    ).select_related('student__user', 'class_arm').order_by('class_arm', 'student__user__last_name')
    
    # Map submissions and results for quick lookup
    submissions = {s.student_id: s for s in ExamSubmission.objects.filter(exam=exam)}
    results = {r.student_id: r for r in ExamResult.objects.filter(exam=exam)}
    
    # Compile performance data
    performance_data = []
    for enroll in enrollments:
        student = enroll.student
        submission = submissions.get(student.id)
        result = results.get(student.id)
        
        status = 'NOT_STARTED'
        if submission:
            if submission.status in ['SUBMITTED', 'AUTO_SUBMITTED']:
                status = 'SUBMITTED'
            else:
                status = 'IN_PROGRESS'
        
        performance_data.append({
            'student': student,
            'class_arm': enroll.class_arm,
            'status': status,
            'submission': submission,
            'result': result
        })
    
    # Stats for summary row
    total_count = enrollments.count()
    submitted_count = sum(1 for d in performance_data if d['status'] == 'SUBMITTED')
    in_progress_count = sum(1 for d in performance_data if d['status'] == 'IN_PROGRESS')
    not_started_count = total_count - (submitted_count + in_progress_count)

    return render(request, 'examinations/exam_results.html', {
        'exam': exam,
        'performance_data': performance_data,
        'stats': {
            'total': total_count,
            'submitted': submitted_count,
            'in_progress': in_progress_count,
            'not_started': not_started_count,
        },
        'page_title': f'Results — {exam.title}'
    })


@login_required
@teaching_staff_required
@require_POST
def exam_reset_submission(request, exam_pk, student_pk):
    """Allows teacher to reset a student's exam attempt"""
    exam = get_object_or_404(Exam, pk=exam_pk)
    student = get_object_or_404(Student, pk=student_pk)
    
    # Permission check: Teacher of the exam, examiner, or superuser
    if not (request.user.is_superuser or request.user.is_examiner or exam.teacher.user == request.user):
        messages.error(request, "You are not authorized to reset this exam.")
        return redirect('examinations:exam_results', pk=exam_pk)
    
    # Delete submission and results
    # Deleting submission will cascade to answers and theory scores in most schemas
    # But we explicitly handle both for safety
    ExamSubmission.objects.filter(exam=exam, student=student).delete()
    ExamResult.objects.filter(exam=exam, student=student).delete()
    
    messages.success(request, f"Exam session for {student.user.get_full_name()} has been successfully reset.")
        
    return redirect('examinations:exam_results', pk=exam_pk)
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
    """Show examiner dashboard with exams awaiting approval grouped by subject"""
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    
    # Get filter parameters
    selected_subject_id = request.GET.get('subject_filter')
    selected_status = request.GET.get('status_filter')
    
    # Base queryset - exams AWAITING_APPROVAL (for main display and stats)
    awaiting_exams = Exam.objects.filter(
        session=current_session,
        term=current_term,
        status=Exam.ExamStatus.AWAITING_APPROVAL
    ).select_related('subject', 'teacher').prefetch_related('class_arms')
    
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
    
    # Get all subjects that have exams awaiting approval
    subjects = Subject.objects.filter(
        exams__in=awaiting_exams
    ).distinct().order_by('name')
    
    # Get subjects with stats (grouped by subject instead of class_arm)
    subjects_with_stats = []
    for subject in subjects:
        subject_exams = awaiting_exams.filter(subject=subject)
        
        # Get all class_arms for this subject's exams
        class_arms = ClassArm.objects.filter(
            exams__in=subject_exams
        ).distinct().order_by('level__name', 'name')
        
        exam_count = subject_exams.count()
        total_questions = ObjectiveQuestion.objects.filter(
            exam__in=subject_exams
        ).count()
        
        subjects_with_stats.append({
            'id': subject.id,
            'pk': subject.pk,
            'name': subject.name,
            'code': subject.code,
            'class_arms': class_arms,  # All classes for this subject
            'exam_count': exam_count,
            'total_questions': total_questions,
            'exams': list(subject_exams)
        })
    
    # Get all subjects for filter dropdown with their class arms
    all_subjects_queryset = Subject.objects.all().order_by('name')
    all_subjects = []
    for subject in all_subjects_queryset:
        # Get all class arms that have exams in this session/term for this subject
        subject_class_arms = list(ClassArm.objects.filter(
            exams__subject=subject,
            exams__session=current_session,
            exams__term=current_term
        ).distinct().order_by('level__name', 'name'))
        
        all_subjects.append({
            'id': subject.id,
            'pk': subject.pk,
            'name': subject.name,
            'code': subject.code,
            'class_arms': subject_class_arms
        })
    
    # Get selected subject for display
    selected_subject = None
    if selected_subject_id:
        try:
            selected_subject = Subject.objects.get(pk=selected_subject_id)
        except Subject.DoesNotExist:
            pass
    
    # Prepare list of exams to display
    if selected_status:
        base_queryset = all_exams_queryset
    else:
        base_queryset = awaiting_exams
    
    # Apply subject filter if selected
    if selected_subject_id:
        exams_list = list(base_queryset.filter(
            subject_id=selected_subject_id
        ).select_related('subject', 'teacher').prefetch_related('class_arms').order_by('-created_at').distinct())
    else:
        exams_list = list(base_queryset.select_related('subject', 'teacher').prefetch_related('class_arms').order_by('-created_at').distinct())
    
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
        'subjects': subjects_with_stats,
        'all_subjects': all_subjects,
        'total_subjects': Subject.objects.count(),
        'total_exams': total_exams,
        'awaiting_approval': awaiting_approval,
        'approved_exams': approved_exams,
        'draft_exams': draft_exams,
        'rejected_exams': rejected_exams,
        'total_awaiting_questions': total_awaiting_questions,
        'exams_list': exams_list,
        'selected_subject_id': selected_subject_id,
        'selected_subject': selected_subject,
        'selected_status': selected_status,
    }
    return render(request, 'examinations/examiner_dashboard.html', context)

@login_required
@examiner_required
def examiner_subject_exams(request, subject_id):
    """Show all exams for a subject awaiting approval"""
    subject = get_object_or_404(Subject, pk=subject_id)
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    
    # Get exams awaiting approval for this subject
    exams = Exam.objects.filter(
        subject=subject,
        session=current_session,
        term=current_term,
        status=Exam.ExamStatus.AWAITING_APPROVAL
    ).select_related('subject', 'teacher').prefetch_related('class_arms').order_by('-created_at')
    
    # Get all class arms involved in these exams
    class_arms = ClassArm.objects.filter(
        exams__in=exams
    ).distinct().order_by('level__name', 'name')
    
    context = {
        'page_title': f'Exams Awaiting Approval — {subject.name}',
        'subject': subject,
        'current_session': current_session,
        'current_term': current_term,
        'class_arms': class_arms,
        'exams': exams,
    }
    return render(request, 'examinations/examiner_subject_exams.html', context)


@login_required
@examiner_required
def examiner_class_subjects(request, class_arm_id):
    """Show all exams for a class awaiting approval"""
    class_arm = get_object_or_404(ClassArm, pk=class_arm_id)
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    
    # Get exams awaiting approval for this class
    exams = Exam.objects.filter(
        class_arms=class_arm,
        session=current_session,
        term=current_term,
        status=Exam.ExamStatus.AWAITING_APPROVAL
    ).select_related('subject', 'teacher').prefetch_related('class_arms').order_by('-created_at')
    
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
        # Allow approval/rejection for awaiting approval, and rejection for approved exams
        if exam.status not in [Exam.ExamStatus.AWAITING_APPROVAL, Exam.ExamStatus.APPROVED]:
            messages.error(request, 'You can only review exams that are awaiting approval or already approved.')
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


# ── EXAM SCHEDULING (Examiner/VP/Principal) ───────────────

@login_required
@examiner_required
def exam_schedule_list(request):
    """List all approved exams available for scheduling"""
    session_id = request.GET.get('session')
    term_id = request.GET.get('term')
    class_arm_id = request.GET.get('class_arm')

    if session_id:
        current_session = get_object_or_404(AcademicSession, pk=session_id)
    else:
        current_session = AcademicSession.get_current()
        
    if term_id:
        current_term = get_object_or_404(Term, pk=term_id)
    else:
        current_term = Term.get_current()

    # Get all approved exams
    queryset = Exam.objects.filter(status=Exam.ExamStatus.APPROVED)
    
    if current_session:
        queryset = queryset.filter(session=current_session)
    if current_term:
        queryset = queryset.filter(term=current_term)
        
    if class_arm_id:
        queryset = queryset.filter(class_arms__id=class_arm_id)

    exams = queryset.select_related('subject').prefetch_related('class_arms').order_by('subject__name').distinct()
    
    # Separate scheduled and unscheduled
    scheduled_exams = [e for e in exams if e.scheduled_start_datetime]
    unscheduled_exams = [e for e in exams if not e.scheduled_start_datetime]
    
    return render(request, 'examinations/exam_schedule_list.html', {
        'page_title': 'Schedule Exams',
        'current_session': current_session,
        'current_term': current_term,
        'selected_class_arm': int(class_arm_id) if class_arm_id else None,
        'scheduled_exams': scheduled_exams,
        'unscheduled_exams': unscheduled_exams,
        'sessions': AcademicSession.objects.all().order_by('-start_date'),
        'terms': Term.objects.all().order_by('id'),
        'class_arms': ClassArm.objects.all().order_by('name'),
    })


@login_required
@examiner_required
def exam_schedule_create(request, exam_id):
    """Schedule an approved exam with date and time"""
    exam = get_object_or_404(Exam, pk=exam_id, status=Exam.ExamStatus.APPROVED)
    
    if request.method == 'POST':
        start_datetime_str = request.POST.get('start_datetime')
        end_datetime_str = request.POST.get('end_datetime')
        
        if not start_datetime_str or not end_datetime_str:
            messages.error(request, 'Both start and end date/time are required.')
            return render(request, 'examinations/exam_schedule_form.html', {
                'exam': exam,
                'page_title': f'Schedule Exam — {exam.title}'
            })
        
        try:
            # Parse datetime strings (expects format: YYYY-MM-DDTHH:MM)
            from datetime import datetime
            start_datetime = datetime.fromisoformat(start_datetime_str)
            end_datetime = datetime.fromisoformat(end_datetime_str)
            
            # Make them timezone-aware
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
            
            if start_datetime >= end_datetime:
                messages.error(request, 'Start time must be before end time.')
                return render(request, 'examinations/exam_schedule_form.html', {
                    'exam': exam,
                    'page_title': f'Schedule Exam — {exam.title}'
                })
            
            # Update exam schedule
            exam.scheduled_start_datetime = start_datetime
            exam.scheduled_end_datetime = end_datetime
            exam.scheduled_by = request.user
            exam.scheduled_at = timezone.now()
            exam.save()
            
            messages.success(
                request,
                f'Exam "{exam.title}" has been scheduled for '
                f'{start_datetime.strftime("%b %d, %Y at %I:%M %p")} '
                f'to {end_datetime.strftime("%I:%M %p")}.'
            )
            return redirect('examinations:exam_schedule_list')
        
        except ValueError as e:
            messages.error(request, f'Invalid date/time format. Please use the date/time picker.')
            return render(request, 'examinations/exam_schedule_form.html', {
                'exam': exam,
                'page_title': f'Schedule Exam — {exam.title}'
            })
    
    return render(request, 'examinations/exam_schedule_form.html', {
        'exam': exam,
        'page_title': f'Schedule Exam — {exam.title}'
    })


@login_required
@examiner_required
def exam_schedule_edit(request, exam_id):
    """Edit an exam's schedule"""
    exam = get_object_or_404(Exam, pk=exam_id, status=Exam.ExamStatus.APPROVED)
    
    if request.method == 'POST':
        start_datetime_str = request.POST.get('start_datetime')
        end_datetime_str = request.POST.get('end_datetime')
        
        if not start_datetime_str or not end_datetime_str:
            messages.error(request, 'Both start and end date/time are required.')
            return render(request, 'examinations/exam_schedule_form.html', {
                'exam': exam,
                'page_title': f'Edit Schedule — {exam.title}',
                'is_edit': True
            })
        
        try:
            from datetime import datetime
            start_datetime = datetime.fromisoformat(start_datetime_str)
            end_datetime = datetime.fromisoformat(end_datetime_str)
            
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
            
            if start_datetime >= end_datetime:
                messages.error(request, 'Start time must be before end time.')
                return render(request, 'examinations/exam_schedule_form.html', {
                    'exam': exam,
                    'page_title': f'Edit Schedule — {exam.title}',
                    'is_edit': True
                })
            
            exam.scheduled_start_datetime = start_datetime
            exam.scheduled_end_datetime = end_datetime
            exam.scheduled_by = request.user
            exam.scheduled_at = timezone.now()
            exam.save()
            
            messages.success(request, f'Exam schedule updated successfully.')
            return redirect('examinations:exam_schedule_list')
        
        except ValueError as e:
            messages.error(request, f'Invalid date/time format.')
            return render(request, 'examinations/exam_schedule_form.html', {
                'exam': exam,
                'page_title': f'Edit Schedule — {exam.title}',
                'is_edit': True
            })
    
    return render(request, 'examinations/exam_schedule_form.html', {
        'exam': exam,
        'page_title': f'Edit Schedule — {exam.title}',
        'is_edit': True
    })


# ── EXAMINER ALL EXAMS MANAGEMENT ──────────────────────────

@login_required
@examiner_required
def examiner_all_exams(request):
    """Show all exams with filters for session, term, subject, class arm, status"""
    # Get filter parameters
    session_filter = request.GET.get('session')
    term_filter = request.GET.get('term')
    subject_filter = request.GET.get('subject')
    class_arm_filter = request.GET.get('class_arm')
    status_filter = request.GET.get('status')
    
    # Get current session/term as default
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    
    # Start with all exams
    exams_query = Exam.objects.select_related('subject', 'teacher', 'approved_by', 'rejected_by').prefetch_related('class_arms')
    
    # Apply session filter
    if session_filter:
        exams_query = exams_query.filter(session_id=session_filter)
    elif current_session:
        exams_query = exams_query.filter(session=current_session)
    
    # Apply term filter
    if term_filter:
        exams_query = exams_query.filter(term_id=term_filter)
    elif current_term:
        exams_query = exams_query.filter(term=current_term)
    
    # Apply subject filter
    if subject_filter:
        exams_query = exams_query.filter(subject_id=subject_filter)
    
    # Apply class arm filter
    if class_arm_filter:
        exams_query = exams_query.filter(class_arms__id=class_arm_filter).distinct()
    
    # Apply status filter
    if status_filter:
        exams_query = exams_query.filter(status=status_filter)
    
    # Order by created date descending
    exams = exams_query.order_by('-created_at')
    
    # Get filter options
    available_sessions = AcademicSession.objects.all().order_by('-start_date')
    available_terms = Term.objects.all().order_by('session', 'name')
    available_subjects = Subject.objects.all().order_by('name')
    available_class_arms = ClassArm.objects.select_related('level').order_by('level__order', 'name')
    
    # Calculate statistics
    total_exams = exams.count()
    by_status = {
        'DRAFT': exams.filter(status=Exam.ExamStatus.DRAFT).count(),
        'AWAITING_APPROVAL': exams.filter(status=Exam.ExamStatus.AWAITING_APPROVAL).count(),
        'APPROVED': exams.filter(status=Exam.ExamStatus.APPROVED).count(),
    }
    
    # Handle delete action only
    if request.method == 'POST':
        action = request.POST.get('action')
        selected_exams = [x for x in request.POST.getlist('selected_exams') if x]
        
        if action == 'delete' and selected_exams:
            selected_exams_obj = Exam.objects.filter(id__in=selected_exams)
            count = selected_exams_obj.count()
            if count > 0:
                selected_exams_obj.delete()
                messages.success(request, f'{count} exam(s) deleted successfully.')
            
            # Redirect to refresh the page
            return redirect('examinations:examiner_all_exams')
    
    context = {
        'page_title': 'All Exams Management',
        'exams': exams,
        'total_exams': total_exams,
        'by_status': by_status,
        'available_sessions': available_sessions,
        'available_terms': available_terms,
        'available_subjects': available_subjects,
        'available_class_arms': available_class_arms,
        'session_filter': session_filter,
        'term_filter': term_filter,
        'subject_filter': subject_filter,
        'class_arm_filter': class_arm_filter,
        'status_filter': status_filter,
        'current_session': current_session,
        'current_term': current_term,
    }
    
    return render(request, 'examinations/examiner_all_exams.html', context)