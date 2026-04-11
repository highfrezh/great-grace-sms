from django.shortcuts import render, redirect, get_object_or_404

from django.urls import reverse

from django.contrib.auth.decorators import login_required

from django.contrib import messages

from django.db import transaction

from django.db.models import Q, Sum

from django.core.paginator import Paginator

from accounts.decorators import teaching_staff_required, admin_staff_required

from academics.models import AcademicSession, Term, ClassArm

from students.models import Student, StudentEnrollment

from examinations.models import ExamResult

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



    report_cards = ReportCard.objects.filter(student=student)

    

    # Filter for student role

    if is_student:

        report_cards = report_cards.filter(is_published=True)

        

    report_cards = report_cards.order_by('session__start_date', 'term__name')



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

        arm.commented_count = report_cards.exclude(teacher_comment='').exclude(teacher_comment__isnull=True).count()

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



    available_sessions = AcademicSession.objects.filter(

        reportcard__student=student,

        reportcard__is_published=True

    ).distinct().order_by('-start_date')



    available_terms = Term.objects.filter(

        reportcard__student=student,

        reportcard__is_published=True

    ).distinct().order_by('id')



    return render(request, 'results/student_results_list.html', {

        'student': student,

        'published_cards': published_cards,

        'available_sessions': available_sessions,

        'available_terms': available_terms,

        'selected_session_id': int(session_id) if session_id else None,

        'selected_term_id': int(term_id) if term_id else None,

        'page_title': 'My Academic Results'

    })



