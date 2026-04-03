from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.core.paginator import Paginator
from accounts.decorators import admin_staff_required, class_teacher_required
from academics.models import AcademicSession, Term, ClassArm
from accounts.models import User
from staff.models import StaffProfile
from .models import Student, Guardian, StudentEnrollment, Attendance
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
            Q(email__icontains=search_query)
        )

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
    student_form = StudentForm(request.POST or None)
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
def student_edit(request, pk):
    """Edit student information"""
    student = get_object_or_404(Student, pk=pk)
    
    student_form = StudentForm(request.POST or None, instance=student)
    
    if request.method == 'POST':
        if student_form.is_valid():
            student_form.save()
            messages.success(request, f'{student.full_name} updated successfully.')
            return redirect('students:student_detail', pk=student.pk)
        else:
            messages.error(request, 'Please fix the errors below.')
    
    return render(request, 'students/student_form.html', {
        'student_form': student_form,
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
        email=student.email or f'{username}@greatgrace.edu',
        first_name=student.first_name,
        last_name=student.last_name,
        password=password,
        phone_number=student.phone or '00000000000',
        is_first_login=True
    )
    
    # Assign student role
    student_role, _ = Role.objects.get_or_create(name='STUDENT')
    user.roles.add(student_role)
    
    # Link to student profile
    student.user = user
    student.save()
    
    return user


def create_guardian_user(guardian):
    """Auto-create guardian user account for parent portal"""
    from accounts.models import Role
    
    # Generate username from phone number
    base_username = f"parent{guardian.phone[-6:]}"  # Last 6 digits of phone
    username = base_username
    password = guardian.phone  # Default password is phone number
    
    # Handle duplicate usernames
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
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
    
    # Link to guardian profile
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
                        # Generate admission number
                        current_year = session.start_date.year % 100 if session else datetime.now().year % 100
                        count = Student.objects.filter(admission_number__startswith=f"{current_year}/").count() + 1 + created_count
                        admission_number = f"{current_year}/{count:04d}"
                        
                        # Create student
                        student = Student.objects.create(
                            first_name=str(row.get('first_name', '')).strip(),
                            last_name=str(row.get('last_name', '')).strip(),
                            other_names=str(row.get('other_names', '')).strip() if pd.notna(row.get('other_names')) else '',
                            admission_number=admission_number,
                            date_of_birth=pd.to_datetime(row.get('date_of_birth')).date() if pd.notna(row.get('date_of_birth')) else None,
                            gender=str(row.get('gender', '')).upper()[:1] if pd.notna(row.get('gender')) else 'M',
                            phone=str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else '',
                            email=str(row.get('email', '')).strip().lower() if pd.notna(row.get('email')) else '',
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
    from datetime import date as date_obj
    from django.utils import timezone

    current_session = AcademicSession.get_current()
    current_term = Term.get_current()
    today = date_obj.today()

    # Get class arm from URL pk or find by teacher
    if pk:
        class_arm = get_object_or_404(
            ClassArm,
            pk=pk,
            class_teacher=request.user
        )
    else:
        class_arm = ClassArm.objects.filter(
            class_teacher=request.user,
            session=current_session
        ).first()

    if not class_arm:
        messages.error(request, 'You are not assigned to any class.')
        return redirect('accounts:dashboard')

    students = Student.objects.filter(
        is_active=True,
        enrollments__class_arm=class_arm,
        enrollments__session=current_session,
        enrollments__term=current_term,
        enrollments__is_active=True
    ).order_by('last_name', 'first_name').distinct()

    if request.method == 'POST':
        attendance_date_str = request.POST.get(
            'attendance_date', today.strftime('%Y-%m-%d')
        )
        try:
            from datetime import datetime
            attendance_date = datetime.strptime(
                attendance_date_str, '%Y-%m-%d'
            ).date()
        except ValueError:
            attendance_date = today

        for student in students:
            status = request.POST.get(f'status_{student.id}', 'PRESENT')
            remarks = request.POST.get(f'remarks_{student.id}', '')

            Attendance.objects.update_or_create(
                student=student,
                date=attendance_date,
                defaults={
                    'class_arm': class_arm,
                    'session': current_session,
                    'term': current_term,
                    'status': status,
                    'remarks': remarks,
                    'marked_by': request.user,
                }
            )

        messages.success(
            request,
            f'Attendance marked for {attendance_date.strftime("%d %B %Y")}'
        )
        return redirect('students:attendance_mark', pk=class_arm.pk)

    existing_attendance = {
        a.student_id: a
        for a in Attendance.objects.filter(
            class_arm=class_arm,
            session=current_session,
            term=current_term,
            date=today
        )
    }

    return render(request, 'students/attendance_mark.html', {
        'class_arm': class_arm,
        'students': students,
        'today': today,
        'existing_attendance': existing_attendance,
        'current_session': current_session,
        'current_term': current_term,
        'page_title': f'Mark Attendance — {class_arm.full_name}',
    })
