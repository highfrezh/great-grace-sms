from django import forms
from django.contrib.auth import get_user_model
from academics.models import Subject, ClassArm, AcademicSession, Term
from staff.models import StaffProfile
from .models import Exam, ObjectiveQuestion, TheoryQuestion, TheoryScore, ExamResult, ExamConfiguration

User = get_user_model()


class ExamForm(forms.ModelForm):
    """Form for creating/editing exams"""
    class_arms = forms.ModelMultipleChoiceField(
        queryset=ClassArm.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-checkbox'}),
        required=True,
        label='Classes',
        help_text='Select all classes that will take this exam'
    )
    
    class Meta:
        model = Exam
        fields = [
            'title', 'subject', 'teacher', 'session', 'term',
            'duration_minutes', 'theory_attachment', 'randomize_questions'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'e.g. First Term Examination',
                'class': 'form-input'
            }),
            'subject': forms.Select(attrs={'class': 'form-input'}),
            'teacher': forms.Select(attrs={'class': 'form-input'}),
            'session': forms.Select(attrs={'class': 'form-input'}),
            'term': forms.Select(attrs={'class': 'form-input'}),
            'duration_minutes': forms.NumberInput(attrs={
                'class': 'form-input', 'min': 5, 'value': 60
            }),
            'theory_attachment': forms.FileInput(attrs={
                'class': 'form-input',
                'accept': '.pdf,.docx,.doc'
            }),
            'randomize_questions': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 m-0 rounded border-gray-300'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_session = AcademicSession.get_current()
        current_term = Term.get_current()
        
        # Set current session and term as defaults
        self.fields['session'].initial = current_session
        self.fields['term'].initial = current_term
        
        # Filter to only teaching staff
        self.fields['teacher'].queryset = StaffProfile.objects.filter(
            user__roles__name__in=['SUBJECT_TEACHER', 'CLASS_TEACHER', 'VICE_PRINCIPAL', 'PRINCIPAL']
        ).distinct()
        
        # Set class_arms initial value if editing
        if self.instance.pk:
            self.fields['class_arms'].initial = self.instance.class_arms.all()
    
    def save(self, commit=True):
        exam = super().save(commit=commit)
        if commit:
            exam.class_arms.set(self.cleaned_data.get('class_arms', []))
        return exam


