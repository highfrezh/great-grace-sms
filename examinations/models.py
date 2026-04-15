from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from academics.models import ClassArm, AcademicSession, Term, Subject
from students.models import Student
from staff.models import StaffProfile


class Exam(models.Model):
    """
    The Header: Stores general exam info, theory file attachment, and metadata.
    Admin sets the exam configuration, teachers create objective questions.
    """

    # ── Core Relationships ────────────────────────────
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='exams')
    class_arms = models.ManyToManyField(
        ClassArm, 
        related_name='exams',
        help_text="Select all classes that will take this exam"
    )
    teacher = models.ForeignKey(
        StaffProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exams_teaching',
        help_text="Subject teacher assigned to create questions for this exam"
    )
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='exams')
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='exams')

    # ── Title & Duration ──────────────────────────────
    title = models.CharField(max_length=255, help_text="e.g., First Term Examination")
    duration_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Duration for the CBT (objective) section in minutes"
    )

    # ── Theory File Upload (for manual administration) ─
    theory_attachment = models.FileField(
        upload_to='exams/theory_files/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'docx', 'doc'])],
        help_text="Upload theory/written questions file for printing (PDF, DOCX, DOC only)"
    )

    randomize_questions = models.BooleanField(
        default=True,
        help_text="Shuffle question order for each student taking the exam"
    )

    show_results_immediately = models.BooleanField(
        default=True,
        help_text="Show score and detailed report to student immediately after submission"
    )

    # ── Publication & Approval Status ────────────────────────────
    class ExamStatus(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft (Editing)'
        AWAITING_APPROVAL = 'AWAITING_APPROVAL', 'Awaiting Examiner Approval'
        APPROVED = 'APPROVED', 'Approved'

    status = models.CharField(
        max_length=20,
        choices=ExamStatus.choices,
        default=ExamStatus.DRAFT,
        help_text="Exam workflow status"
    )

    # ── Approval Details ──────────────────────────────
    approved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exams_approved'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # ── Rejection Details ──────────────────────────────
    rejection_reason = models.TextField(
        null=True,
        blank=True,
        help_text="Reason why the exam was rejected by examiner"
    )
    rejected_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exams_rejected'
    )
    rejected_at = models.DateTimeField(null=True, blank=True)

    # ── Exam Scheduling ───────────────────────────────
    scheduled_start_datetime = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date and time when students can start taking this exam"
    )
    scheduled_end_datetime = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date and time when students can no longer submit exam"
    )
    scheduled_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exams_scheduled'
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)

    # ── Timestamps ────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['subject', 'teacher', 'session', 'term']

    def __str__(self):
        class_list = ', '.join(str(ca) for ca in self.class_arms.all())
        return f"{self.subject} - {class_list} ({self.term})"

    @property
    def objective_count(self):
        """Count of objective questions in this exam"""
        return self.objectives.count()

    @property
    def has_theory_file(self):
        """Check if theory file has been uploaded"""
        return bool(self.theory_attachment)

    @property
    def total_marks(self):
        """Get total marks from ExamConfiguration for this session and term"""
        from .models import ExamConfiguration
        config = ExamConfiguration.objects.filter(
            session=self.session, 
            term=self.term
        ).first()
        return config.total_marks if config else 100

    @property
    def obj_marks(self):
        """Get total marks allocated for objective questions from configuration"""
        from .models import ExamConfiguration
        config = ExamConfiguration.objects.filter(
            session=self.session, 
            term=self.term
        ).first()
        if config:
            return (config.obj_marks_percentage / 100) * config.total_marks
        return 30.0 # Default if no config

    @property
    def marks_per_objective(self):
        """Calculate marks for a single objective question"""
        count = self.objective_count
        if count > 0:
            return float(self.obj_marks) / count
        return 0.0

    @property
    def ca1_marks(self):
        """Get CA1 marks from configuration"""
        from .models import ExamConfiguration
        config = ExamConfiguration.objects.filter(session=self.session, term=self.term).first()
        return (config.ca1_marks_percentage / 100) * config.total_marks if config else 20.0

    @property
    def ca2_marks(self):
        """Get CA2 marks from configuration"""
        from .models import ExamConfiguration
        config = ExamConfiguration.objects.filter(session=self.session, term=self.term).first()
        return (config.ca2_marks_percentage / 100) * config.total_marks if config else 20.0

    @property
    def theory_marks(self):
        """Get total Theory marks from configuration"""
        from .models import ExamConfiguration
        config = ExamConfiguration.objects.filter(session=self.session, term=self.term).first()
        return (config.theory_marks_percentage / 100) * config.total_marks if config else 30.0

    # ── Workflow Methods ──────────────────────────────
    def can_edit(self):
        """Teacher can only edit if exam is in DRAFT status"""
        return self.status == self.ExamStatus.DRAFT

    def publish(self):
        """Publish exam for examiner review"""
        if self.can_edit():
            self.status = self.ExamStatus.AWAITING_APPROVAL
            self.save()
            return True
        return False

    def approve(self, user):
        """Examiner approves the exam"""
        if self.status == self.ExamStatus.AWAITING_APPROVAL:
            self.status = self.ExamStatus.APPROVED
            self.approved_by = user
            self.approved_at = timezone.now()
            # Clear rejection reason when approving
            self.rejection_reason = None
            self.rejected_by = None
            self.rejected_at = None
            self.save()
            return True
        return False

    def reject(self, user, reason):
        """Examiner rejects the exam with reason, reverts to DRAFT"""
        if self.status in [self.ExamStatus.AWAITING_APPROVAL, self.ExamStatus.APPROVED]:
            self.status = self.ExamStatus.DRAFT
            self.rejected_by = user
            self.rejected_at = timezone.now()
            self.rejection_reason = reason
            # Clear approval status if it was previously approved
            self.approved_by = None
            self.approved_at = None
            self.save()
            return True
        return False


