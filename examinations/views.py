from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from accounts.decorators import (
    admin_staff_required, teaching_staff_required, examiner_required,
    subject_teacher_required
)
from academics.models import AcademicSession, Term
from students.models import Student, StudentEnrollment
from .models import (
    Exam, Question, TheoryQuestion, ExamSubmission,
    StudentAnswer, TheoryScore, ExamResult, ExamDeadlinePenalty,
    ExamConfiguration
)
from .forms import (
    ExamForm, QuestionForm, TheoryQuestionForm,
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
def question_bulk_create(request):
    """
    Bulk creation interface for objective questions with theory file upload.
    Teachers can create multiple questions at once for an exam with dynamic form.
    """
    user = request.user
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    
    # Get exams created by this teacher
    exams = Exam.objects.filter(
        created_by=user,
        session=current_session,
        term=current_term
    ).select_related('subject', 'class_arm').order_by('-created_at')
    
    selected_exam = None
    theory_file_form = None
    
    if request.method == 'POST':
        exam_id = request.POST.get('exam_id')
        if not exam_id:
            messages.error(request, 'Please select an exam first.')
            return redirect('examinations:question_bulk_create')
        
        selected_exam = get_object_or_404(Exam, pk=exam_id, created_by=user)
        
        # Process bulk questions
        questions_data = []
        question_index = 0
        
        while True:
            q_text = request.POST.get(f'question_{question_index}_text')
            if not q_text:
                break
            
            q_data = {
                'text': q_text,
                'text_yoruba': request.POST.get(f'question_{question_index}_text_yoruba', ''),
                'option_a': request.POST.get(f'question_{question_index}_option_a'),
                'option_b': request.POST.get(f'question_{question_index}_option_b'),
                'option_c': request.POST.get(f'question_{question_index}_option_c'),
                'option_d': request.POST.get(f'question_{question_index}_option_d'),
                'option_a_yoruba': request.POST.get(f'question_{question_index}_option_a_yoruba', ''),
                'option_b_yoruba': request.POST.get(f'question_{question_index}_option_b_yoruba', ''),
                'option_c_yoruba': request.POST.get(f'question_{question_index}_option_c_yoruba', ''),
                'option_d_yoruba': request.POST.get(f'question_{question_index}_option_d_yoruba', ''),
                'correct_answer': request.POST.get(f'question_{question_index}_correct_answer'),
                'difficulty': request.POST.get(f'question_{question_index}_difficulty', 'MEDIUM'),
                'marks': int(request.POST.get(f'question_{question_index}_marks', 1)),
                'image': request.FILES.get(f'question_{question_index}_image'),
            }
            questions_data.append((question_index, q_data))
            question_index += 1
        
        if not questions_data:
            messages.error(request, 'Please add at least one question.')
            return redirect('examinations:question_bulk_create')
        
        # Validate all questions
        errors = []
        for idx, q_data in questions_data:
            if not q_data.get('text'):
                errors.append(f'Question {idx + 1}: Text is required')
            if not q_data.get('correct_answer'):
                errors.append(f'Question {idx + 1}: Correct answer is required')
            if not all([q_data.get('option_a'), q_data.get('option_b'), 
                       q_data.get('option_c'), q_data.get('option_d')]):
                errors.append(f'Question {idx + 1}: All four options are required')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect('examinations:question_bulk_create')
        
        # Create questions
        created_count = 0
        with transaction.atomic():
            for order, q_data in questions_data:
                question = Question(
                    exam=selected_exam,
                    order=order + 1
                )
                for field in ['text', 'text_yoruba', 'option_a', 'option_b', 'option_c', 
                             'option_d', 'option_a_yoruba', 'option_b_yoruba',
                             'option_c_yoruba', 'option_d_yoruba', 'correct_answer',
                             'difficulty', 'marks', 'image']:
                    if field in q_data:
                        setattr(question, field, q_data[field])
                question.save()
                created_count += 1
            
            # Handle theory file if provided
            if 'theory_file' in request.FILES:
                theory_file = request.FILES['theory_file']
                # Create or update TheoryQuestion
                theory_q, _ = TheoryQuestion.objects.update_or_create(
                    exam=selected_exam,
                    defaults={
                        'title': f'{selected_exam.title} - Theory Questions',
                        'instruction': request.POST.get('theory_instruction', ''),
                        'file': theory_file
                    }
                )
        
        messages.success(
            request,
            f'✅ Successfully created {created_count} objective question(s)!'
        )
        if 'theory_file' in request.FILES:
            messages.success(request, '✅ Theory file uploaded successfully!')
        
        return redirect('examinations:question_list', exam_pk=selected_exam.pk)
    
    # GET request - show form
    elif request.GET.get('exam_id'):
        try:
            selected_exam = Exam.objects.get(
                pk=request.GET.get('exam_id'),
                created_by=user
            )
        except Exam.DoesNotExist:
            pass
    
    return render(request, 'examinations/question_bulk_create.html', {
        'exams': exams,
        'selected_exam': selected_exam,
        'page_title': 'Create Bulk Exam Questions',
        'current_session': current_session,
        'current_term': current_term,
    })


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


@login_required
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