from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.Model):
    """Roles that can be assigned to users"""

    class RoleName(models.TextChoices):
        PRINCIPAL = 'PRINCIPAL', 'Principal'
        VICE_PRINCIPAL = 'VICE_PRINCIPAL', 'Vice Principal'
        CLASS_TEACHER = 'CLASS_TEACHER', 'Class Teacher'
        SUBJECT_TEACHER = 'SUBJECT_TEACHER', 'Subject Teacher'
        EXAMINER = 'EXAMINER', 'Examiner'
        PARENT = 'PARENT', 'Parent'
        STUDENT = 'STUDENT', 'Student'

    name = models.CharField(
        max_length=20,
        choices=RoleName.choices,
        unique=True
    )

    def __str__(self):
        return self.get_name_display()


class User(AbstractUser):
    """Custom user model supporting multiple roles"""

    roles = models.ManyToManyField(
        Role,
        blank=True,
        related_name='users'
    )
    phone_number = models.CharField(max_length=15, blank=True)
    profile_picture = models.ImageField(
        upload_to='profile_pics/',
        null=True,
        blank=True
    )
    is_first_login = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.get_full_name() or self.username}"

    def get_role_display(self):
        """Return all roles as a readable string"""
        return ', '.join([role.get_name_display() for role in self.roles.all()])

    # ── Role check helpers ─────────────────────────────────
    def has_role(self, role_name):
        return self.roles.filter(name=role_name).exists()

    @property
    def is_principal(self):
        return self.has_role(Role.RoleName.PRINCIPAL)

    @property
    def is_vice_principal(self):
        return self.has_role(Role.RoleName.VICE_PRINCIPAL)

    @property
    def is_class_teacher(self):
        return self.has_role(Role.RoleName.CLASS_TEACHER)

    @property
    def is_subject_teacher(self):
        return self.has_role(Role.RoleName.SUBJECT_TEACHER)

    @property
    def is_examiner(self):
        return self.has_role(Role.RoleName.EXAMINER)

    @property
    def is_parent(self):
        return self.has_role(Role.RoleName.PARENT)

    @property
    def is_student(self):
        return self.has_role(Role.RoleName.STUDENT)

    @property
    def is_admin_staff(self):
        return self.has_role(Role.RoleName.PRINCIPAL) or \
               self.has_role(Role.RoleName.VICE_PRINCIPAL)

    @property
    def is_teaching_staff(self):
        return self.has_role(Role.RoleName.SUBJECT_TEACHER) or \
               self.has_role(Role.RoleName.CLASS_TEACHER)

    @property
    def is_exam_committee(self):
        """VP, Principal or Examiner can vet questions"""
        return self.has_role(Role.RoleName.EXAMINER) or \
               self.has_role(Role.RoleName.PRINCIPAL) or \
               self.has_role(Role.RoleName.VICE_PRINCIPAL)

    # @property
    # def primary_role(self):
    #     """Returns highest authority role for display"""
    #     priority = [
    #         Role.RoleName.PRINCIPAL,
    #         Role.RoleName.VICE_PRINCIPAL,
    #         Role.RoleName.EXAMINER,
    #         Role.RoleName.CLASS_TEACHER,
    #         Role.RoleName.SUBJECT_TEACHER,
    #         Role.RoleName.PARENT,
    #         Role.RoleName.STUDENT,
    #     ]
    #     for role_name in priority:
    #         if self.has_role(role_name):
    #             return role_name
    #     return None

    @property
    def primary_role_display(self):
        role = self.primary_role
        if role:
            return role.replace('_', ' ').title()
        return "Staff"

    @property
    def primary_role(self):
        """Always returns highest authority role"""
        if self.is_superuser:
            return 'PRINCIPAL'
        priority = [
            'PRINCIPAL',
            'VICE_PRINCIPAL',
            'EXAMINER',
            'CLASS_TEACHER',
            'SUBJECT_TEACHER',
            'PARENT',
            'STUDENT',
        ]
        for role_name in priority:
            if self.has_role(role_name):
                return role_name
        return None