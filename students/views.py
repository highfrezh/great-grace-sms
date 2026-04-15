from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from django.utils import timezone
from accounts.decorators import admin_staff_required, class_teacher_required
from academics.models import AcademicSession, Term, ClassArm, SubjectTeacherAssignment, Subject
from accounts.models import User
from staff.models import StaffProfile
from .models import Student, Guardian, StudentEnrollment, Attendance, generate_admission_number
from .forms import StudentForm, GuardianForm, StudentEnrollmentForm, StudentSearchForm, BulkStudentImportForm

User = get_user_model()


from academics.models import ClassArm

@login_required
@admin_staff_required
def student_list(request):
    search_form = StudentSearchForm(request.GET)
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()

    active_students = Student.objects.filter(
        is_active=True
    ).select_related('user').prefetch_related(
        'enrollments__class_arm__level', 'guardians'
    )
    inactive_students = Student.objects.filter(
        is_active=False
    ).select_related('user').prefetch_related(
        'enrollments__class_arm__level'
    )

    # Search
    search_query = request.GET.get('search', '').strip()
    class_arm_filter = request.GET.get('class_arm', '')

    if search_query:
        active_students = active_students.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(other_names__icontains=search_query) |
            Q(admission_number__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(guardians__email__icontains=search_query)
        ).distinct()

    if class_arm_filter:
        active_students = active_students.filter(
            enrollments__class_arm_id=class_arm_filter,
            enrollments__is_active=True
        ).distinct()

    active_students = active_students.order_by('-date_admitted')
    inactive_students = inactive_students.order_by('-date_admitted')

    # Stats
    male_count = active_students.filter(gender='M').count()
    female_count = active_students.filter(gender='F').count()

    # Class arms for filter dropdown
    class_arms = ClassArm.objects.filter(
        session=current_session
    ).select_related('level').order_by('level__order', 'name') \
        if current_session else ClassArm.objects.none()

    # Pagination
    paginator = Paginator(active_students, 20)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)

    return render(request, 'students/student_list.html', {
        'page_obj': page_obj,
        'students': page_obj,
        'inactive_students': inactive_students,
        'search_form': search_form,
        'current_session': current_session,
        'current_term': current_term,
        'class_arms': class_arms,
        'male_count': male_count,
        'female_count': female_count,
        'page_title': 'Student Management'
    })


@login_required
@admin_staff_required
@transaction.atomic
def student_create(request):
    """Create new student with optional enrollment and guardian"""
    student_form = StudentForm(request.POST or None, request.FILES or None)
    enrollment_form = StudentEnrollmentForm(request.POST or None, prefix='enrollment')
    guardian_form = GuardianForm(request.POST or None, prefix='guardian')
    
    if request.method == 'POST':
        if student_form.is_valid():
            student = student_form.save()
            
            # Auto-create user account for student (admission number + DOB as password)
            create_student_user(student)
            
            # Handle enrollment
            if enrollment_form.is_valid() and enrollment_form.cleaned_data.get('class_arm'):
                enrollment = enrollment_form.save(commit=False)
                enrollment.student = student
                enrollment.save()
            
            # Handle guardian
            if guardian_form.is_valid() and guardian_form.cleaned_data.get('full_name'):
                guardian = guardian_form.save(commit=False)
                guardian.student = student
                guardian.is_primary = True
                guardian.save()
                
                # Auto-create parent user account
                create_guardian_user(guardian)
            
            messages.success(request, f'Student {student.full_name} admitted successfully. Admission No: {student.admission_number}')
            return redirect('students:student_detail', pk=student.pk)
        else:
            messages.error(request, 'Please fix the errors below.')
    
    return render(request, 'students/student_form.html', {
        'student_form': student_form,
        'enrollment_form': enrollment_form,
        'guardian_form': guardian_form,
        'page_title': 'Admit New Student',
        'is_edit': False
    })


