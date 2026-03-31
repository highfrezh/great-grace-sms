from django import forms
from .models import AcademicSession, Term, ClassLevel, ClassArm, Subject, ClassSubject


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


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g. Mathematics',
                'class': 'form-input'
            }),
            'code': forms.TextInput(attrs={
                'placeholder': 'e.g. MTH',
                'class': 'form-input'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-input'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }