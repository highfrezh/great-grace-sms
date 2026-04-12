from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from academics.models import Subject, ClassArm, Term, AcademicSession

class SchemeOfWork(models.Model):
    """
    Curriculum materials (PDF/DOCX) uploaded by VPs 
    per class arm, subject, term, and session.
    """
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='schemes')
    class_arm = models.ForeignKey(ClassArm, on_delete=models.CASCADE, related_name='schemes')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='schemes')
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='schemes')
    
    attachment = models.FileField(
        upload_to='schemes/attachments/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'docx', 'doc', 'pptx'])],
        help_text="Upload scheme material (PDF, DOCX, DOC, PPTX only)"
    )
    description = models.TextField(blank=True, help_text="Briefly describe the scheme or add notes")
    
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_schemes'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-session__start_date', 'term', 'class_arm__level__order', 'subject__name']
        unique_together = ['subject', 'class_arm', 'term', 'session']
        verbose_name = "Scheme of Work"
        verbose_name_plural = "Schemes of Work"

    def __str__(self):
        return f"{self.subject.name} - {self.class_arm} ({self.term})"