class ObjectiveQuestion(models.Model):
    """
    The Detail: Individual multiple-choice questions for the CBT section.
    Teachers create these for their assigned exams.
    Supports Yoruba characters and Unicode via TextField.
    """

    class CorrectAnswerChoices(models.TextChoices):
        A = 'A', 'Option A'
        B = 'B', 'Option B'
        C = 'C', 'Option C'
        D = 'D', 'Option D'

    # ── Relationship ──────────────────────────────────
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='objectives'
    )

    # ── Question Content ──────────────────────────────
    question_text = models.TextField(
        help_text="Type the question here (supports Yoruba Unicode characters: ṣ, ọ, ẹ, etc.)"
    )

    question_image = models.ImageField(
        upload_to='exams/question_images/',
        null=True,
        blank=True,
        help_text="Diagram, graph, or math equation visual"
    )

    # ── Options ───────────────────────────────────────
    option_a = models.CharField(max_length=500, verbose_name="Option A")
    option_b = models.CharField(max_length=500, verbose_name="Option B")
    option_c = models.CharField(max_length=500, verbose_name="Option C")
    option_d = models.CharField(max_length=500, verbose_name="Option D")

    # ── Answer & Grading ──────────────────────────────
    correct_option = models.CharField(
        max_length=1,
        choices=CorrectAnswerChoices.choices,
        help_text="Select the correct answer for auto-grading when students take the exam"
    )

    class Meta:
        ordering = ['id']  # Keep questions in order of creation
        verbose_name = "Objective Question"
        verbose_name_plural = "Objective Questions"

    def __str__(self):
        return f"Question for {self.exam.subject}"



class TheoryQuestion(models.Model):
    """Theory/Written Questions"""

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='theory_questions'
    )
    text = models.TextField(
        help_text="Theory question text"
    )
    max_marks = models.PositiveIntegerField(
        default=10,
        help_text="Maximum marks for this question"
    )
    marking_guide = models.TextField(
        blank=True,
        help_text="Expected answer / key points for marking"
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"Theory Q{self.order}: {self.text[:50]}..."


class ExamSubmission(models.Model):
    """Tracks a student's CBT exam attempt"""

    class SubmissionStatus(models.TextChoices):
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        SUBMITTED = 'SUBMITTED', 'Submitted'
        AUTO_SUBMITTED = 'AUTO_SUBMITTED', 'Auto Submitted (Time Up)'
        ABANDONED = 'ABANDONED', 'Abandoned'

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='exam_submissions'
    )

    status = models.CharField(
        max_length=20,
        choices=SubmissionStatus.choices,
        default=SubmissionStatus.IN_PROGRESS
    )

    # ── Timing ────────────────────────────────────────
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    time_remaining_seconds = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Saved server-side for connection recovery"
    )
    last_autosave_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Last time answers were auto-saved"
    )
    last_activity_at = models.DateTimeField(
        auto_now=True,
        help_text="Last time student interacted with exam"
    )

    # ── Scores ────────────────────────────────────────
    obj_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text="Auto-calculated OBJ score"
    )

    # ── Malpractice Log ───────────────────────────────
    tab_switch_count = models.PositiveIntegerField(default=0)
    fullscreen_exit_count = models.PositiveIntegerField(default=0)
    auto_submitted_reason = models.CharField(
        max_length=100, blank=True
    )

    class Meta:
        unique_together = ['exam', 'student']
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.student.full_name} — {self.exam.title}"

    @property
    def is_complete(self):
        return self.status in [
            self.SubmissionStatus.SUBMITTED,
            self.SubmissionStatus.AUTO_SUBMITTED
        ]


