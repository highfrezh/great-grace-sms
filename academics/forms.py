from django import forms
from .models import (
    AcademicSession, Term, ClassLevel, ClassArm, Subject, 
    ClassArmSubject, SubjectTeacherAssignment
)

from django.contrib.auth import get_user_model

User = get_user_model()


class AcademicSessionForm(forms.ModelForm):
    class Meta:
        model = AcademicSession
        fields = ['name', 'start_date', 'end_date', 'is_current']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g. 2024/2025',
                'class': 'form-input'
            }),
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-input'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-input'
            }),
            'is_current': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            }),
        }


class TermForm(forms.ModelForm):
    class Meta:
        model = Term
        fields = [
            'session', 'name', 'start_date',
            'end_date', 'is_current', 'is_open', 'resumption_date'
        ]
        widgets = {
            'session': forms.Select(attrs={'class': 'form-input'}),
            'name': forms.Select(attrs={'class': 'form-input'}),
            'start_date': forms.DateInput(attrs={
                'type': 'date', 'class': 'form-input'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date', 'class': 'form-input'
            }),
            'resumption_date': forms.DateInput(attrs={
                'type': 'date', 'class': 'form-input'
            }),
            'is_current': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_open': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class ClassLevelForm(forms.ModelForm):
    class Meta:
        model = ClassLevel
        fields = ['name', 'section', 'order', 'is_terminal', 'next_class']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g. JSS 1',
                'class': 'form-input'
            }),
            'section': forms.Select(attrs={'class': 'form-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-input'}),
            'next_class': forms.Select(attrs={'class': 'form-input'}),
            'is_terminal': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class ClassArmForm(forms.ModelForm):
    class Meta:
        model = ClassArm
        fields = ['level', 'name', 'class_teacher', 'capacity', 'session']
        widgets = {
            'level': forms.Select(attrs={'class': 'form-input'}),
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g. A, B, Science, Art',
                'class': 'form-input'
            }),
            'class_teacher': forms.Select(attrs={'class': 'form-input'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-input'}),
            'session': forms.Select(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show staff in class teacher dropdown
        self.fields['class_teacher'].queryset = User.objects.filter(
            roles__name__in=[
                'SUBJECT_TEACHER', 'CLASS_TEACHER',
                'VICE_PRINCIPAL', 'PRINCIPAL', 'EXAMINER'
            ]
        ).distinct()
        self.fields['class_teacher'].required = False
        self.fields['class_teacher'].empty_label = "---------"
        # Make name field optional
        self.fields['name'].required = False

    def clean(self):
        cleaned_data = super().clean()
        class_teacher = cleaned_data.get('class_teacher')
        session = cleaned_data.get('session')
        
        if class_teacher and session:
            existing = ClassArm.objects.filter(
                class_teacher=class_teacher,
                session=session
            )
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                other_class = existing.first()
                raise forms.ValidationError(
                    f"{class_teacher.get_full_name() or class_teacher.username} is already class teacher for {other_class} in {session}."
                )
        
        return cleaned_data


class SubjectForm(forms.ModelForm):
    # We'll use a simplified approach: just manage the subject itself here.
    # The links to classes (ClassArmSubject) should be managed via a separate view or more advanced form.
    # For now, I'll remove the session-bound class_arms selection to fix the breakage.
    
    class Meta:
        model = Subject
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g. Mathematics',
                'class': 'form-input'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-input'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        return super().save(commit=commit)


class SubjectTeacherAssignmentForm(forms.ModelForm):
    class Meta:
        model = SubjectTeacherAssignment
        fields = ['class_level', 'arm_name', 'subject', 'teacher']
        widgets = {
            'class_level': forms.Select(attrs={'class': 'form-input'}),
            'arm_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. A, B, or Science'
            }),
            'subject': forms.Select(attrs={'class': 'form-input'}),
            'teacher': forms.Select(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show teaching staff in teacher dropdown
        self.fields['teacher'].queryset = User.objects.filter(
            roles__name__in=[
                'SUBJECT_TEACHER', 'CLASS_TEACHER',
                'VICE_PRINCIPAL', 'PRINCIPAL'
            ]
        ).distinct()
        
        # In a real app, we might want to filter subjects based on class_level
        # but since subjects are now globally offered or per-level+arm, 
        # we can just show all active subjects or provide a simpler filter.
        self.fields['subject'].queryset = Subject.objects.filter(is_active=True).order_by('name')

    def _filter_available_subjects(self):
        """Deprecated: Logic should move to a more session-agnostic validation if needed"""
        pass

    def clean(self):
        """Validate that subject isn't already assigned to another teacher in this class"""
        cleaned_data = super().clean()
        subject = cleaned_data.get('subject')
        class_level = cleaned_data.get('class_level')
        arm_name = cleaned_data.get('arm_name')
        
        if subject and class_level and arm_name:
            # Check if this subject is already assigned to another teacher in this class Level+Arm
            existing_assignment = SubjectTeacherAssignment.objects.filter(
                subject=subject,
                class_level=class_level,
                arm_name=arm_name
            )
            
            # If editing, exclude the current assignment
            if self.instance and self.instance.pk:
                existing_assignment = existing_assignment.exclude(pk=self.instance.pk)
            
            if existing_assignment.exists():
                teacher = existing_assignment.first().teacher
                other_teacher = teacher.get_full_name() or teacher.username
                raise forms.ValidationError(
                    f"This subject is already assigned to {other_teacher} in {class_level} {arm_name}."
                )
        
        return cleaned_data


class SubjectSearchForm(forms.Form):
    """Form for searching and filtering subjects"""
    
    STATUS_CHOICES = [
        ('', 'All Status'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    
    query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Search name or code...',
            'style': 'padding-left: 2.5rem;'
        })
    )
    class_level = forms.ModelChoiceField(
        queryset=ClassLevel.objects.all().order_by('order'),
        required=False,
        empty_label="All Levels",
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Removed session-specific filtering logic as it's no longer needed for permanent mapping