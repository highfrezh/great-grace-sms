from django.db import models
from django.conf import settings


class AcademicSession(models.Model):
    """e.g. 2024/2025"""
    name = models.CharField(max_length=20, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Only one session can be current at a time
        if self.is_current:
            AcademicSession.objects.exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_current(cls):
        return cls.objects.filter(is_current=True).first()


class Term(models.Model):
    """First, Second, Third Term"""

    class TermName(models.TextChoices):
        FIRST = 'FIRST', 'First Term'
        SECOND = 'SECOND', 'Second Term'
        THIRD = 'THIRD', 'Third Term'

    session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name='terms'
    )
    name = models.CharField(max_length=10, choices=TermName.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    is_open = models.BooleanField(default=True)
    resumption_date = models.DateField(
        null=True, blank=True,
        help_text="Next term resumption date — printed on report cards"
    )

    class Meta:
        ordering = ['session', 'name']
        unique_together = ['session', 'name']

    def __str__(self):
        return f"{self.get_name_display()} — {self.session.name}"

    def save(self, *args, **kwargs):
        # Only one term can be current at a time
        if self.is_current:
            Term.objects.exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_current(cls):
        return cls.objects.filter(is_current=True).first()


class ClassLevel(models.Model):
    """
    e.g. JSS 1, JSS 2, JSS 3, SS 1, SS 2, SS 3
    Separate from class arms/streams
    """

    class Section(models.TextChoices):
        PRIMARY = 'PRIMARY', 'Primary'
        JSS = 'JSS', 'Junior Secondary'
        SSS = 'SSS', 'Senior Secondary'

    name = models.CharField(max_length=20, unique=True)
    section = models.CharField(max_length=10, choices=Section.choices)
    order = models.PositiveIntegerField(
        default=0,
        help_text="Used for sorting and promotion ordering"
    )
    is_terminal = models.BooleanField(
        default=False,
        help_text="Mark as True for graduating classes e.g. SS3"
    )
    next_class = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='previous_class',
        help_text="Class students move to after promotion"
    )

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


class ClassArm(models.Model):
    """
    A specific class e.g. JSS 1A, JSS 1B, SS 2 Science
    This is what students are actually enrolled in
    """
    level = models.ForeignKey(
        ClassLevel,
        on_delete=models.CASCADE,
        related_name='arms'
    )
    name = models.CharField(
        max_length=10,
        help_text="e.g. A, B, Science, Art"
    )
    class_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='class_teacher_of'
    )
    capacity = models.PositiveIntegerField(default=40)
    session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name='classes'
    )

    class Meta:
        ordering = ['level__order', 'name']
        unique_together = ['level', 'name', 'session']

    def __str__(self):
        return f"{self.level.name} {self.name}"

    @property
    def full_name(self):
        return f"{self.level.name} {self.name}"

    @property
    def student_count(self):
        # Return 0 until Student/Enrollment model is implemented
        try:
            return self.enrollments.filter(is_active=True).count()
        except AttributeError:
            return 0


class Subject(models.Model):
    """Subject catalog"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, blank=True, null=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ClassArmSubject(models.Model):
    """
    Which subjects are offered in which class arm
    e.g. Mathematics in JSS1A, Biology in JSS1B
    Allows customization per class arm
    """
    # Non-nullable after migration
    class_level = models.ForeignKey(
        'ClassLevel',
        on_delete=models.CASCADE,
        related_name='arm_subjects'
    )
    arm_name = models.CharField(
        max_length=10,
        help_text="e.g. A, B, Science"
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='arm_offerings'
    )

    class Meta:
        unique_together = ['class_level', 'arm_name', 'subject']

    def __str__(self):
        return f"{self.subject.name} — {self.class_level.name} {self.arm_name}"


class ClassSubject(models.Model):
    """
    [DEPRECATED - Kept for backward compatibility]
    Which subjects are offered in which class level
    Use ClassArmSubject instead for per-arm customization
    """
    class_level = models.ForeignKey(
        ClassLevel,
        on_delete=models.CASCADE,
        related_name='level_subjects'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='class_levels'
    )
    is_compulsory = models.BooleanField(default=True)

    class Meta:
        unique_together = ['class_level', 'subject']

    def __str__(self):
        return f"{self.subject.name} — {self.class_level.name}"


class SubjectTeacherAssignment(models.Model):
    """
    Which teacher teaches which subject in which class level and arm.
    Assignments are permanent and not tied to a specific session or term.
    """
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='teaching_assignments'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='teacher_assignments'
    )
    class_level = models.ForeignKey(
        'ClassLevel',
        on_delete=models.CASCADE,
        related_name='teacher_assignments'
    )
    arm_name = models.CharField(
        max_length=10,
        help_text="e.g. A, B, Science"
    )

    class Meta:
        unique_together = ['subject', 'class_level', 'arm_name']

    def __str__(self):
        return f"{self.teacher} — {self.subject} — {self.class_level.name} {self.arm_name}"