class TeacherExamForm(forms.ModelForm):
    """Form for subject teachers creating exams (without teacher selection)"""
    
    class Meta:
        model = Exam
        fields = [
            'title', 'subject', 'session', 'term',
            'duration_minutes', 'theory_attachment', 'randomize_questions'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'e.g. First Term Examination',
                'class': 'form-control'
            }),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'session': forms.Select(attrs={'class': 'form-control'}),
            'term': forms.Select(attrs={'class': 'form-control'}),
            'duration_minutes': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 5, 'value': 60
            }),
            'theory_attachment': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.docx,.doc'
            }),
            'randomize_questions': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 m-0 rounded border-gray-300'
            }),
        }

    def __init__(self, *args, **kwargs):
        # Extract teacher from kwargs if provided
        teacher = kwargs.pop('teacher', None)
        self.teacher = teacher  # Store for later use
        super().__init__(*args, **kwargs)
        current_session = AcademicSession.get_current()
        current_term = Term.get_current()
        
        # Set current session and term as defaults
        self.fields['session'].initial = current_session
        self.fields['term'].initial = current_term
        
        # Apply form-control class to all fields
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})
        
        # Add data attributes for dynamic filtering
        self.fields['subject'].widget.attrs['id'] = 'id_subject'
        
        # Filter subject based on teacher's assignments
        if teacher:
            # Get teacher's assignments for the current session and term
            from academics.models import SubjectTeacherAssignment
            assignments = SubjectTeacherAssignment.objects.filter(
                teacher=teacher,
                session=current_session,
                term=current_term
            ).select_related('subject')
            
            # Get unique subjects assigned to teacher
            assigned_subject_ids = assignments.values_list('subject', flat=True).distinct()
            
            # Identify subjects for which the teacher has already created an exam in this session/term
            # Use teacher's staff profile for filtering since Exam.teacher is StaffProfile
            try:
                staff_profile = StaffProfile.objects.get(user=teacher)
                existing_exam_subject_ids = Exam.objects.filter(
                    teacher=staff_profile,
                    session=current_session,
                    term=current_term
                ).values_list('subject_id', flat=True)
            except StaffProfile.DoesNotExist:
                existing_exam_subject_ids = []

            # Filter subjects: assigned to teacher AND no exam exists for this session/term yet
            # Only apply this exclusion for NEW exams (initial creation)
            if not self.instance.pk:
                self.fields['subject'].queryset = Subject.objects.filter(
                    id__in=assigned_subject_ids
                ).exclude(id__in=existing_exam_subject_ids)
            else:
                # For editing, include the current subject but still limit to assigned ones
                self.fields['subject'].queryset = Subject.objects.filter(id__in=assigned_subject_ids)
        
        # Disable fields if exam is in a published state (not DRAFT)
        if self.instance and self.instance.pk and self.instance.status != 'DRAFT':
            # Fields to disable when exam is not in draft
            fields_to_disable = ['title', 'subject', 'session', 'term', 'duration_minutes']
            for field_name in fields_to_disable:
                if field_name in self.fields:
                    self.fields[field_name].disabled = True
    
    def clean(self):
        """Validate that this subject/session/term combination doesn't already have an exam"""
        cleaned_data = super().clean()
        subject = cleaned_data.get('subject')
        session = cleaned_data.get('session')
        term = cleaned_data.get('term')
        
        if subject and session and term and self.teacher:
            # Check if exam already exists for this subject-session-term-teacher combination
            # Note: unique_together is ['subject', 'teacher', 'session', 'term']
            try:
                staff_profile = StaffProfile.objects.get(user=self.teacher)
                existing_exam = Exam.objects.filter(
                    subject=subject,
                    teacher=staff_profile,
                    session=session,
                    term=term
                ).exclude(pk=self.instance.pk if self.instance.pk else None).first()
                
                if existing_exam:
                    existing_classes = ', '.join(
                        str(ca) for ca in existing_exam.class_arms.all()
                    )
                    raise forms.ValidationError(
                        f'An exam already exists for {subject} in {term} — {session}. '
                        f'Classes: {existing_classes}'
                    )
            except StaffProfile.DoesNotExist:
                pass
        
        return cleaned_data
        return exam


class QuestionForm(forms.ModelForm):
    """Form for creating objective questions"""
    class Meta:
        model = ObjectiveQuestion
        fields = [
            'question_text', 'question_image', 'option_a', 'option_b',
            'option_c', 'option_d', 'correct_option'
        ]
        widgets = {
            'question_text': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-input',
                'placeholder': 'Question text (supports Yoruba Unicode characters)'
            }),
            'question_image': forms.FileInput(attrs={
                'class': 'form-input',
                'accept': 'image/*',
                'help_text': 'Upload diagram, graph, or math equation image'
            }),
            'option_a': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'Option A'
            }),
            'option_b': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'Option B'
            }),
            'option_c': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'Option C'
            }),
            'option_d': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'Option D'
            }),
            'correct_option': forms.Select(attrs={'class': 'form-input'}),
        }



class TheoryQuestionForm(forms.ModelForm):
    class Meta:
        model = TheoryQuestion
        fields = ['text', 'max_marks', 'marking_guide', 'order']
        widgets = {
            'text': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-input',
                'placeholder': 'Theory question text'
            }),
            'max_marks': forms.NumberInput(attrs={
                'class': 'form-input', 'min': 1
            }),
            'marking_guide': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-input',
                'placeholder': 'Expected answer / key points (only visible to teacher)'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-input', 'min': 1
            }),
        }


class VettingForm(forms.Form):
    action = forms.ChoiceField(
        choices=[('approve', 'Approve'), ('reject', 'Reject')],
        widget=forms.RadioSelect
    )
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-input',
            'placeholder': 'Add a comment (required if rejecting)'
        })
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('action') == 'reject' and not cleaned.get('comment'):
            raise forms.ValidationError(
                'Please provide a reason for rejection.'
            )
        return cleaned