@login_required
@admin_staff_required
def student_detail(request, pk):
    """Student detail view with enrollment history and guardians"""
    student = get_object_or_404(
        Student.objects.prefetch_related('enrollments', 'guardians', 'attendance_records'),
        pk=pk
    )
    
    current_enrollment = student.get_current_enrollment()
    enrollments = student.enrollments.all().order_by('-date_enrolled')[:5]
    guardians = student.guardians.all()
    
    return render(request, 'students/student_detail.html', {
        'student': student,
        'current_enrollment': current_enrollment,
        'enrollments': enrollments,
        'guardians': guardians,
        'page_title': student.full_name
    })


@login_required
@admin_staff_required
@transaction.atomic
def student_edit(request, pk):
    """Edit student information and primary guardian"""
    student = get_object_or_404(Student, pk=pk)
    
    # Get primary guardian
    guardian = student.guardians.filter(is_primary=True).first()
    if not guardian:
        guardian = student.guardians.first()
    
    student_form = StudentForm(request.POST or None, request.FILES or None, instance=student)
    guardian_form = GuardianForm(request.POST or None, instance=guardian, prefix='guardian')
    
    current_enrollment = student.get_current_enrollment()
    enrollment_form = StudentEnrollmentForm(request.POST or None, instance=current_enrollment)
    
    if request.method == 'POST':
        if student_form.is_valid() and guardian_form.is_valid() and enrollment_form.is_valid():
            old_phone = guardian.phone if guardian else None
            
            student_form.save()
            
            if guardian_form.cleaned_data.get('full_name'):
                new_guardian = guardian_form.save(commit=False)
                new_phone = new_guardian.phone
                
                if new_phone != old_phone and guardian and guardian.user:
                    # Sibling-Aware Logic: Update existing or Split away?
                    user = guardian.user
                    is_shared = user.guardian_profiles.count() > 1
                    
                    if is_shared:
                        # SPLIT: Move this student to a different account
                        # Clear the user link on the database record first
                        guardian.user = None
                        guardian.save()
                        
                        # Now update the local object and create the new user
                        new_guardian.user = None 
                        new_guardian.save()
                        create_guardian_user(new_guardian)
                        messages.info(request, f"Separated parent account for {new_phone}")
                    else:
                        # UPDATE: Only child, just update the existing account info
                        new_username = new_phone
                        if User.objects.filter(username=new_username).exclude(id=user.id).exists():
                            new_username = f"{new_phone}_rev"
                        
                        user.username = new_username
                        user.phone_number = new_phone
                        user.save()
                        new_guardian.save()
                        messages.info(request, f"Parent portal login updated to {new_username}")
                else:
                    # No phone change or first-time guardian setup
                    if not guardian:
                        new_guardian.student = student
                        new_guardian.is_primary = True
                    new_guardian.save()
                    if not new_guardian.user and new_guardian.phone:
                        create_guardian_user(new_guardian)

            if enrollment_form.cleaned_data.get('class_arm'):
                enrollment = enrollment_form.save(commit=False)
                enrollment.student = student
                enrollment.save()

            messages.success(request, f'{student.full_name} updated successfully.')
            return redirect('students:student_detail', pk=student.pk)
        else:
            messages.error(request, 'Please fix the errors below.')
    
    return render(request, 'students/student_form.html', {
        'student_form': student_form,
        'guardian_form': guardian_form,
        'enrollment_form': enrollment_form,
        'page_title': f'Edit — {student.full_name}',
        'is_edit': True,
        'student': student
    })


@login_required
@admin_staff_required
@transaction.atomic
def student_deactivate(request, pk):
    """Toggle student active status (deactivate/reactivate)"""
    student = get_object_or_404(Student, pk=pk)
    
    if request.method == 'POST':
        # Toggle the active status
        student.is_active = not student.is_active
        student.save()
        
        # Sync user account status
        if student.user:
            student.user.is_active = student.is_active
            student.user.save()
        
        if student.is_active:
            messages.success(request, f'{student.full_name} has been reactivated.')
        else:
            messages.success(request, f'{student.full_name} has been deactivated.')
    
    return redirect('students:student_list')


