from django.db import models
from django.conf import settings
from academics.models import ClassArm, AcademicSession, Term


def generate_admission_number():
    """Generate unique admission number: GG/YYYY/XXXXX"""
    year = AcademicSession.get_current()
    year_str = year.name.split('/')[0] if year else '2024'
    
    prefix = f"GG/{year_str}/"
    last_student = Student.objects.filter(
        admission_number__startswith=prefix
    ).order_by('-admission_number').first()
    
    if last_student:
        last_num = int(last_student.admission_number.split('/')[-1])
        new_num = last_num + 1
    else:
        new_num = 1
    
    return f"{prefix}{new_num:05d}"


class Student(models.Model):
    class Gender(models.TextChoices):
        MALE = 'M', 'Male'
        FEMALE = 'F', 'Female'
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='student_profile'
    )
    
    admission_number = models.CharField(
        max_length=20,
        unique=True,
        default=generate_admission_number,
        help_text="Auto-generated: GG/YYYY/XXXXX"
    )
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    other_names = models.CharField(max_length=50, blank=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=Gender.choices)
    
    phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    
    blood_group = models.CharField(max_length=5, blank=True)
    allergies = models.TextField(blank=True)
    medical_conditions = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=100, blank=True)
    emergency_phone = models.CharField(max_length=15, blank=True)
    
    is_active = models.BooleanField(default=True)
    date_admitted = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date_admitted', 'last_name', 'first_name']
        
    def __str__(self):
        return f"{self.admission_number} — {self.full_name}"
    
    @property
    def full_name(self):
        if self.other_names:
            return f"{self.first_name} {self.other_names} {self.last_name}"
        return f"{self.first_name} {self.last_name}"
    
    @property
    def initials(self):
        return f"{self.first_name[0]}{self.last_name[0]}".upper()
    
    def get_current_enrollment(self):
        return self.enrollments.filter(is_active=True).first()


class Guardian(models.Model):
    class Relationship(models.TextChoices):
        FATHER = 'FATHER', 'Father'
        MOTHER = 'MOTHER', 'Mother'
        GUARDIAN = 'GUARDIAN', 'Guardian'
        OTHER = 'OTHER', 'Other'
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='guardian_profile'
    )
    
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='guardians'
    )
    
    full_name = models.CharField(max_length=100)
    relationship = models.CharField(max_length=10, choices=Relationship.choices)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(default=False)
    portal_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-is_primary', 'full_name']
    
    def __str__(self):
        return f"{self.full_name} ({self.get_relationship_display()}) — {self.student.full_name}"


class StudentEnrollment(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    class_arm = models.ForeignKey(
        ClassArm,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name='student_enrollments'
    )
    term = models.ForeignKey(
        Term,
        on_delete=models.CASCADE,
        related_name='student_enrollments'
    )
    
    is_active = models.BooleanField(default=True)
    date_enrolled = models.DateField(auto_now_add=True)
    
    transferred_from = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transferred_to'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['student', 'session', 'term']
        ordering = ['-session__start_date', '-term__name', 'class_arm__level__order', 'class_arm__name']
    
    def __str__(self):
        return f"{self.student.full_name} — {self.class_arm.full_name} ({self.session.name} {self.term.get_name_display})"


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'PRESENT', 'Present'
        ABSENT = 'ABSENT', 'Absent'
        LATE = 'LATE', 'Late'
        EXCUSED = 'EXCUSED', 'Excused'
    
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    class_arm = models.ForeignKey(
        ClassArm,
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    term = models.ForeignKey(
        Term,
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PRESENT)
    remarks = models.TextField(blank=True)
    
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='attendance_marked'
    )
    marked_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['student', 'date']
        ordering = ['-date', 'student__last_name']
    
    def __str__(self):
        return f"{self.student.full_name} — {self.date} — {self.get_status_display()}"