class CAScoreForm(forms.Form):
    """Dynamic form for entering CA scores for all students"""
    def __init__(self, *args, students=None, exam=None, **kwargs):
        super().__init__(*args, **kwargs)
        if students and exam:
            for student in students:
                self.fields[f'ca1_{student.id}'] = forms.DecimalField(
                    max_digits=5, decimal_places=2,
                    min_value=0, max_value=exam.ca1_marks,
                    required=False,
                    widget=forms.NumberInput(attrs={
                        'class': 'w-20 px-2 py-1 text-sm border border-gray-200 rounded-lg text-center',
                        'step': '0.5',
                        'placeholder': '0'
                    })
                )
                self.fields[f'ca2_{student.id}'] = forms.DecimalField(
                    max_digits=5, decimal_places=2,
                    min_value=0, max_value=exam.ca2_marks,
                    required=False,
                    widget=forms.NumberInput(attrs={
                        'class': 'w-20 px-2 py-1 text-sm border border-gray-200 rounded-lg text-center',
                        'step': '0.5',
                        'placeholder': '0'
                    })
                )
                self.fields[f'theory_{student.id}'] = forms.DecimalField(
                    max_digits=5, decimal_places=2,
                    min_value=0, max_value=exam.theory_marks,
                    required=False,
                    widget=forms.NumberInput(attrs={
                        'class': 'w-20 px-2 py-1 text-sm border border-gray-200 rounded-lg text-center',
                        'step': '0.5',
                        'placeholder': '0'
                    })
                )


class ExamConfigurationForm(forms.ModelForm):
    """Form for Principals/Vice-Principals to configure exam settings"""
    
    class Meta:
        model = ExamConfiguration
        fields = [
            'session', 'term', 'total_marks',
            'ca1_marks_percentage', 'ca2_marks_percentage', 
            'obj_marks_percentage', 'theory_marks_percentage',
            'question_submission_deadline', 'exam_start_date', 'exam_end_date', 'default_exam_duration_minutes'
        ]
        widgets = {
            'session': forms.Select(attrs={'class': 'form-input'}),
            'term': forms.Select(attrs={'class': 'form-input'}),
            'total_marks': forms.NumberInput(attrs={
                'class': 'form-input', 'min': 50, 'placeholder': '100',
                'readonly': True
            }),
            
            # Percentages
            'ca1_marks_percentage': forms.NumberInput(attrs={
                'class': 'form-input percentage-input', 'min': 0, 'max': 100, 
                'placeholder': '20',
                'data-field': 'ca1'
            }),
            'ca2_marks_percentage': forms.NumberInput(attrs={
                'class': 'form-input percentage-input', 'min': 0, 'max': 100, 
                'placeholder': '20',
                'data-field': 'ca2'
            }),
            'obj_marks_percentage': forms.NumberInput(attrs={
                'class': 'form-input percentage-input', 'min': 0, 'max': 100, 
                'placeholder': '30',
                'data-field': 'obj'
            }),
            'theory_marks_percentage': forms.NumberInput(attrs={
                'class': 'form-input percentage-input', 'min': 0, 'max': 100, 
                'placeholder': '30',
                'data-field': 'theory'
            }),
            
            # Deadlines
            'question_submission_deadline': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-input'
            }),
            'exam_start_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-input'
            }),
            'exam_end_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-input'
            }),
            
            # CBT Settings
            'default_exam_duration_minutes': forms.NumberInput(attrs={
                'class': 'form-input', 'min': 5, 'placeholder': '60'
            }),
        }
    
    def clean(self):
        """Validate that percentages sum to 100"""
        cleaned_data = super().clean()
        ca1 = cleaned_data.get('ca1_marks_percentage', 0)
        ca2 = cleaned_data.get('ca2_marks_percentage', 0)
        obj = cleaned_data.get('obj_marks_percentage', 0)
        theory = cleaned_data.get('theory_marks_percentage', 0)
        
        total_percentage = ca1 + ca2 + obj + theory
        
        if total_percentage != 100:
            raise forms.ValidationError(
                f"Mark percentages must sum to exactly 100%. Current total: {total_percentage}%"
            )
        
        return cleaned_data