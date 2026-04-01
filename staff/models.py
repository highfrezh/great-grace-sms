from django.db import models
from django.conf import settings


class StaffProfile(models.Model):

    class Gender(models.TextChoices):
        MALE = 'MALE', 'Male'
        FEMALE = 'FEMALE', 'Female'

    class MaritalStatus(models.TextChoices):
        SINGLE = 'SINGLE', 'Single'
        MARRIED = 'MARRIED', 'Married'
        DIVORCED = 'DIVORCED', 'Divorced'
        WIDOWED = 'WIDOWED', 'Widowed'

    class QualificationLevel(models.TextChoices):
        SSCE = 'SSCE', 'SSCE / WAEC'
        OND = 'OND', 'OND'
        HND = 'HND', 'HND'
        BSC = 'BSC', 'B.Sc / B.Ed / BA'
        PGD = 'PGD', 'PGD'
        MSC = 'MSC', 'M.Sc / M.Ed / MA'
        PHD = 'PHD', 'Ph.D'
        NCE = 'NCE', 'NCE'

    class EmploymentType(models.TextChoices):
        FULL_TIME = 'FULL_TIME', 'Full Time'
        PART_TIME = 'PART_TIME', 'Part Time'
        CONTRACT = 'CONTRACT', 'Contract'
        VOLUNTEER = 'VOLUNTEER', 'Volunteer'

    # ── Core link to User ─────────────────────────────────
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='staff_profile'
    )

    # ── Auto-generated Staff ID ───────────────────────────
    staff_id = models.CharField(max_length=20, unique=True, blank=True)

    # ── Personal Details ──────────────────────────────────
    gender = models.CharField(max_length=10, choices=Gender.choices)
    date_of_birth = models.DateField(null=True, blank=True)
    marital_status = models.CharField(
        max_length=10,
        choices=MaritalStatus.choices,
        blank=True
    )
    address = models.TextField(blank=True)
    state_of_origin = models.CharField(max_length=50, blank=True)
    religion = models.CharField(max_length=50, blank=True)

    # ── Profile Picture ───────────────────────────────────
    profile_picture = models.ImageField(
        upload_to='staff/profile_pics/',
        null=True,
        blank=True
    )

    # ── Employment Details ────────────────────────────────
    employment_date = models.DateField(null=True, blank=True)
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME
    )
    is_active = models.BooleanField(default=True)
    date_left = models.DateField(null=True, blank=True)

    # ── Qualifications ────────────────────────────────────
    highest_qualification = models.CharField(
        max_length=10,
        choices=QualificationLevel.choices,
        blank=True
    )
    qualification_subject = models.CharField(
        max_length=100,
        blank=True,
        help_text="e.g. B.Sc Mathematics"
    )
    institution = models.CharField(
        max_length=200,
        blank=True,
        help_text="Institution where highest qualification was obtained"
    )
    year_obtained = models.PositiveIntegerField(null=True, blank=True)
    teaching_certificate = models.CharField(
        max_length=100,
        blank=True,
        help_text="e.g. PGDE, NCE"
    )

    # ── Next of Kin ───────────────────────────────────────
    next_of_kin_name = models.CharField(max_length=100, blank=True)
    next_of_kin_relationship = models.CharField(max_length=50, blank=True)
    next_of_kin_phone = models.CharField(max_length=15, blank=True)
    next_of_kin_address = models.TextField(blank=True)

    # ── Bank Details ──────────────────────────────────────
    bank_name = models.CharField(max_length=100, blank=True)
    account_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=20, blank=True)

    # ── Timestamps ────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.staff_id}"

    def save(self, *args, **kwargs):
        # Auto-generate staff ID if not set
        if not self.staff_id:
            last = StaffProfile.objects.order_by('id').last()
            if last and last.staff_id:
                try:
                    num = int(last.staff_id.replace('GGS/', '')) + 1
                except ValueError:
                    num = 1
            else:
                num = 1
            self.staff_id = f"GGS/{num:04d}"
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return self.user.get_full_name()

    @property
    def primary_role(self):
        return self.user.primary_role