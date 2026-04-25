from django.db import models
from django.conf import settings
from students.models import Student
from academics.models import AcademicSession, ClassArm

class PromotionHistory(models.Model):
    """
    History of a student's movement between sessions and classes.
    """
    class Status(models.TextChoices):
        PROMOTED = 'PROMOTED', 'Promoted'
        REPEATED = 'REPEATED', 'Repeated'
        GRADUATED = 'GRADUATED', 'Graduated'

    student = models.ForeignKey(
        Student, 
        on_delete=models.CASCADE, 
        related_name='promotion_history'
    )
    from_session = models.ForeignKey(
        AcademicSession, 
        on_delete=models.CASCADE, 
        related_name='promotions_from'
    )
    to_session = models.ForeignKey(
        AcademicSession, 
        on_delete=models.CASCADE, 
        related_name='promotions_to'
    )
    from_class = models.ForeignKey(
        ClassArm, 
        on_delete=models.CASCADE, 
        related_name='promoted_from'
    )
    to_class = models.ForeignKey(
        ClassArm, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        related_name='promoted_to',
        help_text="Target class for next session. Null if graduated or withdrawn."
    )
    
    avg_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="The sessional cumulative average used for the decision."
    )
    status = models.CharField(
        max_length=20, 
        choices=Status.choices,
        default=Status.PROMOTED
    )
    
    remarks = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Promotion Histories"

    def __str__(self):
        return f"{self.student.full_name}: {self.from_session} -> {self.to_session} ({self.status})"