class MalpracticeViolation(models.Model):
    """Log of malpractice violations during exam"""

    class ViolationType(models.TextChoices):
        TAB_SWITCH = 'TAB_SWITCH', 'Tab Switch'
        FULLSCREEN_EXIT = 'FULLSCREEN_EXIT', 'Fullscreen Exit'
        IDLE_TIMEOUT = 'IDLE_TIMEOUT', 'Idle Timeout'

    submission = models.ForeignKey(
        ExamSubmission,
        on_delete=models.CASCADE,
        related_name='violations'
    )
    violation_type = models.CharField(
        max_length=20,
        choices=ViolationType.choices
    )
    violation_count = models.PositiveIntegerField(
        default=1,
        help_text="Number of times this violation occurred"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True)

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['submission', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.submission.student} — {self.violation_type}"


class StudentAnswer(models.Model):
    """Student's answer to each CBT question"""

    submission = models.ForeignKey(
        ExamSubmission,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    question = models.ForeignKey(
        ObjectiveQuestion,
        on_delete=models.CASCADE,
        related_name='student_answers'
    )
    selected_option = models.CharField(
        max_length=1,
        choices=[('A','A'),('B','B'),('C','C'),('D','D')],
        blank=True
    )
    is_correct = models.BooleanField(default=False)
    is_flagged = models.BooleanField(
        default=False,
        help_text="Student flagged for review"
    )
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['submission', 'question']

    def save(self, *args, **kwargs):
        # Auto-check if answer is correct
        if self.selected_option:
            self.is_correct = (
                self.selected_option == self.question.correct_option
            )
        super().save(*args, **kwargs)


class TheoryScore(models.Model):
    """Teacher enters theory marks per student per question"""

    submission = models.ForeignKey(
        ExamSubmission,
        on_delete=models.CASCADE,
        related_name='theory_scores'
    )
    theory_question = models.ForeignKey(
        TheoryQuestion,
        on_delete=models.CASCADE,
        related_name='student_scores'
    )
    score = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=0
    )
    feedback = models.TextField(blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='theory_scores_entered'
    )
    marked_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['submission', 'theory_question']

    def __str__(self):
        return (
            f"{self.submission.student.full_name} — "
            f"Theory Q{self.theory_question.order}: {self.score}"
        )


class ExamResult(models.Model):
    """Final combined result per student per exam"""

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='results'
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='exam_results'
    )
    submission = models.OneToOneField(
        ExamSubmission,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='result'
    )

    # ── Score Breakdown ───────────────────────────────
    ca1_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    ca2_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    obj_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    theory_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    total_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    grade = models.CharField(max_length=2, blank=True)
    remark = models.CharField(max_length=20, blank=True)

    # ── Publishing ────────────────────────────────────
    is_published = models.BooleanField(default=False)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='results_published'
    )
    published_at = models.DateTimeField(null=True, blank=True)

    # ── Audit ─────────────────────────────────────────
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='results_modified'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['exam', 'student']
        ordering = ['-total_score']

    def __str__(self):
        return (
            f"{self.student.full_name} — "
            f"{self.exam.subject.name}: {self.total_score}"
        )

    def calculate_grade(self):
        p = float(self.percentage)
        if p >= 70: return 'A', 'Excellent'
        elif p >= 60: return 'B', 'Good'
        elif p >= 50: return 'C', 'Credit'
        elif p >= 45: return 'D', 'Pass'
        elif p >= 40: return 'E', 'Poor'
        else: return 'F', 'Fail'

    def save(self, *args, **kwargs):
        # Auto-calculate total and grade
        self.total_score = (
            self.ca1_score + self.ca2_score +
            self.obj_score + self.theory_score
        )
        if self.exam.total_marks > 0:
            self.percentage = round(
                float(self.total_score) /
                float(self.exam.total_marks) * 100, 2
            )
        self.grade, self.remark = self.calculate_grade()
        super().save(*args, **kwargs)


