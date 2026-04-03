from django.db import models

# Create your models here.
from django.db import models
from django.conf import settings
from academics.models import ClassArm, AcademicSession, Term, Subject
from students.models import Student


class Exam(models.Model):

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PENDING_VETTING = 'PENDING_VETTING', 'Pending Vetting'
        VETTED = 'VETTED', 'Vetted'
        APPROVED = 'APPROVED', 'Approved'
        ACTIVE = 'ACTIVE', 'Active'
        CLOSED = 'CLOSED', 'Closed'

    class ExamType(models.TextChoices):
        CA1 = 'CA1', 'First Continuous Assessment'
        CA2 = 'CA2', 'Second Continuous Assessment'
        EXAM = 'EXAM', 'End of Term Examination'

    # ── Core Info ─────────────────────────────────────
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='exams'
    )
    class_arm = models.ForeignKey(
        ClassArm,
        on_delete=models.CASCADE,
        related_name='exams'
    )
    session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name='exams'
    )
    term = models.ForeignKey(
        Term,
        on_delete=models.CASCADE,
        related_name='exams'
    )
    exam_type = models.CharField(
        max_length=10,
        choices=ExamType.choices,
        default=ExamType.EXAM
    )

    # ── Marks Breakdown ───────────────────────────────
    obj_marks = models.PositiveIntegerField(
        default=30,
        help_text="Maximum marks for CBT/Objective section"
    )
    theory_marks = models.PositiveIntegerField(
        default=30,
        help_text="Maximum marks for Theory section"
    )
    ca1_marks = models.PositiveIntegerField(
        default=20,
        help_text="Maximum marks for CA1"
    )
    ca2_marks = models.PositiveIntegerField(
        default=20,
        help_text="Maximum marks for CA2"
    )

    # ── CBT Settings ──────────────────────────────────
    duration_minutes = models.PositiveIntegerField(
        default=30,
        help_text="CBT exam duration in minutes"
    )
    randomize_questions = models.BooleanField(default=True)
    show_result_immediately = models.BooleanField(default=False)

    # ── Deadline & Penalty ────────────────────────────
    submission_deadline = models.DateTimeField(
        null=True, blank=True,
        help_text="Deadline for teacher to submit/activate this exam"
    )
    deadline_penalty_logged = models.BooleanField(default=False)

    # ── Status & Workflow ─────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )

    # ── People ────────────────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='exams_created'
    )
    vetted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='exams_vetted'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='exams_approved'
    )
    vetted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    vetting_comment = models.TextField(blank=True)

    # ── Timestamps ────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['subject', 'class_arm', 'session', 'term', 'exam_type']

    def __str__(self):
        return f"{self.title} — {self.class_arm} ({self.session})"

    @property
    def total_marks(self):
        return self.obj_marks + self.theory_marks + self.ca1_marks + self.ca2_marks

    @property
    def question_count(self):
        return self.questions.count()

    @property
    def theory_question_count(self):
        return self.theory_questions.count()

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def is_submittable(self):
        return self.status == self.Status.DRAFT

    @property
    def can_be_vetted(self):
        return self.status == self.Status.PENDING_VETTING

    @property
    def can_be_approved(self):
        return self.status == self.Status.VETTED

    @property
    def can_be_activated(self):
        return self.status == self.Status.APPROVED


class Question(models.Model):
    """CBT Objective Questions"""

    class Difficulty(models.TextChoices):
        EASY = 'EASY', 'Easy'
        MEDIUM = 'MEDIUM', 'Medium'
        HARD = 'HARD', 'Hard'

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    
    # ── English Version ───────────────────────────────
    text = models.TextField(
        help_text="Question text. Use LaTeX for math: $x^2 + y^2$"
    )
    image = models.ImageField(
        upload_to='exam_questions/',
        null=True, blank=True
    )
    option_a = models.TextField()
    option_b = models.TextField()
    option_c = models.TextField()
    option_d = models.TextField()
    
    # ── Yoruba Translation ────────────────────────────
    text_yoruba = models.TextField(
        blank=True,
        help_text="Yoruba translation of question (optional)"
    )
    option_a_yoruba = models.TextField(
        blank=True,
        help_text="Yoruba translation of option A"
    )
    option_b_yoruba = models.TextField(
        blank=True,
        help_text="Yoruba translation of option B"
    )
    option_c_yoruba = models.TextField(
        blank=True,
        help_text="Yoruba translation of option C"
    )
    option_d_yoruba = models.TextField(
        blank=True,
        help_text="Yoruba translation of option D"
    )
    
    # ── Metadata ───────────────────────────────────
    correct_answer = models.CharField(
        max_length=1,
        choices=[('A','A'),('B','B'),('C','C'),('D','D')]
    )
    difficulty = models.CharField(
        max_length=10,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM
    )
    marks = models.PositiveIntegerField(
        default=1,
        help_text="Marks for this question"
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"Q{self.order}: {self.text[:50]}..."


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


class StudentAnswer(models.Model):
    """Student's answer to each CBT question"""

    submission = models.ForeignKey(
        ExamSubmission,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    question = models.ForeignKey(
        Question,
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
                self.selected_option == self.question.correct_answer
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
    exam_vetting_deadline = models.DateTimeField(
        help_text="Deadline for examiner to vet exam questions"
    )
    exam_approval_deadline = models.DateTimeField(
        help_text="Deadline for admin to approve exam"
    )
    
    # ── CBT Settings ───────────────────────────────────
    default_exam_duration_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Default duration for exam in minutes"
    )
    randomize_questions_by_default = models.BooleanField(
        default=True,
        help_text="Randomize question order for students by default"
    )
    show_results_immediately = models.BooleanField(
        default=False,
        help_text="Show exam results immediately after submission"
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
    def is_vetting_deadline_passed(self):
        from django.utils import timezone
        return timezone.now() > self.exam_vetting_deadline
    
    @property
    def is_approval_deadline_passed(self):
        from django.utils import timezone
        return timezone.now() > self.exam_approval_deadline