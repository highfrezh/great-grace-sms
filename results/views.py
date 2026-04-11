from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum
from django.core.paginator import Paginator
from accounts.decorators import teaching_staff_required, admin_staff_required
from academics.models import AcademicSession, Term, ClassArm
from students.models import Student, StudentEnrollment
from examinations.models import ExamResult
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
            # Aggregate all ExamResults for this student in this term
            results = ExamResult.objects.filter(
                student=rc.student,
                exam__session=session,
                exam__term=term
            )
            
            total = results.aggregate(Sum('total_score'))['total_score__sum'] or 0
            count = results.count()
            avg = float(total) / count if count > 0 else 0
            
            rc.total_score = total
            rc.average = avg
            rc.save()

        # 2. Calculate positions
        # Order report cards by total score descending
        sorted_rcs = report_cards.order_by('-total_score')
        for i, rc in enumerate(sorted_rcs):
            rc.position = i + 1
            rc.save()

    messages.success(request, f"Termly positions and averages calculated for {class_arm.full_name}")
    return redirect('results:report_card_management')

@login_required
def view_report_card(request, pk):
    """View a single student's report card"""
    report_card = get_object_or_404(ReportCard, pk=pk)
    is_admin = request.user.is_staff or getattr(request.user, 'is_admin_staff', False)
    is_class_teacher = (report_card.class_arm.class_teacher == request.user)
    
    if not (is_admin or is_class_teacher):
        messages.error(request, "You are not authorized to view this report card.")
        return redirect('accounts:dashboard')

    return render(request, 'results/report_card_view.html', {
        'rc': report_card,
        'results': report_card.get_subject_results,
        'affective': report_card.domain_ratings.filter(category=StudentDomainRating.Category.AFFECTIVE),
        'psychomotor': report_card.domain_ratings.filter(category=StudentDomainRating.Category.PSYCHOMOTOR),
    })

@login_required
def view_transcript(request, student_id):
    """Cumulative academic history for a student across all sessions"""
    student = get_object_or_404(Student, pk=student_id)
    is_admin = request.user.is_staff or getattr(request.user, 'is_admin_staff', False)
    
    try:
        is_student = (request.user.student_profile == student)
    except:
        is_student = False

    if not (is_admin or is_student):
        messages.error(request, "You are not authorized to view this transcript.")
        return redirect('accounts:dashboard')

    report_cards = ReportCard.objects.filter(student=student).order_by('session__start_date', 'term__name')

    return render(request, 'results/transcript_view.html', {
        'student': student,
        'report_cards': report_cards,
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

