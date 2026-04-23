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
    theory_attachment = forms.FileField(
        label='Theory Questions File',
        required=False,
        help_text='Upload a PDF or TXT file containing the theory questions.',
        widget=forms.FileInput(attrs={'accept': '.pdf,.txt'})
    )

    def clean_theory_attachment(self):
        file = self.cleaned_data.get('theory_attachment')
        if file:
            extension = file.name.split('.')[-1].lower()
            if extension not in ['pdf', 'txt']:
                raise forms.ValidationError("Only PDF and TXT files are supported for theory questions.")
        return file
    
    class Meta:
        model = Exam
        fields = [
            'title', 'subject', 'teacher', 'session', 'term',
            'duration_minutes', 'theory_attachment', 'randomize_questions',
            'show_results_immediately'
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
                'accept': '.pdf,.txt'
            }),
            'randomize_questions': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 m-0 rounded border-gray-300'
            }),
            'show_results_immediately': forms.CheckboxInput(attrs={
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
        
        # Set class_arms initial value if editing
        if self.instance.pk:
            self.fields['class_arms'].initial = self.instance.class_arms.all()
        
        # If user is a teacher, restrict subject and class_arms
        user = kwargs.get('user')
        if user and not (user.is_admin_staff or user.is_superuser):
            from academics.models import SubjectTeacherAssignment
            assignments = SubjectTeacherAssignment.objects.filter(teacher=user)
            
            # Filter subjects
            assigned_subject_ids = assignments.values_list('subject_id', flat=True).distinct()
            self.fields['subject'].queryset = Subject.objects.filter(id__in=assigned_subject_ids)
            
            # Filter class_arms to only those in current session matching assignments
            assigned_class_ids = set()
            for assignment in assignments:
                matching_arms = ClassArm.objects.filter(
                    session=current_session,
                    level=assignment.class_level,
                    name=assignment.arm_name
                ).values_list('id', flat=True)
                assigned_class_ids.update(matching_arms)
            
            self.fields['class_arms'].queryset = ClassArm.objects.filter(id__in=assigned_class_ids)
    
    def save(self, commit=True):
        exam = super().save(commit=commit)
        if commit:
            exam.class_arms.set(self.cleaned_data.get('class_arms', []))
        return exam


class TeacherExamForm(forms.ModelForm):
    """Simplified form for subject teachers creating exams with a single multi-select field"""
    
    subject_arms = forms.MultipleChoiceField(
        choices=[],
        widget=forms.SelectMultiple(attrs={'class': 'form-control', 'style': 'height: 150px;'}),
        label='Assigned Subjects & Classes',
        help_text='Hold Ctrl (Cmd on Mac) to select multiple classes for the same subject.'
    )

    class Meta:
        model = Exam
        fields = [
            'title', 'session', 'term',
            'duration_minutes', 'theory_attachment', 'randomize_questions',
            'show_results_immediately'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'e.g. First Term Examination',
                'class': 'form-control'
            }),
            'session': forms.Select(attrs={'class': 'form-control'}),
            'term': forms.Select(attrs={'class': 'form-control'}),
            'duration_minutes': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 5, 'value': 60
            }),
            'theory_attachment': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.txt'
            }),
            'randomize_questions': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 m-0 rounded border-gray-300'
            }),
            'show_results_immediately': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 m-0 rounded border-gray-300'
            }),
        }

    def __init__(self, *args, **kwargs):
        teacher = kwargs.pop('teacher', None)
        self.teacher = teacher
        super().__init__(*args, **kwargs)
        
        current_session = AcademicSession.get_current()
        current_term = Term.get_current()
        self.fields['session'].initial = current_session
        self.fields['term'].initial = current_term
        
        if teacher:
            from academics.models import SubjectTeacherAssignment, ClassArm as _ClassArm
            assignments = SubjectTeacherAssignment.objects.filter(
                teacher=teacher
            ).select_related('subject', 'class_level').order_by('subject__name', 'class_level__order', 'arm_name')
            
            choices = []
            for assignment in assignments:
                # Find matching arms in current session
                arms = _ClassArm.objects.filter(
                    session=current_session,
                    level=assignment.class_level,
                    name=assignment.arm_name
                )
                for arm in arms:
                    value = f"{assignment.subject_id}:{arm.id}"
                    label = f"{assignment.subject.name} ({arm.full_name})"
                    choices.append((value, label))
            
            self.fields['subject_arms'].choices = choices

        if self.instance.pk:
            # Set initial values for subject_arms if editing
            initial_choices = []
            for arm in self.instance.class_arms.all():
                initial_choices.append(f"{self.instance.subject_id}:{arm.id}")
            self.fields['subject_arms'].initial = initial_choices

            # Disable fields if not in DRAFT
            if self.instance.status != 'DRAFT':
                for field in ['title', 'session', 'term', 'duration_minutes', 'subject_arms']:
                    if field in self.fields:
                        self.fields[field].disabled = True
                        self.fields[field].required = False

    def clean(self):
        cleaned_data = super().clean()
        subject_arms = cleaned_data.get('subject_arms')
        session = cleaned_data.get('session')
        term = cleaned_data.get('term')

        if subject_arms and session and term:
            # Parse all selected subject:arm pairs
            selected_subject_ids = set()
            arm_ids = []
            
            for item in subject_arms:
                try:
                    s_id, a_id = item.split(':', 1)
                    selected_subject_ids.add(s_id)
                    arm_ids.append(a_id)
                except ValueError:
                    continue
            
            # Validation: All selected combinations MUST belong to the same subject
            if len(selected_subject_ids) > 1:
                raise forms.ValidationError(
                    "You cannot create one exam for multiple different subjects. "
                    "Please select only classes for a single subject."
                )
            
            if not selected_subject_ids:
                raise forms.ValidationError("Please select at least one subject-class combination.")

            # Store the resolved subject for the view to use
            from academics.models import Subject as _Subject, ClassArm as _ClassArm
            subject = _Subject.objects.get(id=list(selected_subject_ids)[0])
            cleaned_data['resolved_subject'] = subject
            cleaned_data['resolved_arm_ids'] = arm_ids

            # Check for existing exams for any of these combinations
            staff_profile = None
            if self.teacher:
                from staff.models import StaffProfile
                try:
                    staff_profile = StaffProfile.objects.get(user=self.teacher)
                except StaffProfile.DoesNotExist:
                    pass

            if staff_profile:
                for arm_id in arm_ids:
                    existing_exam = Exam.objects.filter(
                        subject=subject,
                        teacher=staff_profile,
                        session=session,
                        term=term,
                        class_arms__id=arm_id
                    ).exclude(pk=self.instance.pk if self.instance.pk else None).first()

                    if existing_exam:
                        arm = _ClassArm.objects.get(id=arm_id)
                        raise forms.ValidationError(
                            f'An exam already exists for {subject.name} in {arm.full_name} for this term.'
                        )

        return cleaned_data

    def save(self, commit=True):
        exam = super().save(commit=False)
        # Set the resolved subject
        if 'resolved_subject' in self.cleaned_data:
            exam.subject = self.cleaned_data['resolved_subject']
        
        # Handle file cleanup: If a new theory_attachment is uploaded, delete the old one
        if self.instance.pk:
            try:
                old_exam = Exam.objects.get(pk=self.instance.pk)
                new_file = self.cleaned_data.get('theory_attachment')
                
                # Check if file has changed (and it's not just the same file being re-saved)
                if new_file and old_exam.theory_attachment and old_exam.theory_attachment != new_file:
                    import os
                    if os.path.isfile(old_exam.theory_attachment.path):
                        os.remove(old_exam.theory_attachment.path)
            except (Exam.DoesNotExist, ValueError):
                pass

        if commit:
            exam.save()
            # Set ManyToMany class arms
            if 'resolved_arm_ids' in self.cleaned_data:
                exam.class_arms.set(self.cleaned_data['resolved_arm_ids'])
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