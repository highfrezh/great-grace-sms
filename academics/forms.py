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
    class_arms = forms.ModelMultipleChoiceField(
        queryset=ClassArm.objects.all().select_related('level').order_by('level__order', 'name'),
        widget=forms.SelectMultiple(attrs={'class': 'form-input', 'size': 8}),
        required=True,
        label="Classes",
        help_text="Hold Ctrl/Cmd to select multiple classes"
    )

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
        # Pre-populate class_arms field when editing
        if self.instance and self.instance.pk:
            # Get all ClassArmSubject entries for this subject
            class_arms = ClassArmSubject.objects.filter(
                subject=self.instance
            ).values_list('class_arm_id', flat=True)
            self.fields['class_arms'].initial = list(class_arms)

    def save(self, commit=True):
        instance = super().save(commit=commit)
        
        if commit:
            # Get selected class arms
            class_arms = self.cleaned_data.get('class_arms', [])
            
            # Clear existing ClassArmSubject entries for this subject
            ClassArmSubject.objects.filter(subject=instance).delete()
            
            # Create ClassArmSubject entries for all selected class arms
            for class_arm in class_arms:
                ClassArmSubject.objects.create(
                    subject=instance,
                    class_arm=class_arm,
                    is_compulsory=True
                )
        
        return instance


class SubjectTeacherAssignmentForm(forms.ModelForm):
    class Meta:
        model = SubjectTeacherAssignment
        fields = ['class_arm', 'subject', 'teacher']
        widgets = {
            'class_arm': forms.Select(attrs={'class': 'form-input'}),
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
        
        # Filter out subjects already assigned to this teacher for current session/term
        self._filter_available_subjects()

    def _filter_available_subjects(self):
        """Filter subjects based on class arm, excluding already assigned subjects"""
        # Get cleaned data if form was submitted, otherwise use initial data or instance
        class_arm = self.data.get('class_arm')
        
        # If not submitted, try to get from initial or instance
        if not class_arm:
            class_arm = self.initial.get('class_arm') or (self.instance.class_arm_id if self.instance and self.instance.pk else None)
        
        if not class_arm:
            # No class_arm selected yet - show empty dropdown
            self.fields['subject'].queryset = Subject.objects.none()
            self.fields['subject'].empty_label = "Select Class first"
            return
        
        # Get the class arm instance
        try:
            class_arm_instance = ClassArm.objects.get(pk=class_arm)
        except (ClassArm.DoesNotExist, ValueError, TypeError):
            self.fields['subject'].queryset = Subject.objects.none()
            self.fields['subject'].empty_label = "Invalid class selected"
            return
        
        # Get subjects available for this class arm (via ClassArmSubject relationship)
        available_subjects_for_arm = ClassArmSubject.objects.filter(
            class_arm=class_arm_instance
        ).values_list('subject_id', flat=True)
        
        # Get ALREADY ASSIGNED subjects to ANY teacher in this class (not just current teacher)
        current_session = AcademicSession.get_current()
        current_term = Term.get_current()
        
        if current_session and current_term:
            assigned_subject_ids = SubjectTeacherAssignment.objects.filter(
                class_arm_id=class_arm,
                session=current_session,
                term=current_term
            ).values_list('subject_id', flat=True)
            
            # If editing an existing assignment, include the current subject in available options
            if self.instance and self.instance.pk:
                assigned_subject_ids = [sid for sid in assigned_subject_ids if sid != self.instance.subject_id]
        else:
            assigned_subject_ids = []
        
        # Show only subjects that are:
        # 1. Available for this class arm
        # 2. Not already assigned to ANY teacher in this class
        # 3. Active
        self.fields['subject'].queryset = Subject.objects.filter(
            id__in=available_subjects_for_arm,
            is_active=True
        ).exclude(
            id__in=assigned_subject_ids
        ).order_by('name')

    def clean(self):
        """Validate that subject isn't already assigned to another teacher in this class"""
        cleaned_data = super().clean()
        subject = cleaned_data.get('subject')
        class_arm = cleaned_data.get('class_arm')
        
        if subject and class_arm:
            current_session = AcademicSession.get_current()
            current_term = Term.get_current()
            
            if current_session and current_term:
                # Check if this subject is already assigned to another teacher in this class
                existing_assignment = SubjectTeacherAssignment.objects.filter(
                    subject=subject,
                    class_arm=class_arm,
                    session=current_session,
                    term=current_term
                )
                
                # If editing, exclude the current assignment
                if self.instance and self.instance.pk:
                    existing_assignment = existing_assignment.exclude(pk=self.instance.pk)
                
                if existing_assignment.exists():
                    other_teacher = existing_assignment.first().teacher.get_full_name() or existing_assignment.first().teacher.username
                    raise forms.ValidationError(
                        f"This subject is already assigned to {other_teacher} in this class for this session/term."
                    )
        
        return cleaned_data

    def save(self, commit=True):
        """Auto-set session and term to current values"""
        instance = super().save(commit=False)
        instance.session = AcademicSession.get_current()
        instance.term = Term.get_current()
        if commit:
            instance.save()
        return instance


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
    class_arm = forms.ModelChoiceField(
        queryset=ClassArm.objects.none(),
        required=False,
        empty_label="All Classes",
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Fetch class arms for the current session to populate the dropdown
        current_session = AcademicSession.get_current()
        if current_session:
            self.fields['class_arm'].queryset = ClassArm.objects.filter(
                session=current_session
            ).select_related('level').order_by('level__order', 'name')