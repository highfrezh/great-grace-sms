from django import forms
from django.contrib.auth import get_user_model
from academics.models import Subject, ClassArm, AcademicSession, Term
from .models import Exam, Question, TheoryQuestion, TheoryScore, ExamResult, ExamConfiguration

User = get_user_model()


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = [
            'title', 'subject', 'class_arm', 'session', 'term',
            'exam_type', 'obj_marks', 'theory_marks',
            'ca1_marks', 'ca2_marks', 'duration_minutes',
            'randomize_questions', 'show_result_immediately',
            'submission_deadline',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'e.g. Mathematics First Term Exam 2024',
                'class': 'form-input'
            }),
            'subject': forms.Select(attrs={'class': 'form-input'}),
            'class_arm': forms.Select(attrs={'class': 'form-input'}),
            'session': forms.Select(attrs={'class': 'form-input'}),
            'term': forms.Select(attrs={'class': 'form-input'}),
            'exam_type': forms.Select(attrs={'class': 'form-input'}),
            'obj_marks': forms.NumberInput(attrs={
                'class': 'form-input', 'min': 0
            }),
            'theory_marks': forms.NumberInput(attrs={
                'class': 'form-input', 'min': 0
            }),
            'ca1_marks': forms.NumberInput(attrs={
                'class': 'form-input', 'min': 0
            }),
            'ca2_marks': forms.NumberInput(attrs={
                'class': 'form-input', 'min': 0
            }),
            'duration_minutes': forms.NumberInput(attrs={
                'class': 'form-input', 'min': 5
            }),
            'submission_deadline': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-input'
            }),
            'randomize_questions': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            }),
            'show_result_immediately': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        current_session = AcademicSession.get_current()
        current_term = Term.get_current()
        self.fields['session'].initial = current_session
        self.fields['term'].initial = current_term

        # If subject teacher filter to their assigned subjects
        if user and user.is_subject_teacher and not user.is_admin_staff:
            from academics.models import SubjectTeacherAssignment
            assigned = SubjectTeacherAssignment.objects.filter(
                teacher=user,
                session=current_session
            ).values_list('subject_id', 'class_arm_id')
            subject_ids = list(set([a[0] for a in assigned]))
            class_ids = list(set([a[1] for a in assigned]))
            self.fields['subject'].queryset = Subject.objects.filter(
                id__in=subject_ids
            )
            self.fields['class_arm'].queryset = ClassArm.objects.filter(
                id__in=class_ids
            )


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = [
            'text', 'image', 'option_a', 'option_b',
            'option_c', 'option_d', 'correct_answer',
            'difficulty', 'marks', 'order',
            'text_yoruba', 'option_a_yoruba', 'option_b_yoruba',
            'option_c_yoruba', 'option_d_yoruba'
        ]
        widgets = {
            # ── English Fields ────────────────────
            'text': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-input',
                'placeholder': 'Question text. Use $...$ for LaTeX math.'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-input',
                'accept': 'image/*'
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
            
            # ── Yoruba Fields ─────────────────────
            'text_yoruba': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-input',
                'placeholder': 'Literal translation in Yoruba (optional)'
            }),
            'option_a_yoruba': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'Option A (Yoruba)'
            }),
            'option_b_yoruba': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'Option B (Yoruba)'
            }),
            'option_c_yoruba': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'Option C (Yoruba)'
            }),
            'option_d_yoruba': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'Option D (Yoruba)'
            }),
            
            # ── Metadata ───────────────────────────
            'correct_answer': forms.Select(attrs={'class': 'form-input'}),
            'difficulty': forms.Select(attrs={'class': 'form-input'}),
            'marks': forms.NumberInput(attrs={
                'class': 'form-input', 'min': 1
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-input', 'min': 1
            }),
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


class ExamConfigurationForm(forms.ModelForm):
    """Form for Principals/Vice-Principals to configure exam settings"""
    
    class Meta:
        model = ExamConfiguration
        fields = [
            'session', 'term', 'total_marks',
            'ca1_marks_percentage', 'ca2_marks_percentage', 
            'obj_marks_percentage', 'theory_marks_percentage',
            'question_submission_deadline', 'exam_vetting_deadline',
            'exam_approval_deadline', 'default_exam_duration_minutes',
            'randomize_questions_by_default', 'show_results_immediately'
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
            'exam_vetting_deadline': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-input'
            }),
            'exam_approval_deadline': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-input'
            }),
            
            # CBT Settings
            'default_exam_duration_minutes': forms.NumberInput(attrs={
                'class': 'form-input', 'min': 5, 'placeholder': '60'
            }),
            'randomize_questions_by_default': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            }),
            'show_results_immediately': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
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