from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Avg
from accounts.decorators import admin_staff_required
from academics.models import AcademicSession, ClassArm, ClassLevel
from students.models import Student, StudentEnrollment
from results.models import ReportCard
from .models import PromotionHistory
import decimal

@login_required
@admin_staff_required
def promotion_dashboard(request):
    """View to select source class and target session for promotion"""
    sessions = AcademicSession.objects.all().order_by('-start_date')
    current_session = AcademicSession.get_current()
    
    # Find potential next session
    next_session = None
    if current_session:
        next_session = AcademicSession.objects.filter(
            start_date__gt=current_session.start_date
        ).order_by('start_date').first()
    
    if request.method == 'POST':
        source_class_id = request.POST.get('source_class')
        target_session_id = request.POST.get('target_session')
        
        if source_class_id and target_session_id:
            return redirect('promotions:promotion_worksheet', 
                            class_arm_id=source_class_id, 
                            target_session_id=target_session_id)

    class_arms = []
    if current_session:
        class_arms = ClassArm.objects.filter(
            session=current_session
        ).select_related('level').order_by('level__order', 'name')
    
    return render(request, 'promotions/dashboard.html', {
        'sessions': sessions,
        'current_session': current_session,
        'next_session': next_session,
        'class_arms': class_arms,
        'page_title': 'Student Promotions'
    })

@login_required
@admin_staff_required
def promotion_worksheet(request, class_arm_id, target_session_id):
    """Detailed view to decide on student promotions for a specific class"""
    source_class = get_object_or_404(ClassArm, id=class_arm_id)
    target_session = get_object_or_404(AcademicSession, id=target_session_id)
    
    enrollments = StudentEnrollment.objects.filter(
        class_arm=source_class,
        is_active=True
    ).select_related('student__user').order_by('student__user__last_name')
    
    worksheet_data = []
    
    # Fetch target session classes for dropdowns
    target_classes = ClassArm.objects.filter(
        session=target_session
    ).select_related('level').order_by('level__order', 'name')
    
    # Possible next level
    next_level = source_class.level.next_class
    
    for enroll in enrollments:
        student = enroll.student
        
        # Calculate Sessional Average
        report_cards = ReportCard.objects.filter(
            student=student,
            session=source_class.session
        )
        
        term_averages = [rc.average for rc in report_cards if rc.average is not None]
        sessional_avg = sum(term_averages) / len(term_averages) if term_averages else 0
        
        # Proposed Action
        # PASS_MARK = 50.0 (Hardcoded for now as suggestion)
        status = PromotionHistory.Status.PROMOTED if sessional_avg >= 50 else PromotionHistory.Status.REPEATED
        
        # If terminal class and passed, suggest GRADUATED
        if source_class.level.is_terminal and status == PromotionHistory.Status.PROMOTED:
            status = PromotionHistory.Status.GRADUATED

        # Proposed Target Class Arm
        suggested_class = None
        if status == PromotionHistory.Status.PROMOTED and next_level:
            # Try to find the same arm name in the next level
            suggested_class = target_classes.filter(level=next_level, name=source_class.name).first()
            if not suggested_class:
                suggested_class = target_classes.filter(level=next_level).first()
        elif status == PromotionHistory.Status.REPEATED:
            # Suggest the same level in the target session
            suggested_class = target_classes.filter(level=source_class.level, name=source_class.name).first()

        worksheet_data.append({
            'enrollment': enroll,
            'student': student,
            'sessional_avg': round(sessional_avg, 2),
            'proposed_status': status,
            'suggested_class': suggested_class,
            'results_count': len(term_averages)
        })
        
    return render(request, 'promotions/worksheet.html', {
        'source_class': source_class,
        'target_session': target_session,
        'worksheet_data': worksheet_data,
        'target_classes': target_classes,
        'next_level': next_level,
        'page_title': f"Promotion Worksheet: {source_class.full_name}"
    })

@login_required
@admin_staff_required
@transaction.atomic
def process_bulk_promotion(request):
    """Handle the POST request to execute promotions"""
    if request.method != 'POST':
        return redirect('promotions:promotion_dashboard')
        
    source_class_id = request.POST.get('source_class_id')
    target_session_id = request.POST.get('target_session_id')
    
    source_class = get_object_or_404(ClassArm, id=source_class_id)
    target_session = get_object_or_404(AcademicSession, id=target_session_id)
    
    # 1. Check if target session has terms before starting (Avoid IntegrityError)
    from academics.models import Term
    first_term = Term.objects.filter(session=target_session, name=Term.TermName.FIRST).first()
    if not first_term:
        first_term = Term.objects.filter(session=target_session).order_by('id').first()
        
    if not first_term:
        messages.error(
            request, 
            f"Cannot process promotion: The target session '{target_session.name}' has no terms defined. "
            "Please create at least one term for this session first."
        )
        return redirect('promotions:promotion_worksheet', 
                        class_arm_id=source_class_id, 
                        target_session_id=target_session_id)
    
    student_ids = request.POST.getlist('student_ids')
    
    # 2. Pre-validate: Ensure all PROMOTED/REPEATED students have a target class (Avoid data loss/orphaning)
    missing_class_students = []
    for student_id in student_ids:
        decision = request.POST.get(f'decision_{student_id}')
        target_class_id = request.POST.get(f'target_class_{student_id}')
        
        if decision in [PromotionHistory.Status.PROMOTED, PromotionHistory.Status.PROMOTED_TRIAL, PromotionHistory.Status.REPEATED]:
            if not target_class_id:
                student = Student.objects.filter(id=student_id).first()
                if student:
                    missing_class_students.append(student.full_name)
    
    if missing_class_students:
        names_str = ", ".join(missing_class_students)
        messages.error(
            request, 
            f"Cannot process promotion: The following students are marked for promotion or repeat but have no target class assigned: {names_str}. "
            "Please assign a class arm for every student staying in the school."
        )
        return redirect('promotions:promotion_worksheet', 
                        class_arm_id=source_class_id, 
                        target_session_id=target_session_id)
    
    count_success = 0
    
    for student_id in student_ids:
        decision = request.POST.get(f'decision_{student_id}')
        target_class_id = request.POST.get(f'target_class_{student_id}')
        avg_score = request.POST.get(f'avg_{student_id}', 0)
        
        student = get_object_or_404(Student, id=student_id)
        
        # 3. Create Promotion Record
        target_class = None
        if target_class_id:
            target_class = ClassArm.objects.filter(id=target_class_id).first()
            
        PromotionHistory.objects.create(
            student=student,
            from_session=source_class.session,
            to_session=target_session,
            from_class=source_class,
            to_class=target_class,
            avg_score=decimal.Decimal(avg_score),
            status=decision,
            created_by=request.user
        )
        
        # 3. Handle Enrollment Updates
        # Deactivate old enrollment
        StudentEnrollment.objects.filter(
            student=student, 
            session=source_class.session,
            is_active=True
        ).update(is_active=False)
        
        # Create new enrollment if Promoted or Repeated
        if decision in [PromotionHistory.Status.PROMOTED, PromotionHistory.Status.PROMOTED_TRIAL, PromotionHistory.Status.REPEATED]:
            if target_class:
                StudentEnrollment.objects.create(
                    student=student,
                    class_arm=target_class,
                    session=target_session,
                    term=first_term,
                    is_active=True
                )
                count_success += 1
        else:
            # Graduated or Withdrawn students don't get new enrollments
            count_success += 1

    messages.success(request, f"Successfully processed promotion for {count_success} students.")
    return redirect('promotions:promotion_dashboard')