@login_required
@admin_staff_required
@transaction.atomic
def student_delete(request, pk):
    """Permanently delete student"""
    student = get_object_or_404(Student, pk=pk)
    
    if request.method == 'POST':
        student_name = student.full_name
        
        # Delete user account if exists
        if student.user:
            student.user.delete()
        
        # Delete the student
        student.delete()
        
        messages.success(request, f'{student_name} has been permanently deleted.')
    
    return redirect('students:student_list')


@login_required
@admin_staff_required
def student_reset_password(request, pk):
    """Admin resets a student's password to their date of birth"""
    student = get_object_or_404(Student, pk=pk)
    
    if request.method == 'POST':
        if student.user:
            password = student.date_of_birth.strftime('%d%m%Y')  # DDMMYYYY format
            student.user.set_password(password)
            student.user.is_first_login = False
            student.user.save()
            messages.success(
                request, 
                f"Password for {student.full_name} has been reset to their date of birth: {password}"
            )
        else:
            messages.error(request, f"{student.full_name} does not have a user account.")
            
    return redirect('students:student_detail', pk=pk)


def create_student_user(student):
    """Auto-create student user account with admission number + DOB as password"""
    from accounts.models import Role
    
    base_username = student.admission_number.replace('/', '').lower()
    username = base_username
    password = student.date_of_birth.strftime('%d%m%Y')  # DDMMYYYY format
    
    # Handle duplicate usernames
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1
    
    user = User.objects.create_user(
        username=username,
        email=f'{username}@greatgrace.edu',
        first_name=student.first_name,
        last_name=student.last_name,
        password=password,
        phone_number='00000000000',
        is_first_login=False
    )
    
    # Assign student role
    student_role, _ = Role.objects.get_or_create(name='STUDENT')
    user.roles.add(student_role)
    
    # Link to student profile
    student.user = user
    student.save()
    
    return user


def create_guardian_user(guardian):
    """
    Auto-create or link guardian user account for parent portal.
    Uses phone number as direct username and password for first login.
    """
    from accounts.models import Role, User
    
    if not guardian.phone:
        return None

    # check if user already exists with this phone number
    user = User.objects.filter(phone_number=guardian.phone).first()
    
    if not user:
        # Create new user
        username = guardian.phone
        password = guardian.phone
        
        # Ensure username is unique (highly likely with phone, but safety first)
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1
            
        user = User.objects.create_user(
            username=username,
            email=guardian.email or f'{username}@greatgrace.edu',
            first_name=guardian.full_name.split()[0],
            last_name=guardian.full_name.split()[-1] if len(guardian.full_name.split()) > 1 else '',
            password=password,
            phone_number=guardian.phone,
            is_first_login=True
        )
        
        # Assign parent role
        parent_role, _ = Role.objects.get_or_create(name='PARENT')
        user.roles.add(parent_role)
    
    # Link to student's guardian record
    guardian.user = user
    guardian.save()
    
    return user


