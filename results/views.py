import json
from .forms import PrincipalReportCardForm
from django.shortcuts import render, redirect, get_object_or_404

from django.urls import reverse

from django.http import JsonResponse

from django.contrib.auth.decorators import login_required

from django.contrib import messages

from django.db import transaction

from django.db.models import Q, Sum, Avg

from django.core.paginator import Paginator

from accounts.decorators import teaching_staff_required, admin_staff_required

from academics.models import AcademicSession, Term, ClassArm

from students.models import Student, StudentEnrollment

from examinations.models import ExamResult, Exam

from django.views.decorators.http import require_POST

from .models import ReportCard, StudentDomainRating, ResultAuditLog

from .forms import ReportCardCommentForm

@login_required

@teaching_staff_required

def report_card_management(request):

    """Class teacher dashboard to manage comments and ratings for their class"""

    session = AcademicSession.get_current()

    term = Term.get_current()

    # Get the class arm where this user is the class teacher

    class_arm = ClassArm.objects.filter(

        class_teacher=request.user, 

        session=session

    ).first()

    if not class_arm:

        messages.warning(request, "You are not assigned as a class teacher for any class in the current session.")

        return redirect('accounts:dashboard')

    enrollments = StudentEnrollment.objects.filter(

        class_arm=class_arm,

        session=session,

        is_active=True

    ).select_related('student__user').order_by('student__user__last_name')

    # Get or create report cards for all students

    report_cards = []

    for enroll in enrollments:

        rc, created = ReportCard.objects.get_or_create(

            student=enroll.student,

            session=session,

            term=term,

            class_arm=class_arm

        )

        # Initialize domain ratings if they don't exist

        if created:

            with transaction.atomic():

                for attr in StudentDomainRating.AFFECTIVE_ATTRIBUTES:

                    StudentDomainRating.objects.get_or_create(

                        report_card=rc,

                        category=StudentDomainRating.Category.AFFECTIVE,

                        attribute_name=attr

                    )

                for attr in StudentDomainRating.PSYCHOMOTOR_ATTRIBUTES:

                    StudentDomainRating.objects.get_or_create(

                        report_card=rc,

                        category=StudentDomainRating.Category.PSYCHOMOTOR,

                        attribute_name=attr

                    )
        
        # Automatically update averages whenever the dashboard is viewed
        rc.recalculate_totals()
        
        report_cards.append(rc)

    return render(request, 'results/report_card_management.html', {

        'class_arm': class_arm,

        'report_cards': report_cards,

        'term': term,

        'page_title': f"Class Management — {class_arm.full_name}"

    })

@login_required

@teaching_staff_required

def update_student_results(request, student_id):

    """Update comments and domain ratings for a specific student"""

    term = Term.get_current()

    student = get_object_or_404(Student, pk=student_id)

    report_card = get_object_or_404(ReportCard, student=student, term=term)

    # Safety Check: Verify this teacher owns this class

    if report_card.class_arm.class_teacher != request.user:

        messages.error(request, "You are not authorized to manage this student's report card.")

        return redirect('results:report_card_management')

    # Status Check: Locked if published

    if report_card.is_published:

        messages.warning(request, f"Result for {student.full_name} is already published and locked. Contact Admin to unpublish before editing.")

        return redirect('results:report_card_management')

    if request.method == 'POST':

        form = ReportCardCommentForm(request.POST, instance=report_card)

        if form.is_valid():

            form.save()

            # Log the change

            ResultAuditLog.objects.create(

                report_card=report_card,

                modified_by=request.user,

                action="Updated Report Card Comments/Attendance",

                change_details=f"By {request.user.get_full_name() or request.user.username}"

            )

            # Update domain ratings from POST data

            for rating in report_card.domain_ratings.all():

                val_key = f'rating_{rating.id}'

                if val_key in request.POST:

                    old_rating = rating.rating

                    new_rating = int(request.POST.get(val_key))

                    if old_rating != new_rating:

                        rating.rating = new_rating

                        rating.save()

                        # Log domain change

                        ResultAuditLog.objects.create(

                            report_card=report_card,

                            modified_by=request.user,

                            action=f"Updated {rating.attribute_name} Rating",

                            change_details=f"From {old_rating} to {new_rating}"

                        )

            messages.success(request, f"Updated results for {student.full_name}")

            return redirect('results:report_card_management')

    else:

        form = ReportCardCommentForm(instance=report_card)

    return render(request, 'results/update_student_results.html', {

        'student': student,

        'report_card': report_card,

        'form': form,

        'affective': report_card.domain_ratings.filter(category=StudentDomainRating.Category.AFFECTIVE),

        'psychomotor': report_card.domain_ratings.filter(category=StudentDomainRating.Category.PSYCHOMOTOR),

        'page_title': f"Update Results — {student.full_name}"

    })

