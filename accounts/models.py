from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    class Role(models.TextChoices):
        PRINCIPAL = 'PRINCIPAL', 'Principal'
        VICE_PRINCIPAL = 'VICE_PRINCIPAL', 'Vice Principal'
        CLASS_TEACHER = 'CLASS_TEACHER', 'Class Teacher'
        SUBJECT_TEACHER = 'SUBJECT_TEACHER', 'Subject Teacher'
        STUDENT = 'STUDENT', 'Student'
        PARENT = 'PARENT', 'Parent'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        null=True,
        blank=True
    )
    phone_number = models.CharField(max_length=15, blank=True)
    profile_picture = models.ImageField(
        upload_to='profile_pics/',
        null=True,
        blank=True
    )
    is_first_login = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"

    # Role helper properties
    @property
    def is_principal(self):
        return self.role == self.Role.PRINCIPAL

    @property
    def is_vice_principal(self):
        return self.role == self.Role.VICE_PRINCIPAL

    @property
    def is_class_teacher(self):
        return self.role == self.Role.CLASS_TEACHER

    @property
    def is_subject_teacher(self):
        return self.role == self.Role.SUBJECT_TEACHER

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_parent(self):
        return self.role == self.Role.PARENT

    @property
    def is_admin_staff(self):
        return self.role in [self.Role.PRINCIPAL, self.Role.VICE_PRINCIPAL]