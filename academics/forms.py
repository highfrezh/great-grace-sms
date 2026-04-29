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
        # Only show active staff in class teacher dropdown
        self.fields['class_teacher'].queryset = User.objects.filter(
            is_active=True,
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
        level = cleaned_data.get('level')
        name = cleaned_data.get('name', '')
        session = cleaned_data.get('session')
        
        if level and session:
            # Check for uniqueness manually to prevent IntegrityError
            qs = ClassArm.objects.filter(level=level, name=name, session=session)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
                
            if qs.exists():
                raise forms.ValidationError(
                    "A class with this Level, Name, and Session already exists."
                )
                
        return cleaned_data


class SubjectForm(forms.ModelForm):
    class_arms = forms.ModelMultipleChoiceField(
        queryset=ClassArm.objects.none(),
        widget=forms.SelectMultiple(attrs={
            'class': 'form-input',
            'style': 'height: 120px;'  # Set a taller height for the multiselect
        }),
        required=False,
        label="Offered in Classes",
        help_text="Hold 'Ctrl' (Windows) or 'Command' (Mac) to select multiple classes."
    )
    
    class Meta:
        model = Subject
        fields = ['name', 'class_arms', 'description', 'is_active']
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
        # Fetch current session to show relevant classes
        current_session = AcademicSession.get_current()
        if current_session:
            self.fields['class_arms'].queryset = ClassArm.objects.filter(
                session=current_session
            ).select_related('level').order_by('level__order', 'name')
        
        # If editing, pre-populate class_arms based on existing ClassArmSubject records
        if self.instance and self.instance.pk:
            # We find ClassArms in the current session that match the (Level, ArmName) of ClassArmSubject
            offerings = ClassArmSubject.objects.filter(subject=self.instance)
            initial_ids = []
            for offering in offerings:
                matching_arms = ClassArm.objects.filter(
                    session=current_session,
                    level=offering.class_level,
                    name=offering.arm_name
                ).values_list('id', flat=True)
                initial_ids.extend(list(matching_arms))
            
            self.initial['class_arms'] = initial_ids

    def save(self, commit=True):
        subject = super().save(commit=commit)
        if commit:
            selected_arms = self.cleaned_data.get('class_arms')
            
            # Map selected arms to their (Level, ArmName) pairs
            selected_mappings = set()
            for arm in selected_arms:
                selected_mappings.add((arm.level.id, arm.name))
            
            # Current mappings for this subject
            existing_offerings = ClassArmSubject.objects.filter(subject=subject)
            existing_mappings = { (o.class_level_id, o.arm_name) for o in existing_offerings }
            
            # 1. Add new mappings
            to_add = selected_mappings - existing_mappings
            for level_id, arm_name in to_add:
                ClassArmSubject.objects.create(
                    subject=subject,
                    class_level_id=level_id,
                    arm_name=arm_name
                )
            
            # 2. Remove deselected mappings
            # Note: We only remove mappings that the user could have seen (i.e. those with matching arms in current session)
            # Fetch all arms in current session to know what the user could have unchecked
            current_session = AcademicSession.get_current()
            if current_session:
                visible_arms = ClassArm.objects.filter(session=current_session)
                visible_mappings = { (a.level_id, a.name) for a in visible_arms }
                
                to_remove = (existing_mappings & visible_mappings) - selected_mappings
                
                if to_remove:
                    for level_id, arm_name in to_remove:
                        ClassArmSubject.objects.filter(
                            subject=subject,
                            class_level_id=level_id,
                            arm_name=arm_name
                        ).delete()
        
        return subject


class SubjectTeacherAssignmentForm(forms.ModelForm):
    class_level = forms.ModelChoiceField(
        queryset=ClassLevel.objects.all(),
        required=False,
        label="Filter by Class Level",
        widget=forms.Select(attrs={'class': 'form-control', '@change': 'fetchOfferings()', 'x-model': 'levelId'}),
        help_text="Select a class level to view its offered subjects."
    )

    # Consolidate selection into a single field of Subject+Class combinations
    subject_assignments = forms.ModelMultipleChoiceField(
        queryset=ClassArmSubject.objects.none(),  # Loaded via AJAX
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'style': 'height: 300px;'
        }),
        label="Offered Subjects",
        required=True,
        help_text="Hold Ctrl (Windows) or Cmd (Mac) to select multiple subjects. Note: List only displays subjects that are yet to be assigned."
    )

    class Meta:
        model = SubjectTeacherAssignment
        fields = ['teacher', 'class_level', 'subject_assignments']
        widgets = {
            'teacher': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Custom label generator for subject_assignments
        self.fields['subject_assignments'].label_from_instance = lambda obj: \
            f"{obj.subject.name} ({obj.class_level.name} {obj.arm_name})"
            
        # Handle dynamic filtering for validation
        if 'class_level' in self.data:
            try:
                level_id = int(self.data.get('class_level'))
                self.fields['subject_assignments'].queryset = ClassArmSubject.objects.filter(
                    class_level_id=level_id
                ).select_related('subject', 'class_level').order_by('arm_name', 'subject__name')
            except (ValueError, TypeError):
                pass
        elif self.instance and self.instance.pk:
            self.fields['subject_assignments'].queryset = ClassArmSubject.objects.filter(
                class_level=self.instance.class_level
            ).select_related('subject', 'class_level').order_by('arm_name', 'subject__name')
            
        # Only show teaching staff in teacher dropdown
        self.fields['teacher'].queryset = User.objects.filter(
            roles__name__in=[
                'SUBJECT_TEACHER', 'CLASS_TEACHER',
                'VICE_PRINCIPAL', 'PRINCIPAL'
            ]
        ).distinct()
        
        # In edit mode, pre-select the current offering
        if self.instance and self.instance.pk:
            current_offering = ClassArmSubject.objects.filter(
                subject=self.instance.subject,
                class_level=self.instance.class_level,
                arm_name=self.instance.arm_name
            ).first()
            if current_offering:
                self.fields['subject_assignments'].initial = [current_offering.pk]

    def clean(self):
        cleaned_data = super().clean()
        teacher = cleaned_data.get('teacher')
        subject_assignments = cleaned_data.get('subject_assignments')
        
        if not teacher or not subject_assignments:
            return cleaned_data
            
        return cleaned_data

    def save(self, commit=True):
        # Saving logic handled in the view for bulk support
        return super().save(commit=commit)


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