@login_required

@teaching_staff_required

def generate_class_report_cards(request):

    """Calculate totals, averages, and positions for all students in the class"""

    session = AcademicSession.get_current()

    term = Term.get_current()

    class_arm = ClassArm.objects.filter(

        class_teacher=request.user, 

        session=session

    ).first()

    if not class_arm:

        messages.error(request, "Class not found.")

        return redirect('accounts:dashboard')

    report_cards = ReportCard.objects.filter(

        class_arm=class_arm,

        session=session,

        term=term

    )

    with transaction.atomic():

        # 1. Update individual totals and averages
        for rc in report_cards:
            rc.recalculate_totals()
            rc.save()

    messages.success(request, f"Termly averages calculated for {class_arm.full_name}")

    return redirect('results:report_card_management')

@login_required

def view_report_card(request, pk):

    """View a single student's report card"""

    report_card = get_object_or_404(ReportCard, pk=pk)

    is_admin = request.user.is_staff or getattr(request.user, 'is_admin_staff', False)

    is_class_teacher = (report_card.class_arm.class_teacher == request.user)

    # Student/Parent check

    is_student = False

    try:

        is_student = (request.user.student_profile == report_card.student)

    except:

        pass

    is_parent = False

    try:

        is_parent = (request.user.guardian_profile.student == report_card.student)

    except:

        pass

    # Visibility check

    if is_student or is_parent:

        if not report_card.is_published:

            messages.error(request, "This report card has not been published yet.")

            return redirect('accounts:dashboard')

    elif not (is_admin or is_class_teacher):

        messages.error(request, "You are not authorized to view this report card.")

        return redirect('accounts:dashboard')

    # Sessional Performance Summary Data
    session_reports = ReportCard.objects.filter(
        student=report_card.student,
        session=report_card.session
    ).select_related('term')
    
    term_summary = {
        'FIRST': None,
        'SECOND': None,
        'THIRD': None
    }
    term_averages = []
    for sr in session_reports:
        term_summary[sr.term.name] = float(sr.average)
        term_averages.append(float(sr.average))
    
    cumulative_avg = sum(term_averages) / len(term_averages) if term_averages else 0

    return render(request, 'results/report_card_view.html', {

        'rc': report_card,

        'results': report_card.get_subject_results,

        'affective': report_card.domain_ratings.filter(category=StudentDomainRating.Category.AFFECTIVE),

        'psychomotor': report_card.domain_ratings.filter(category=StudentDomainRating.Category.PSYCHOMOTOR),

        'is_admin': is_admin,

        'is_class_teacher': is_class_teacher,

        'term_summary': term_summary,

        'cumulative_avg': round(cumulative_avg, 2),

    })

@login_required

@admin_staff_required