class ExamDeadlinePenalty(models.Model):
    """Logs penalty when teacher misses exam submission deadline"""

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='penalties'
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exam_penalties'
    )
    deadline = models.DateTimeField()
    logged_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    def __str__(self):
        return (
            f"{self.teacher.get_full_name()} — "
            f"{self.exam.title} (missed deadline)"
        )


class ExamConfiguration(models.Model):
    """
    School-wide exam configuration set by Principals.
    Defines default mark distributions and deadlines for all exams.
    """
    
    session = models.OneToOneField(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name='exam_config'
    )
    term = models.ForeignKey(
        Term,
        on_delete=models.CASCADE,
        related_name='exam_configs'
    )
    
    # ── Mark Percentages (Total must equal 100) ────────
    ca1_marks_percentage = models.PositiveIntegerField(
        default=20,
        help_text="CA1 percentage of total marks"
    )
    ca2_marks_percentage = models.PositiveIntegerField(
        default=20,
        help_text="CA2 percentage of total marks"
    )
    obj_marks_percentage = models.PositiveIntegerField(
        default=30,
        help_text="OBJ percentage of total marks"
    )
    theory_marks_percentage = models.PositiveIntegerField(
        default=30,
        help_text="Theory percentage of total marks"
    )
    
    # ── Total Marks (100 for percentage calculation) ────
    total_marks = models.PositiveIntegerField(
        default=100,
        help_text="Total marks for exam (used to calculate actual marks from percentages)"
    )
    
    # ── Deadlines ──────────────────────────────────────
    question_submission_deadline = models.DateTimeField(
        help_text="Deadline for teachers to submit exam questions"
    )
    
    # ── CBT Settings ───────────────────────────────────
    default_exam_duration_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Default duration for exam in minutes"
    )
    
    exam_start_date = models.DateTimeField(
        null=True, blank=True,
        help_text="Official start date for exams. Upcoming exams become visible on student dashboard from this date."
    )
    
    exam_end_date = models.DateTimeField(
        null=True, blank=True,
        help_text="Official end date for exams. After this date, exams are hidden from the student dashboard."
    )
    
    # ── Metadata ───────────────────────────────────────
    configured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='exam_configs_set',
        limit_choices_to={'roles__name__in': ['PRINCIPAL', 'VICE_PRINCIPAL']}
    )
    configured_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['session', 'term']
        verbose_name_plural = "Exam Configurations"
    
    def __str__(self):
        return f"Exam Config — {self.session} · {self.term}"
    
    @property
    def ca1_marks(self):
        """Calculate CA1 marks from percentage"""
        return int((self.ca1_marks_percentage / 100) * self.total_marks)
    
    @property
    def ca2_marks(self):
        """Calculate CA2 marks from percentage"""
        return int((self.ca2_marks_percentage / 100) * self.total_marks)
    
    @property
    def obj_marks(self):
        """Calculate OBJ marks from percentage"""
        return int((self.obj_marks_percentage / 100) * self.total_marks)
    
    @property
    def theory_marks(self):
        """Calculate Theory marks from percentage"""
        return int((self.theory_marks_percentage / 100) * self.total_marks)
    
    @property
    def percentages_total(self):
        """Check if percentages sum to 100"""
        return (self.ca1_marks_percentage + self.ca2_marks_percentage + 
                self.obj_marks_percentage + self.theory_marks_percentage)
    
    @property
    def is_valid_percentages(self):
        """Validate that percentages sum to 100"""
        return self.percentages_total == 100
    
    @property
    def is_question_deadline_passed(self):
        from django.utils import timezone
        return timezone.now() > self.question_submission_deadline
    
    @property
    def is_exam_period_over(self):
        """Check if exam period has officially ended"""
        if not self.exam_end_date:
            return False
        from django.utils import timezone
        return timezone.now() > self.exam_end_date