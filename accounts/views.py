from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from academics.models import AcademicSession, Term, SubjectTeacherAssignment, ClassArm
from students.models import StudentEnrollment, Attendance
from staff.models import StaffProfile
from examinations.models import Exam


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

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
    primary_role = user.primary_role if not user.is_superuser else 'PRINCIPAL'

    if primary_role == 'STUDENT':
        # Redirect to comprehensive student dashboard
        return redirect('students:student_dashboard')
    elif primary_role == 'PARENT':
        return render(request, 'accounts/dashboard_parent.html')
    
    # Generic staff dashboard context
    context = {
        'page_title': 'Dashboard',
        'primary_role': primary_role,
        'primary_role_display': primary_role.replace('_', ' ').title(),
    }

    # If the user is teaching staff, gather academic metrics
    if user.is_teaching_staff or user.is_principal or user.is_vice_principal:
        current_session = AcademicSession.get_current()
        current_term = Term.get_current()
        
        # Get staff profile
        staff_profile = StaffProfile.objects.filter(user=user).first()
        
        # 1. Assigned Subjects & Classes
        assignments = SubjectTeacherAssignment.objects.filter(
            teacher=user,
            session=current_session,
            term=current_term
        ).select_related('subject', 'class_arm')
        
        subject_ids = set(assignments.values_list('subject_id', flat=True).distinct())
        class_ids = set(assignments.values_list('class_arm_id', flat=True).distinct())
        
        # Add managed classes (if Class Teacher) to the class IDs list
        managed_classes = ClassArm.objects.filter(class_teacher=user, session=current_session)
        for c in managed_classes:
            class_ids.add(c.id)
            
        # 2. Total Students (across all assigned and managed classes)
        total_students = StudentEnrollment.objects.filter(
            class_arm_id__in=class_ids,
            session=current_session,
            is_active=True
        ).values('student_id').distinct().count()
        
        # 3. Exam Stats
        teacher_exams = Exam.objects.filter(
            teacher=staff_profile,
            session=current_session,
            term=current_term
        )
        exam_stats = {
            'draft': teacher_exams.filter(status='DRAFT').count(),
            'awaiting': teacher_exams.filter(status='AWAITING_APPROVAL').count(),
            'approved': teacher_exams.filter(status='APPROVED').count(),
            'total': teacher_exams.count(),
        }
        
        # 4. Today's Attendance (Only if Class Teacher)
        attendance_marked_today = False
        managed_class_names = ""
        if user.is_class_teacher:
            # Check for today's mark for classes they are teacher of
            managed_classes = ClassArm.objects.filter(class_teacher=user, session=current_session)
            if managed_classes.exists():
                managed_class_names = ", ".join([str(c) for c in managed_classes])
                attendance_marked_today = Attendance.objects.filter(
                    class_arm__in=managed_classes,
                    date=timezone.now().date(),
                    session=current_session
                ).exists()

        context.update({
            'current_session': current_session,
            'current_term': current_term,
            'assigned_subjects_count': len(subject_ids),
            'assigned_classes_count': len(class_ids),
            'total_students_count': total_students,
            'exam_stats': exam_stats,
            'attendance_marked_today': attendance_marked_today,
            'managed_class_names': managed_class_names,
            'my_assignments': assignments,
        })

    return render(request, 'accounts/dashboard.html', context)