def view_transcript(request, student_id):

    """

    Cumulative academic history for a student across all sessions.

    Strictly for Principal/VP/Admin to print.

    """

    student = get_object_or_404(Student, pk=student_id)

    # Fetch all report cards for this student in chronological order

    report_cards = ReportCard.objects.filter(

        student=student

    ).select_related('session', 'term', 'class_arm__level').order_by('session__start_date', 'term__name')

    # Prepare data for each report card to avoid N+1 queries in template

    transcript_data = []

    for rc in report_cards:

        transcript_data.append({

            'report_card': rc,

            'subjects': rc.get_subject_results,

            'affective': rc.domain_ratings.filter(category=StudentDomainRating.Category.AFFECTIVE),

            'psychomotor': rc.domain_ratings.filter(category=StudentDomainRating.Category.PSYCHOMOTOR)

        })

    from django.utils import timezone

    return render(request, 'results/transcript_view.html', {

        'student': student,

        'transcript_data': transcript_data,

        'print_date': timezone.now(),

        'page_title': f"Academic Transcript — {student.full_name}"

    })

@login_required

@admin_staff_required

def all_student_results(request):

    """View allowing Principal/VP to view, search, and filter all report cards"""

    # Fetch parameters

    query = request.GET.get('q', '')

    session_id = request.GET.get('session', '')

    term_id = request.GET.get('term', '')

    class_arm_id = request.GET.get('class_arm', '')

    current_session = AcademicSession.get_current()
    current_term = Term.get_current()

    # Default to current session/term if not specified
    if not session_id and current_session:
        session_id = str(current_session.id)
    if not term_id and current_term:
        term_id = str(current_term.id)

    # Base Queryset

    report_cards = ReportCard.objects.select_related(

        'student', 'session', 'term', 'class_arm__level'

    ).order_by('-session__start_date', '-term__name', 'class_arm__level__order', 'student__user__last_name')

    # Filtering

    if session_id:

        report_cards = report_cards.filter(session_id=session_id)

    if term_id:

        report_cards = report_cards.filter(term_id=term_id)

    if class_arm_id:

        report_cards = report_cards.filter(class_arm_id=class_arm_id)

    # Searching

    if query:

        report_cards = report_cards.filter(

            Q(student__user__first_name__icontains=query) |

            Q(student__user__last_name__icontains=query) |

            Q(student__other_names__icontains=query) |

            Q(student__admission_number__icontains=query)

        )

    # Pagination Settings (50 records per page)

    paginator = Paginator(report_cards, 50)

    page_number = request.GET.get('page', 1)

    page_obj = paginator.get_page(page_number)

    # Filter Options Data

    sessions = AcademicSession.objects.all().order_by('-start_date')

    terms = Term.objects.all()

    class_arms = ClassArm.objects.select_related('level').all().order_by('level__order', 'name')

    return render(request, 'results/all_student_results.html', {

        'page_obj': page_obj,

        'query': query,

        'selected_session': session_id,

        'selected_term': term_id,

        'selected_class_arm': class_arm_id,

        'sessions': sessions,

        'terms': terms,

        'class_arms': class_arms,

        'page_title': "All Student Results"

    })

@login_required

@admin_staff_required