@login_required
@admin_staff_required
def student_bulk_import(request):
    """Bulk import students from Excel/CSV file"""
    if request.method == 'POST':
        form = BulkStudentImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                import pandas as pd
                from datetime import datetime
                
                uploaded_file = request.FILES['file']
                class_arm = form.cleaned_data['class_arm']
                session = form.cleaned_data['session']
                term = form.cleaned_data['term']
                
                # Read Excel file
                df = pd.read_excel(uploaded_file)
                
                created_count = 0
                error_count = 0
                error_details = []
                
                for idx, row in df.iterrows():
                    try:
                        # Generate admission number using the same function as manual creation
                        admission_number = generate_admission_number()
                        
                        # Create student
                        student = Student.objects.create(
                            first_name=str(row.get('first_name', '')).strip(),
                            last_name=str(row.get('last_name', '')).strip(),
                            other_names=str(row.get('other_names', '')).strip() if pd.notna(row.get('other_names')) else '',
                            admission_number=admission_number,
                            date_of_birth=pd.to_datetime(row.get('date_of_birth')).date() if pd.notna(row.get('date_of_birth')) else None,
                            gender=str(row.get('gender', '')).upper()[:1] if pd.notna(row.get('gender')) else 'M',
                            address=str(row.get('address', '')).strip() if pd.notna(row.get('address')) else '',
                        )
                        
                        # Create enrollment
                        StudentEnrollment.objects.create(
                            student=student,
                            class_arm=class_arm,
                            session=session,
                            term=term,
                        )
                        
                        # Create guardian if data provided
                        guardian_name = str(row.get('guardian_name', '')).strip() if pd.notna(row.get('guardian_name')) else ''
                        if guardian_name:
                            guardian = Guardian.objects.create(
                                student=student,
                                full_name=guardian_name,
                                phone=str(row.get('guardian_phone', '')).strip() if pd.notna(row.get('guardian_phone')) else '',
                                email=str(row.get('guardian_email', '')).strip().lower() if pd.notna(row.get('guardian_email')) else '',
                                relationship=str(row.get('guardian_relationship', 'PARENT')).strip().upper() if pd.notna(row.get('guardian_relationship')) else 'PARENT',
                                is_primary=True,
                            )
                            create_guardian_user(guardian)
                        
                        # Create student user account
                        create_student_user(student)
                        
                        created_count += 1
                    except Exception as e:
                        error_count += 1
                        student_name = f"{row.get('first_name', 'Unknown')} {row.get('last_name', '')}".strip()
                        error_details.append(f"Row {idx + 2} ({student_name}): {str(e)}")
                        continue
                
                if created_count > 0:
                    messages.success(request, f'Successfully imported {created_count} students.')
                if error_count > 0:
                    messages.warning(request, f'{error_count} rows failed to import. Check details below.')
                    # Store errors in session for display
                    request.session['import_errors'] = error_details[:10]
                    request.session.modified = True
                    print(f"DEBUG: Error details captured: {error_details[:3]}")  # Debug print
                
                return redirect('students:student_bulk_import')
                
            except ImportError:
                messages.error(request, 'pandas and openpyxl are required. Install with: pip install pandas openpyxl')
            except Exception as e:
                messages.error(request, f'Error processing file: {str(e)}')
    else:
        form = BulkStudentImportForm()
        # Clear old errors when loading fresh
        print(f"DEBUG: Session errors on load: {request.session.get('import_errors', 'None')}")
        if 'import_errors' in request.session:
            del request.session['import_errors']
    
    return render(request, 'students/student_bulk_import.html', {
        'form': form,
        'page_title': 'Bulk Import Students'
    })


