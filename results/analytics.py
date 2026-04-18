from django.db.models import Avg, Count, Case, When, IntegerField, F, Q
from examinations.models import ExamResult, Exam
from results.models import ReportCard
from django.db.models.functions import Coalesce

def get_student_radar_data(student_id, session_id, term_id, class_arm_id):
    """
    Returns data for the Radar chart: Student subject scores vs Class Averages.
    Format:
    {
        'labels': ['Math', 'English', ...],
        'student_scores': [85, 72, ...],
        'class_averages': [60, 65, ...]
    }
    """
    # Check if the term is published for this student
    is_published = ReportCard.objects.filter(
        student_id=student_id,
        session_id=session_id,
        term_id=term_id,
        is_published=True
    ).exists()

    if not is_published:
        return {'labels': [], 'student_scores': [], 'class_averages': []}

    # Get student's subject results
    student_results = ExamResult.objects.filter(
        student_id=student_id,
        exam__session_id=session_id,
        exam__term_id=term_id
    ).select_related('exam__subject')

    student_scores_map = {res.exam.subject.name: float(res.total_score) for res in student_results}
    
    # Get class averages for the same subjects
    class_results = ExamResult.objects.filter(
        student__enrollments__class_arm_id=class_arm_id,
        student__enrollments__session_id=session_id,
        student__enrollments__is_active=True,
        exam__session_id=session_id,
        exam__term_id=term_id
    ).values('exam__subject__name').annotate(
        avg_score=Avg('total_score')
    )
    class_averages_map = {res['exam__subject__name']: float(res['avg_score']) for res in class_results}

    labels = []
    student_data = []
    class_data = []

    for subject, score in student_scores_map.items():
        labels.append(subject)
        student_data.append(score)
        class_data.append(round(class_averages_map.get(subject, 0), 2))

    return {
        'labels': labels,
        'student_scores': student_data,
        'class_averages': class_data
    }

def get_student_trend_data(student_id, session_id):
    """
    Returns data for Line Chart: Student average across terms in a session.
    Format:
    {
        'labels': ['1st Term', '2nd Term', '3rd Term'],
        'averages': [75.5, 80.2, 78.0]
    }
    """
    report_cards = ReportCard.objects.filter(
        student_id=student_id,
        session_id=session_id,
        is_published=True
    ).select_related('term').order_by('term__name')

    labels = []
    averages = []

    for rc in report_cards:
        labels.append(rc.term.get_name_display())
        averages.append(float(rc.average))

    return {
        'labels': labels,
        'averages': averages
    }

def get_class_insight_data(class_arm_id, session_id, term_id):
    """
    Returns data for Teacher Bar Chart and Top/Bottom Students.
    """
    # 1. Subject averages
    class_results = ExamResult.objects.filter(
        student__enrollments__class_arm_id=class_arm_id,
        student__enrollments__session_id=session_id,
        student__enrollments__is_active=True,
        exam__session_id=session_id,
        exam__term_id=term_id
    ).filter(Q(is_published=True) | Q(exam__status=Exam.ExamStatus.APPROVED)).values('exam__subject__name').annotate(
        avg_score=Avg('total_score')
    ).order_by('-avg_score')

    subject_labels = []
    subject_averages = []
    for res in class_results:
        subject_labels.append(res['exam__subject__name'])
        subject_averages.append(round(float(res['avg_score']), 2))

    # 2. Top and Bottom students
    report_cards = ReportCard.objects.filter(
        class_arm_id=class_arm_id,
        session_id=session_id,
        term_id=term_id,
        is_published=True
    ).select_related('student').order_by('-average')

    rc_list = list(report_cards)
    top_5 = [{
        'name': rc.student.get_full_name(), 
        'average': float(rc.average)
    } for rc in rc_list[:5]]
    
    bottom_5 = [{
        'name': rc.student.get_full_name(), 
        'average': float(rc.average)
    } for rc in reversed(rc_list[-5:]) if rc not in rc_list[:5]]  # avoid overlap if class is very small

    return {
        'chart': {
            'labels': subject_labels,
            'averages': subject_averages
        },
        'top_students': top_5,
        'bottom_students': bottom_5
    }

def get_school_insight_data(session_id, term_id):
    """
    Returns Doughnut chart Data (Pass/Fail) based on >= 50%
    """
    pass_benchmark = 50.0
    
    stats = ReportCard.objects.filter(
        session_id=session_id,
        term_id=term_id,
        is_published=True
    ).aggregate(
        passed=Count(Case(When(average__gte=pass_benchmark, then=1), output_field=IntegerField())),
        failed=Count(Case(When(average__lt=pass_benchmark, then=1), output_field=IntegerField()))
    )
    
    return {
        'labels': ['Passed (>=50%)', 'Failed (<50%)'],
        'data': [stats['passed'], stats['failed']]
    }