def manage_releases(request):

    """

    Dashboard for Principal/VP to manage result releases per class level/arm.

    """

    session_id = request.GET.get('session')

    term_id = request.GET.get('term')

    level_id = request.GET.get('level')

    # Defaults to current if not specified

    if session_id:

        current_session = get_object_or_404(AcademicSession, pk=session_id)

    else:

        current_session = AcademicSession.get_current()

    if term_id:

        current_term = get_object_or_404(Term, pk=term_id)

    else:

        current_term = Term.get_current()

    # Base queryset for class arms in the selected session

    class_arms = ClassArm.objects.filter(

        session=current_session

    ).select_related('level').order_by('level__order', 'name')

    # Filter by level if specified

    if level_id:

        class_arms = class_arms.filter(level_id=level_id)

    # Enrich class arms with report card stats for the selected term

    for arm in class_arms:

        report_cards = ReportCard.objects.filter(

            class_arm=arm, 

            session=current_session, 

            term=current_term

        )

        arm.total_students = report_cards.count()

        arm.published_count = report_cards.filter(is_published=True).count()

        arm.publish_percentage = (arm.published_count / arm.total_students * 100) if arm.total_students > 0 else 0

        arm.is_fully_published = arm.total_students > 0 and arm.published_count == arm.total_students

        # "Performance Compiled" = teacher has added a comment (result is complete)

        arm.commented_count = report_cards.exclude(
            teacher_comment=''
        ).exclude(
            teacher_comment__isnull=True
        ).exclude(
            principal_comment=''
        ).exclude(
            principal_comment__isnull=True
        ).count()

        arm.commented_percentage = (arm.commented_count / arm.total_students * 100) if arm.total_students > 0 else 0

        arm.is_fully_commented = arm.total_students > 0 and arm.commented_count == arm.total_students

    # Get options for filters

    from academics.models import ClassLevel

    sessions = AcademicSession.objects.all().order_by('-start_date')

    terms = Term.objects.all().order_by('id')

    levels = ClassLevel.objects.all().order_by('order')

    # Summary stats for the header row

    class_arms_list = list(class_arms)  # evaluate queryset once

    summary_published = sum(1 for arm in class_arms_list if arm.is_fully_published)

    summary_draft = sum(1 for arm in class_arms_list if not arm.is_fully_published)

    summary_total_students = sum(arm.total_students for arm in class_arms_list)

    return render(request, 'results/manage_releases.html', {

        'class_arms': class_arms_list,

        'current_session': current_session,

        'current_term': current_term,

        'sessions': sessions,

        'terms': terms,

        'levels': levels,

        'selected_session_id': int(session_id) if session_id else (current_session.id if current_session else None),

        'selected_term_id': int(term_id) if term_id else (current_term.id if current_term else None),

        'selected_level_id': int(level_id) if level_id else None,

        'published_count': summary_published,

        'draft_count': summary_draft,

        'total_students': summary_total_students,

        'page_title': 'Result Release Management'

    })

@login_required

@admin_staff_required

@require_POST

def toggle_release(request):

    """

    Bulk publish/unpublish results for a class arm.

    """

    class_arm_id = request.POST.get('class_arm_id')

    session_id = request.POST.get('session_id')

    term_id = request.POST.get('term_id')

    action = request.POST.get('action') # 'publish' or 'unpublish'

    session = get_object_or_404(AcademicSession, pk=session_id) if session_id else AcademicSession.get_current()

    term = get_object_or_404(Term, pk=term_id) if term_id else Term.get_current()

    class_arm = get_object_or_404(ClassArm, pk=class_arm_id)

    report_cards = ReportCard.objects.filter(

        class_arm=class_arm,

        session=session,

        term=term

    )

    if action == 'publish':

        report_cards.update(is_published=True)

        messages.success(request, f"Successfully published results for {class_arm.full_name}")

    else:

        report_cards.update(is_published=False)

        messages.success(request, f"Successfully unpublished results for {class_arm.full_name}")

    # Build redirect URL with existing filters

    redirect_url = reverse('results:manage_releases')

    params = []

    if session_id: params.append(f"session={session_id}")

    if term_id: params.append(f"term={term_id}")

    if params:

        redirect_url += "?" + "&".join(params)

    return redirect(redirect_url)

@login_required