@login_required
@class_teacher_required
def attendance_mark(request, pk=None):
    from datetime import date as date_obj, datetime

    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    today = date_obj.today()

    # Get class arm
    if pk:
        class_arm = get_object_or_404(
            ClassArm, pk=pk, class_teacher=request.user
        )
    else:
        class_arm = ClassArm.objects.filter(
            class_teacher=request.user,
            session=current_session
        ).first()

    if not class_arm:
        messages.error(request, 'You are not assigned to any class.')
        return redirect('accounts:dashboard')

    # Get selected date from GET param or default to today
    date_str = request.GET.get('date', today.strftime('%Y-%m-%d'))
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = today

    # Get students
    students = Student.objects.filter(
        is_active=True,
        enrollments__class_arm=class_arm,
        enrollments__session=current_session,
        enrollments__term=current_term,
        enrollments__is_active=True
    ).order_by('last_name', 'first_name').distinct()

    # Handle POST — save attendance
    if request.method == 'POST':
        date_str_post = request.POST.get(
            'attendance_date', today.strftime('%Y-%m-%d')
        )
        try:
            attendance_date = datetime.strptime(
                date_str_post, '%Y-%m-%d'
            ).date()
        except ValueError:
            attendance_date = today

        # Boundary check - must be within current term and not in future
        if attendance_date < current_term.start_date:
            messages.error(request, f'Attendance cannot be marked before the term start date: {current_term.start_date.strftime("%d %B %Y")}')
            return redirect('students:attendance_mark', pk=class_arm.pk)
        
        if attendance_date > today:
            messages.error(request, 'Attendance cannot be marked for future dates.')
            return redirect('students:attendance_mark', pk=class_arm.pk)

        from results.models import ReportCard
        
        for student in students:
            status = request.POST.get(f'status_{student.id}', 'PRESENT')
            Attendance.objects.update_or_create(
                student=student,
                date=attendance_date,
                defaults={
                    'class_arm': class_arm,
                    'session': current_session,
                    'term': current_term,
                    'status': status,
                    'marked_by': request.user,
                }
            )
            
            # Auto-sync report card
            rc = ReportCard.objects.filter(
                student=student, 
                session=current_session, 
                term=current_term
            ).first()
            if rc:
                rc.sync_attendance()

        messages.success(
            request,
            f'Attendance saved for '
            f'{attendance_date.strftime("%d %B %Y")}.'
        )
        return redirect('students:attendance_mark', pk=class_arm.pk)

    # Existing attendance for selected date
    existing_attendance = {
        a.student_id: a
        for a in Attendance.objects.filter(
            class_arm=class_arm,
            session=current_session,
            term=current_term,
            date=selected_date
        )
    }

    attendance_marked = bool(existing_attendance)

    # Today's stats
    today_records = Attendance.objects.filter(
        class_arm=class_arm,
        session=current_session,
        term=current_term,
        date=today
    )
    present_today = today_records.filter(status='PRESENT').count()
    absent_today = today_records.filter(status='ABSENT').count()

    # Days marked this term
    from django.db.models import Count
    days_marked = Attendance.objects.filter(
        class_arm=class_arm,
        session=current_session,
        term=current_term
    ).values('date').distinct().count()

    # Term report per student
    from django.db.models import Q as DQ
    student_stats = []
    for student in students:
        records = Attendance.objects.filter(
            student=student,
            class_arm=class_arm,
            session=current_session,
            term=current_term
        )
        present = records.filter(status='PRESENT').count()
        absent = records.filter(status='ABSENT').count()
        total = present + absent
        percentage = round(present / total * 100) if total > 0 else 0
        student_stats.append({
            'student': student,
            'present': present,
            'absent': absent,
            'percentage': percentage,
        })

    # Attendance history — unique dates
    history_dates = Attendance.objects.filter(
        class_arm=class_arm,
        session=current_session,
        term=current_term
    ).values('date', 'marked_by__first_name',
             'marked_by__last_name').distinct().order_by('-date')

    attendance_history = []
    for entry in history_dates:
        day_records = Attendance.objects.filter(
            class_arm=class_arm,
            session=current_session,
            term=current_term,
            date=entry['date']
        )
        attendance_history.append({
            'date': entry['date'],
            'marked_by': f"{entry['marked_by__first_name']} "
                         f"{entry['marked_by__last_name']}",
            'present': day_records.filter(status='PRESENT').count(),
            'absent': day_records.filter(status='ABSENT').count(),
        })

    # Status choices for template
    attendance_statuses = [
        ('PRESENT', 'Present',
         'bg-green-100 text-green-700 hover:bg-green-200'),
        ('ABSENT', 'Absent',
         'bg-red-100 text-red-700 hover:bg-red-200'),
    ]

    return render(request, 'students/attendance_mark.html', {
        'class_arm': class_arm,
        'students': students,
        'today': today,
        'selected_date': selected_date,
        'existing_attendance': existing_attendance,
        'attendance_marked': attendance_marked,
        'current_session': current_session,
        'current_term': current_term,
        'present_today': present_today,
        'absent_today': absent_today,
        'days_marked': days_marked,
        'student_stats': student_stats,
        'attendance_history': attendance_history,
        'attendance_statuses': attendance_statuses,
        'page_title': f'Attendance — {class_arm.full_name}',
    })


# ── STUDENT DASHBOARD ──────────────────────────────────────

