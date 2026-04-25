from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q
from academics.models import AcademicSession, Term, SubjectTeacherAssignment, ClassArm
from students.models import StudentEnrollment, Attendance, Student
from staff.models import StaffProfile
from examinations.models import Exam
from accounts.decorators import admin_staff_required
from results.models import ReportCard, ResultAuditLog


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        if username:
            # Normalize admission numbers (strip slashes and lowercase)
            username = username.replace('/', '').lower()
            
        password = request.POST.get('password')

        # Check if user exists but is deactivated
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user_record = User.objects.filter(username=username).first()
        if user_record and not user_record.is_active:
            messages.error(request, 'This account has been deactivated. Please contact administration.')
            return render(request, 'accounts/login.html')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(
                request,
                f'Welcome back, {user.get_full_name() or user.username}!'
            )
            return redirect('accounts:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('accounts:login')


@login_required
def dashboard_view(request):
    user = request.user
    
    # Force password change on first login (Exclude Students per request)
    if user.is_first_login and not user.is_student and request.resolver_match.url_name != 'password_change':
        messages.info(request, 'For security reasons, please change your password to continue.')
        return redirect('accounts:password_change')

    primary_role = user.primary_role if not user.is_superuser else 'PRINCIPAL'

    if primary_role == 'STUDENT':
        return redirect('students:student_dashboard')
    elif primary_role == 'PARENT':
        # Fetch all children linked to this parent via the Guardian model
        # Strict check: Must match the user's current phone number to avoid ghost links
        guardian_links = user.guardian_profiles.filter(phone=user.phone_number).select_related('student')
        
        # Use a dictionary to keep only unique students (prevents same child showing twice)
        unique_children = {}
        for link in guardian_links:
            if link.student and link.student.is_active:
                unique_children[link.student.id] = link.student
        
        children = list(unique_children.values())
        
        context = {
            'page_title': 'Parent Dashboard',
            'children': children,
        }
        return render(request, 'accounts/dashboard_parent.html', context)

    # Redirect Principal and Vice Principal to their dedicated dashboard
    if primary_role in ('PRINCIPAL', 'VICE_PRINCIPAL') or user.is_superuser:
        return redirect('accounts:principal_dashboard')

    # Generic staff dashboard context
    context = {
        'page_title': 'Dashboard',
        'primary_role': primary_role,
        'primary_role_display': primary_role.replace('_', ' ').title(),
    }

    # If the user is teaching staff, gather academic metrics
    if user.is_teaching_staff or user.is_principal or user.is_vice_principal:
        # Reverted back to always showing Current Session on the main dashboard
        view_session = AcademicSession.get_current()
        view_term = Term.get_current()

        # Get staff profile
        staff_profile = StaffProfile.objects.filter(user=user).first()

        # 1. Assigned Subjects & Classes (Contextualized to Selected Session)
        assignments = SubjectTeacherAssignment.objects.filter(
            teacher=user,
        ).select_related('subject', 'class_level')

        subject_ids = set(assignments.values_list('subject_id', flat=True).distinct())
        
        # Map assignments to session-specific ClassArms
        class_arms_map = {
            (ca.level_id, ca.name): ca
            for ca in ClassArm.objects.filter(session=view_session).select_related('level')
        }

        assigned_class_ids = set()
        for assignment in assignments:
            assignment.class_arm = class_arms_map.get((assignment.class_level_id, assignment.arm_name))
            if assignment.class_arm:
                assigned_class_ids.add(assignment.class_arm.id)

        # Add managed classes (if Class Teacher) to the class IDs list
        managed_classes = ClassArm.objects.filter(class_teacher=user, session=view_session)
        managed_class_ids = set(managed_classes.values_list('id', flat=True))
        
        # Managed students count (including historical records for this session)
        student_filter = {
            'class_arm_id__in': managed_class_ids, 
            'session': view_session,
            'student__is_active': True  # Only count students still in the school
        }
        managed_students = StudentEnrollment.objects.filter(
            **student_filter
        ).values('student_id').distinct().count()

        # 2. Total Students 
        if user.is_class_teacher:
            total_students = managed_students
        else:
            total_student_filter = {
                'class_arm_id__in': assigned_class_ids, 
                'session': view_session,
                'student__is_active': True
            }
            total_students = StudentEnrollment.objects.filter(
                **total_student_filter
            ).values('student_id').distinct().count()

        # 3. Exam Stats
        teacher_exams = Exam.objects.filter(
            teacher=staff_profile,
            session=view_session,
            term=view_term
        )
        exam_stats = {
            'draft': teacher_exams.filter(status='DRAFT').count(),
            'awaiting': teacher_exams.filter(status='AWAITING_APPROVAL').count(),
            'approved': teacher_exams.filter(status='APPROVED').count(),
            'total': teacher_exams.count(),
        }

        # 4. Today's Attendance (Only relevant for current session)
        attendance_marked_today = False
        managed_class_names = ""
        if user.is_class_teacher:
            if managed_classes.exists():
                managed_class_names = ", ".join([str(c) for c in managed_classes])
                if view_session:
                    attendance_marked_today = Attendance.objects.filter(
                        class_arm__in=managed_classes,
                        date=timezone.now().date(),
                        session=view_session
                    ).exists()

        context.update({
            'current_session': view_session,
            'current_term': view_term,
            'assigned_subjects_count': len(subject_ids),
            'assigned_classes_count': len(assigned_class_ids),
            'total_students_count': total_students,
            'managed_students_count': managed_students,
            'exam_stats': exam_stats,
            'attendance_marked_today': attendance_marked_today,
            'managed_class_names': managed_class_names,
            'my_assignments': assignments,
        })

    return render(request, 'accounts/dashboard.html', context)


@login_required
@admin_staff_required
def principal_dashboard(request):
    """Dedicated executive dashboard for Principal and Vice Principal"""
    # Reverted back to always showing Current Session on the main dashboard
    view_session = AcademicSession.get_current()
    view_term = Term.get_current()
    today = timezone.now().date()

    # ── KPI: School-wide Student Count ──────────────────────────
    total_students = StudentEnrollment.objects.filter(
        session=view_session,
        student__is_active=True
    ).values('student_id').distinct().count()

    # ── KPI: Total Classes ──────────────────────────────────────
    total_classes = ClassArm.objects.filter(session=view_session).count()

    # ── KPI: Total Teaching Staff ────────────────────────────────
    total_staff = StaffProfile.objects.filter(is_active=True).count()

    # ── KPI: Exams Awaiting Approval ─────────────────────────────
    exams_awaiting = Exam.objects.filter(
        session=view_session,
        term=view_term,
        status='AWAITING_APPROVAL'
    ).count()

    # ── Report Cards Progress ─────────────────────────────────────
    total_report_cards = ReportCard.objects.filter(
        session=view_session,
        term=view_term
    ).count()
    published_report_cards = ReportCard.objects.filter(
        session=view_session,
        term=view_term,
        is_published=True
    ).count()
    report_card_pct = round((published_report_cards / total_report_cards * 100), 1) if total_report_cards > 0 else 0

    # ── Attendance Summary ──────────────────────────────────────────
    # Attendance is usually checked for today or current session
    classes_with_attendance_today = Attendance.objects.filter(
        date=today,
        session=view_session
    ).values('class_arm_id').distinct().count()
    attendance_pct = round((classes_with_attendance_today / total_classes * 100), 1) if total_classes > 0 else 0

    # ── Exam Stats Overview ───────────────────────────────────────
    all_exams = Exam.objects.filter(session=view_session, term=view_term)
    exam_summary = {
        'total': all_exams.count(),
        'draft': all_exams.filter(status='DRAFT').count(),
        'awaiting': all_exams.filter(status='AWAITING_APPROVAL').count(),
        'approved': all_exams.filter(status='APPROVED').count(),
    }

    # ── Recent Audit Activity ─────────────────────────────────────
    recent_activity = ResultAuditLog.objects.select_related(
        'report_card__student', 'modified_by'
    ).order_by('-created_at')[:8]

    # ── Gender Breakdown ──────────────────────────────────────────
    male_count = StudentEnrollment.objects.filter(
        student__gender='M',
        session=view_session,
        is_active=True
    ).values('student_id').distinct().count()
    female_count = total_students - male_count

    context = {
        'page_title': 'Principal Dashboard',
        'current_session': view_session,
        'current_term': view_term,
        'today': today,
        # KPIs
        'total_students': total_students,
        'total_classes': total_classes,
        'total_staff': total_staff,
        'exams_awaiting': exams_awaiting,
        # Report Cards
        'total_report_cards': total_report_cards,
        'published_report_cards': published_report_cards,
        'report_card_pct': report_card_pct,
        # Attendance
        'classes_with_attendance_today': classes_with_attendance_today,
        'attendance_pct': attendance_pct,
        # Exams
        'exam_summary': exam_summary,
        # Activity
        'recent_activity': recent_activity,
        # Demographics
        'male_count': male_count,
        'female_count': female_count,
    }

    return render(request, 'accounts/dashboard_principal.html', context)

@login_required
def password_change_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Update session to prevent logout
            update_session_auth_hash(request, user)
            
            # Mark first login as complete
            if user.is_first_login:
                user.is_first_login = False
                user.save()
                
            messages.success(request, 'Your password was successfully updated!')
            return redirect('accounts:dashboard')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/password_change.html', {
        'form': form,
        'page_title': 'Change Password'
    })