def student_report_card_list(request):

    """

    View for students and parents to see a list of published report cards.

    """

    # Identify the target student

    student = None

    try:

        if hasattr(request.user, 'student_profile'):

            student = request.user.student_profile

        elif hasattr(request.user, 'guardian_profile'):

            student = request.user.guardian_profile.student

    except:

        pass

    if not student:

        messages.error(request, "Access denied. Student profile not found.")

        return redirect('accounts:dashboard')

    session_id = request.GET.get('session')

    term_id = request.GET.get('term')

    published_cards = ReportCard.objects.filter(

        student=student,

        is_published=True

    ).select_related('session', 'term', 'class_arm__level').order_by('-session__start_date', '-term__name')

    if session_id:

        published_cards = published_cards.filter(session_id=session_id)

    if term_id:

        published_cards = published_cards.filter(term_id=term_id)

    available_sessions = AcademicSession.objects.all().order_by('-start_date')

    available_terms_base = Term.objects.all()

    if session_id:

        available_terms = available_terms_base.filter(session_id=session_id).order_by('id')

    else:

        available_terms = available_terms_base.order_by('id')

    return render(request, 'results/student_results_list.html', {

        'student': student,

        'published_cards': published_cards,

        'available_sessions': available_sessions,

        'available_terms': available_terms,

        'selected_session_id': int(session_id) if session_id else None,

        'selected_term_id': int(term_id) if term_id else None,

        'page_title': 'My Academic Results'

    })

@login_required
@admin_staff_required
def admin_update_report_card(request, pk):
    """View for Principal/VP to add remarks to a specific report card"""
    report_card = get_object_or_404(ReportCard, pk=pk)
    student = report_card.student

    if request.method == 'POST':
        form = PrincipalReportCardForm(request.POST, instance=report_card)
        if form.is_valid():
            form.save()
            
            # Log the change
            ResultAuditLog.objects.create(
                report_card=report_card,
                modified_by=request.user,
                action="Added Principal/VP Remark",
                change_details=f"By Admin: {request.user.get_full_name() or request.user.username}"
            )
            
            messages.success(request, f"Official remark added for {student.full_name}")
            return redirect('results:all_student_results')
    else:
        form = PrincipalReportCardForm(instance=report_card)
    
    return render(request, 'results/admin_update_report_card.html', {
        'student': student,
        'report_card': report_card,
        'form': form,
        'page_title': f"Official Remark — {student.full_name}"
    })


# ── Performance Analytics APIs ──────────────────────────────────────

from .analytics import get_student_radar_data, get_student_trend_data, get_class_insight_data, get_school_insight_data