@login_required
def student_dashboard(request):
    """
    Student dashboard - view profile, current session, subjects, and available exams.
    Also supports Parents viewing their children's portals.
    """
    now = timezone.now()
    
    student_id = request.GET.get('student_id')
    if student_id and (request.user.is_parent or request.user.is_superuser):
        # Parents can view their linked children's dashboards
        student = get_object_or_404(Student, id=student_id)
        # Verify permission for parents - MUST check that guardian phone matches user phone
        if request.user.is_parent:
            if not request.user.guardian_profiles.filter(student=student, phone=request.user.phone_number).exists():
                messages.error(request, "Access denied: This student is no longer linked to your current phone number.")
                return redirect('accounts:dashboard')
    else:
        # Standard student login
        try:
            student = request.user.student_profile
        except Student.DoesNotExist:
            # If a parent tries to access the direct /students/dashboard/ without an ID
            if request.user.is_parent:
                return redirect('accounts:dashboard')
            messages.error(request, 'Student profile not found.')
            return redirect('accounts:dashboard')
    
    # Get current session and term
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    
    if not current_session or not current_term:
        messages.warning(request, 'No active session or term configured.')
        current_session = None
        current_term = None
    
    # Get exam configuration
    from examinations.models import ExamConfiguration, Exam, ExamSubmission
    exam_config = ExamConfiguration.objects.filter(
        session=current_session,
        term=current_term
    ).first()
    
    # Get current enrollment
    current_enrollment = student.enrollments.filter(
        is_active=True,
        session=current_session
    ).select_related('class_arm__level').first()
    
    class_arm = current_enrollment.class_arm if current_enrollment else None
    
    # Get subjects for current class/term
    subjects_data = []
    if class_arm and current_term:
        # Get all assignments, deduplicate by subject in Python (SQLite doesn't support DISTINCT ON)
        assignments_list = SubjectTeacherAssignment.objects.filter(
            class_arm=class_arm,
            term=current_term
        ).select_related('subject', 'teacher')
        
        # Deduplicate: keep first assignment per subject
        seen_subjects = {}
        for assignment in assignments_list:
            if assignment.subject_id not in seen_subjects:
                seen_subjects[assignment.subject_id] = assignment
        
        subjects = seen_subjects.values()
        
        for assignment in subjects:
            subject = assignment.subject
            
            # Check if exam is available
            exam = Exam.objects.filter(
                subject=subject,
                class_arms=class_arm,
                term=current_term,
                session=current_session,
                status=Exam.ExamStatus.APPROVED
            ).first()
            
            # Check submission status
            submission = None
            exam_status = None
            if exam:
                submission = ExamSubmission.objects.filter(
                    exam=exam,
                    student=student
                ).first()
                
                if submission:
                    exam_status = submission.status
            
            subjects_data.append({
                'subject': subject,
                'teacher': assignment.teacher,
                'exam': exam,
                'submission': submission,
                'exam_status': exam_status,
                'is_scheduled_to_start': exam is not None and (exam.scheduled_start_datetime is None or now >= exam.scheduled_start_datetime),
                'can_take_exam': exam is not None and (exam.scheduled_start_datetime is None or now >= exam.scheduled_start_datetime) and (submission is None or submission.status == ExamSubmission.SubmissionStatus.IN_PROGRESS)
            })
    
    # Get recent exam results
    from examinations.models import ExamResult
    recent_results = ExamResult.objects.filter(
        student=student,
        is_published=True
    ).select_related('exam__subject', 'submission').order_by('-updated_at')[:5]
    
    # Calculate stats
    total_subjects = len(subjects_data)
    
    # Get upcoming scheduled exams and release status
    can_view_exams = True
    if exam_config:
        if exam_config.exam_start_date and now < exam_config.exam_start_date:
            can_view_exams = False
        elif exam_config.exam_end_date and now > exam_config.exam_end_date:
            can_view_exams = False
    
    if can_view_exams:
        # Only count exams as available if they have reached their scheduled start time
        total_exams_available = sum(1 for s in subjects_data if s['exam'] and s['is_scheduled_to_start'])
        
        # Only count completed exams for the CURRENT session and term
        exams_completed = ExamSubmission.objects.filter(
            student=student,
            exam__session=current_session,
            exam__term=current_term,
            status__in=[
                ExamSubmission.SubmissionStatus.SUBMITTED,
                ExamSubmission.SubmissionStatus.AUTO_SUBMITTED
            ]
        ).count()
        
        results_published = recent_results.count()
        avg_score = ExamResult.objects.filter(
            student=student,
            exam__session=current_session,
            exam__term=current_term,
            is_published=True
        ).aggregate(Avg('total_score'))['total_score__avg'] or 0
        
        upcoming_exams = Exam.objects.filter(
            class_arms=class_arm,
            term=current_term,
            session=current_session,
            status=Exam.ExamStatus.APPROVED,
            scheduled_start_datetime__isnull=False
        ).select_related('subject').order_by('scheduled_start_datetime')[:5]
        
        # Check for submissions for these exams
        submissions = ExamSubmission.objects.filter(
            student=student,
            exam__in=upcoming_exams,
            status__in=['SUBMITTED', 'AUTO_SUBMITTED']
        ).values_list('exam_id', flat=True)
        
        # Attach submission status to each exam
        for exam in upcoming_exams:
            exam.has_submitted = exam.id in submissions
    else:
        total_exams_available = 0
        exams_completed = 0
        results_published = 0
        avg_score = 0
        upcoming_exams = Exam.objects.none()
    
    context = {
        'student': student,
        'current_session': current_session,
        'current_term': current_term,
        'class_arm': class_arm,
        'current_enrollment': current_enrollment,
        'subjects_data': subjects_data,
        'recent_results': recent_results,
        'upcoming_exams': upcoming_exams,
        'can_view_exams': can_view_exams,
        'exam_start_date': exam_config.exam_start_date if exam_config else None,
        'exam_end_date': exam_config.exam_end_date if exam_config else None,
        'is_exam_period_over': exam_config.is_exam_period_over if exam_config else False,
        # Stats
        'total_subjects': total_subjects,
        'total_exams_available': total_exams_available,
        'exams_completed': exams_completed,
        'results_published': results_published,
        'avg_score': round(avg_score, 2),
        'page_title': 'Student Dashboard'
    }
    
    return render(request, 'students/student_dashboard.html', context)


