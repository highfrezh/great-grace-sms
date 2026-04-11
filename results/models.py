
from django.db import models
from django.conf import settings
from students.models import Student
from academics.models import AcademicSession, Term, ClassArm

class ReportCard(models.Model):
    """Termly summary report for a student"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='report_cards')
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    class_arm = models.ForeignKey(ClassArm, on_delete=models.CASCADE)
    
    # Metadata
    total_score = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    average = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    position = models.PositiveIntegerField(null=True, blank=True)
    
    # Comments & Attendance
    attendance_present = models.PositiveIntegerField(default=0)
    attendance_total = models.PositiveIntegerField(default=0)
    teacher_comment = models.TextField(blank=True)
    principal_comment = models.TextField(blank=True)
    
    # Workflow
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'session', 'term']
        ordering = ['class_arm', 'student']

    def __str__(self):
        return f"Report Card — {self.student.full_name} ({self.term})"

    @property
    def get_subject_results(self):
        """Fetch all subject results for this student in this term"""
        from examinations.models import ExamResult
        return ExamResult.objects.filter(
            student=self.student,
            exam__session=self.session,
            exam__term=self.term
        ).select_related('exam__subject').order_by('exam__subject__name')

class StudentDomainRating(models.Model):
    """Ratings for Affective and Psychomotor domains"""
    
    class Category(models.TextChoices):
        AFFECTIVE = 'AFFECTIVE', 'Affective Domain'
        PSYCHOMOTOR = 'PSYCHOMOTOR', 'Psychomotor Domain'
    
    # Default attributes
    AFFECTIVE_ATTRIBUTES = [
        'Punctuality', 'Honesty', 'Neatness', 'Politeness', 'Self-Control',
        'Relationship with Others', 'Leadership'
    ]
    PSYCHOMOTOR_ATTRIBUTES = [
        'Handwriting', 'Musical Skills', 'Sports', 'Crafts', 'Creativity'
    ]
    
    report_card = models.ForeignKey(ReportCard, on_delete=models.CASCADE, related_name='domain_ratings')
    category = models.CharField(max_length=20, choices=Category.choices)
    attribute_name = models.CharField(max_length=50) # e.g. Punctuality, Handwriting
    rating = models.PositiveIntegerField(default=3, choices=[(i, str(i)) for i in range(1, 6)])

    class Meta:
        unique_together = ['report_card', 'attribute_name']

    def __str__(self):
        return f"{self.attribute_name}: {self.rating}"

class ResultAuditLog(models.Model):
    """Log of every change made to a student's score"""
    report_card = models.ForeignKey(ReportCard, on_delete=models.CASCADE, related_name='audit_logs')
    modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100) # e.g. "Updated CA1 Score"
    change_details = models.TextField() # e.g. "From 15.0 to 18.0"
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.modified_by} - {self.action} - {self.created_at}"