@login_required
def student_performance_summary_api(request, session_id):
    """
    Consolidated API for the new student insights dashboard.
    Returns:
    - subjects: [{name, ca1, ca2, theory, obj, total, total_percentage, grade, class_average_percentage, position}]
    - trend: [{term_name, average}]
    """
    user = request.user
    if not (user.is_student or user.is_staff):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    student = user.student_profile if user.is_student else None
    if not student:
        return JsonResponse({'error': 'Student profile not found'}, status=404)

    try:
        term_id = int(request.GET.get('term_id')) if request.GET.get('term_id') else None
    except (ValueError, TypeError):
        term_id = None

    # Find all terms in this session that have been published for this student
    published_term_ids = ReportCard.objects.filter(
        student=student,
        session_id=session_id,
        is_published=True
    ).values_list('term_id', flat=True)

    # 1. Per-term subject detail (only if the term is officially published)
    subjects_data = []
    if term_id and term_id in published_term_ids:
        # Results are visible only if the term is published
        results_qs = ExamResult.objects.filter(
            student=student,
            exam__session_id=session_id,
            exam__term_id=term_id,
        ).select_related('exam__subject', 'exam')

        for res in results_qs:
            avg_data = ExamResult.objects.filter(
                exam=res.exam
            ).aggregate(avg_score=Avg('total_score'))
            class_avg = float(avg_data['avg_score'] or 0)
            class_avg_pct = round(
                (class_avg / float(res.exam.total_marks)) * 100, 1
            ) if res.exam.total_marks > 0 else 0

            subjects_data.append({
                'name': res.exam.subject.name,
                'ca1': float(res.ca1_score),
                'ca2': float(res.ca2_score),
                'theory': float(res.theory_score),
                'obj': float(res.obj_score),
                'total': float(res.total_score),
                'total_percentage': float(res.percentage),
                'grade': res.grade,
                'class_average_percentage': class_avg_pct
            })

    # 2. Cross-term subject comparison (always full session, ignores term filter)
    all_terms = Term.objects.filter(session_id=session_id)
    subject_map = {}  # {subject_id: {id, name, term1, term2, term3}}

    term_mapping = {
        Term.TermName.FIRST: 'term1',
        Term.TermName.SECOND: 'term2',
        Term.TermName.THIRD: 'term3',
    }

    for term in all_terms:
        # Only include term comparison data if the term has been published
        if term.id not in published_term_ids:
            continue

        term_key = term_mapping.get(term.name)
        if not term_key:
            continue

        term_results = ExamResult.objects.filter(
            student=student,
            exam__session_id=session_id,
            exam__term_id=term.id,
        ).select_related('exam__subject')

        for res in term_results:
            subj = res.exam.subject
            if subj.id not in subject_map:
                subject_map[subj.id] = {'id': subj.id, 'name': subj.name,
                                         'term1': None, 'term2': None, 'term3': None}
            subject_map[subj.id][term_key] = round(float(res.percentage), 1)

    subject_term_data = []
    for subj_id, s in subject_map.items():
        scores = [v for v in [s['term1'], s['term2'], s['term3']] if v is not None]
        session_avg = round(sum(scores) / len(scores), 1) if scores else 0
        non_null = [s[f'term{i+1}'] for i in range(3) if s.get(f'term{i+1}') is not None]
        trend = round(non_null[-1] - non_null[0], 1) if len(non_null) >= 2 else 0
        subject_term_data.append({
            'id': subj_id, 'name': s['name'],
            'term1': s['term1'], 'term2': s['term2'], 'term3': s['term3'],
            'session_avg': session_avg, 'trend': trend,
        })

    # 3. Dynamic Trend Data (calculates from ReportCard for history, ensuring latest)
    # First, ensure current term report card is fresh for the insights view
    current_rc = ReportCard.objects.filter(
        student=student, session_id=session_id, term_id=term_id
    ).first() if term_id else None
    
    if current_rc:
        current_rc.recalculate_totals()

    trend_data = []
    report_cards = ReportCard.objects.filter(
        student=student,
        session_id=session_id,
        is_published=True
    ).select_related('term').order_by('term__name')
    
    for rc in report_cards:
        # Sync each card if it has 0 average but results exist
        if rc.average == 0:
            rc.recalculate_totals()
            
        trend_data.append({
            'term_name': rc.term.get_name_display(),
            'average': float(rc.average)
        })

    return JsonResponse({
        'success': True,
        'subjects': subjects_data,
        'subject_term_data': subject_term_data,
        'trend': trend_data
    })