@login_required
@class_teacher_required
def my_students_list(request):
    current_session = AcademicSession.get_current()
    if not current_session:
        messages.warning(request, "No active academic session found.")
        return redirect('accounts:dashboard')
        
    class_arms = ClassArm.objects.filter(class_teacher=request.user, session=current_session)
    
    # We want ALL students who have ever been enrolled in this class during this session.
    enrollments = StudentEnrollment.objects.filter(
        class_arm__in=class_arms,
        session=current_session
    ).select_related('student', 'class_arm').order_by('class_arm__name', 'student__last_name')
    
    query = request.GET.get('q', '').strip()
    if query:
        from django.db.models import Q
        enrollments = enrollments.filter(
            Q(student__first_name__icontains=query) |
            Q(student__last_name__icontains=query) |
            Q(student__other_names__icontains=query) |
            Q(student__admission_number__icontains=query)
        )
    
    context = {
        'enrollments': enrollments,
        'class_arms': class_arms,
        'current_session': current_session,
        'query': query,
        'page_title': 'My Students'
    }
    return render(request, 'students/my_students_list.html', context)


@login_required
@class_teacher_required
def my_student_profile(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    
    # Verify the student belongs to one of the teacher's class arms for the current session
    class_arms = ClassArm.objects.filter(class_teacher=request.user, session=current_session)
    enrollment = StudentEnrollment.objects.filter(
        student=student, session=current_session, class_arm__in=class_arms
    ).first()
    
    if not enrollment:
        messages.error(request, "You are not the class teacher for this student in the current session.")
        return redirect('students:my_students_list')
        
    from results.models import ReportCard
    from examinations.models import ExamResult
    
    report_card = ReportCard.objects.filter(
        student=student, session=current_session, term=current_term
    ).first()
    
    exam_results = ExamResult.objects.filter(
        student=student, exam__session=current_session, exam__term=current_term
    ).select_related('exam__subject')
    
    context = {
        'student': student,
        'enrollment': enrollment,
        'report_card': report_card,
        'exam_results': exam_results,
        'current_term': current_term,
        'page_title': f"{student.full_name} | Profile"
    }
    return render(request, 'students/my_student_profile.html', context)