@login_required
def class_performance_summary_api(request, class_arm_id):
    """
    Comprehensive class analytics for the staff dashboard.
    Returns stats, student list, subject performance, and grade distribution.
    """
    user = request.user
    class_arm = get_object_or_404(ClassArm, pk=class_arm_id)
    
    # Permission check: Admin Staff (Principal/VP) or the specific Class Teacher
    if not (user.is_admin_staff or class_arm.class_teacher == user):
        return JsonResponse({'error': 'Unauthorized: Only Class Teachers or Admins can view class performance insights.'}, status=403)
    
    session_id = request.GET.get('session_id')
    try:
        term_id = int(request.GET.get('term_id')) if request.GET.get('term_id') else None
    except (ValueError, TypeError):
        term_id = None
    
    if not session_id or not term_id:
        current_session = AcademicSession.get_current()
        current_term = Term.get_current()
        session_id = session_id or (current_session.id if current_session else None)
        term_id = term_id or (current_term.id if current_term else None)

    # 1. Base Data: Published Report Cards OR Approved Exams
    # For stats, we rely on report cards if available, but for live stats, we check both
    report_cards = ReportCard.objects.filter(
        class_arm_id=class_arm_id,
        session_id=session_id,
        term_id=term_id,
        is_published=True
    ).select_related('student').order_by('-average')

    if not report_cards.exists():
        # Fallback for empty data
        total_students = StudentEnrollment.objects.filter(class_arm_id=class_arm_id, session_id=session_id, is_active=True).count()
        return JsonResponse({
            'success': True, 
            'hasData': False, 
            'stats': {
                'totalStudents': total_students,
                'classAverage': 0,
                'passRate': 0,
                'topStudent': {'name': '-', 'score': 0},
                'bottomStudent': {'name': '-', 'score': 0}
            }, 
            'students': [], 
            'subjects': [], 
            'subjectPerformance': [], 
            'gradeDistribution': {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        })

    # 2. Stats Calculation
    total_students = StudentEnrollment.objects.filter(class_arm_id=class_arm_id, session_id=session_id, is_active=True).count()
    overall_avg = report_cards.aggregate(avg=Avg('average'))['avg'] or 0
    passed_count = report_cards.filter(average__gte=50).count()
    pass_rate = round((passed_count / total_students) * 100, 1) if total_students > 0 else 0
    
    top_rc = report_cards.first()
    bottom_rc = report_cards.last()

    def get_grade(avg):
        avg = float(avg)
        if avg >= 70: return 'A'
        elif avg >= 60: return 'B'
        elif avg >= 50: return 'C'
        elif avg >= 45: return 'D'
        else: return 'F'

    # 3. Student List & Trend
    students_data = []
    grade_counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
    
    # Get current term object to find previous term by name
    term_obj = get_object_or_404(Term, pk=term_id)
    
    # Previous term for trend (ordered by name alphabetically works for FIRST, SECOND, THIRD)
    prev_term = Term.objects.filter(
        session_id=session_id, 
        name__lt=term_obj.name
    ).order_by('-name').first()

    for rc in report_cards:
        grade = get_grade(rc.average)
        grade_counts[grade] += 1
        
        # Calculate trend
        trend = 0
        if prev_term:
            prev_rc = ReportCard.objects.filter(student=rc.student, session_id=session_id, term=prev_term, is_published=True).first()
            if prev_rc:
                trend = float(rc.average) - float(prev_rc.average)
        
        students_data.append({
            'id': rc.student.id,
            'name': rc.student.full_name,
            'average': float(rc.average),
            'grade': grade,
            'trend': round(trend, 1),
            'total': float(rc.total_score),
            'subjects_count': ExamResult.objects.filter(
                student=rc.student,
                exam__session_id=session_id,
                exam__term_id=term_id
            ).count()
        })

    # 4. Subject Performance
    subject_performance = []
    # Results are visible if explicitly published OR if the exam is approved
    exam_results = ExamResult.objects.filter(
        Q(is_published=True) | Q(exam__status=Exam.ExamStatus.APPROVED),
        student__enrollments__class_arm_id=class_arm_id,
        student__enrollments__session_id=session_id,
        student__enrollments__is_active=True,
        exam__session_id=session_id,
        exam__term_id=term_id
    ).values('exam__subject__id', 'exam__subject__name').annotate(
        avg_score=Avg('percentage')
    ).order_by('-avg_score')

    unique_subjects = []
    for res in exam_results:
        subject_performance.append({
            'id': res['exam__subject__id'],
            'name': res['exam__subject__name'],
            'average': round(float(res['avg_score']), 1)
        })
        unique_subjects.append({
            'id': res['exam__subject__id'],
            'name': res['exam__subject__name']
        })

    return JsonResponse({
        'success': True,
        'hasData': True,
        'stats': {
            'totalStudents': total_students,
            'classAverage': round(float(overall_avg), 1),
            'passRate': pass_rate,
            'topStudent': {'name': top_rc.student.full_name, 'score': float(top_rc.average)},
            'bottomStudent': {'name': bottom_rc.student.full_name, 'score': float(bottom_rc.average)}
        },
        'students': students_data,
        'subjects': unique_subjects,
        'subjectPerformance': subject_performance,
        'gradeDistribution': grade_counts
    })


@login_required
def student_performance_api(request, session_id, term_id, student_id):
    """API for Student Radar Chart and Line Graph"""
    # Verify permission: Must be the student, their parent, or staff
    user = request.user
    if user.is_student and user.student_profile.id != student_id:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    student_enrollment = get_object_or_404(
        StudentEnrollment, 
        student_id=student_id, 
        session_id=session_id, 
        is_active=True
    )
    class_arm_id = student_enrollment.class_arm_id

    try:
        radar_data = get_student_radar_data(student_id, session_id, term_id, class_arm_id)
        trend_data = get_student_trend_data(student_id, session_id)
        return JsonResponse({
            'success': True,
            'radar': radar_data,
            'trend': trend_data
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@teaching_staff_required
def class_performance_api(request, session_id, term_id, class_arm_id):
    """API for Teacher Insight Data"""
    # Verify permission: Must be the class teacher or admin
    class_arm = get_object_or_404(ClassArm, id=class_arm_id)
    if not (request.user.is_admin_staff or class_arm.class_teacher == request.user):
        return JsonResponse({'error': 'Unauthorized. Must be Class Teacher or Admin.'}, status=403)
        
    try:
        data = get_class_insight_data(class_arm_id, session_id, term_id)
        return JsonResponse({'success': True, 'data': data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@admin_staff_required
def school_performance_api(request, session_id, term_id):
    """API for Principal Insight Data"""
    try:
        data = get_school_insight_data(session_id, term_id)
        return JsonResponse({'success': True, 'data': data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@teaching_staff_required
def staff_performance_insights(request):
    """View to return the HTML template container for the analytics SPA"""
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    
    all_terms = Term.objects.all().order_by('id')
    terms_by_session = {}
    for t in all_terms:
        if t.session_id not in terms_by_session:
            terms_by_session[t.session_id] = []
        terms_by_session[t.session_id].append({'id': t.id, 'name': t.get_name_display()})

    context = {
        'current_session': current_session,
        'current_term': current_term,
        'page_title': 'Performance Insights',
        'sessions': AcademicSession.objects.all().order_by('-start_date'),
        'terms_by_session': json.dumps(terms_by_session),
    }

    if request.user.is_admin_staff:
        # Pass all class arms so the principal can drill down into any of them
        class_arms = ClassArm.objects.filter(session=current_session).order_by('level__order', 'name')
    else:
        # For non-admin teaching staff, only show classes they manage as Class Teacher
        class_arms = ClassArm.objects.filter(class_teacher=request.user, session=current_session).order_by('level__order', 'name')
        
    context['class_arms'] = class_arms
    
    # Pre-select the first available class
    managed_class = class_arms.first()
    if managed_class:
        context['default_class_id'] = managed_class.id
        context['default_class_name'] = managed_class.full_name
            
    return render(request, 'results/insights_staff.html', context)

@login_required
def student_performance_insights(request):
    """View to return the HTML template container for the Student analytics SPA"""
    if not request.user.is_student:
        return redirect('accounts:dashboard')
        
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    student = request.user.student_profile
    
    all_terms = Term.objects.all().order_by('id')
    terms_by_session = {}
    for t in all_terms:
        if t.session_id not in terms_by_session:
            terms_by_session[t.session_id] = []
        terms_by_session[t.session_id].append({'id': t.id, 'name': t.get_name_display()})

    context = {
        'current_session': current_session,
        'current_term': current_term,
        'student': student,
        'page_title': 'My Academic Insights',
        'sessions': AcademicSession.objects.all().order_by('-start_date'),
        'terms_by_session': json.dumps(terms_by_session),
    }
    
    return render(request, 'results/insights_student.html', context)
