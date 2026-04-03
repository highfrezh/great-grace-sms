from django import forms
from django.core.validators import RegexValidator
from .models import Student, Guardian, StudentEnrollment
from academics.models import ClassArm, AcademicSession, Term


class StudentForm(forms.ModelForm):
    """Form for creating and editing students"""
    
    class Meta:
        model = Student
        fields = [
            'first_name', 'last_name', 'other_names',
            'date_of_birth', 'gender',
            'phone', 'email', 'address',
            'blood_group', 'allergies', 'medical_conditions',
            'emergency_contact', 'emergency_phone',
            'is_active'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last Name'}),
            'other_names': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Other Names (optional)'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-input'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Phone Number'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email Address'}),
            'address': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Home Address'}),
            'blood_group': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. O+'}),
            'allergies': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Known allergies'}),
            'medical_conditions': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Medical conditions'}),
            'emergency_contact': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Emergency Contact Name'}),
            'emergency_phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Emergency Phone'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class GuardianForm(forms.ModelForm):
    """Form for creating and editing guardians"""
    
    class Meta:
        model = Guardian
        fields = [
            'full_name', 'relationship', 'phone', 'email',
            'address', 'occupation', 'is_primary', 'portal_enabled'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full Name'}),
            'relationship': forms.Select(attrs={'class': 'form-input'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Phone Number'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email Address'}),
            'address': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Address'}),
            'occupation': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Occupation'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'portal_enabled': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class StudentEnrollmentForm(forms.ModelForm):
    """Form for enrolling students into class arms"""
    
    class Meta:
        model = StudentEnrollment
        fields = ['class_arm', 'session', 'term']
        widgets = {
            'class_arm': forms.Select(attrs={'class': 'form-input'}),
            'session': forms.Select(attrs={'class': 'form-input'}),
            'term': forms.Select(attrs={'class': 'form-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Default to current session and term
        self.fields['session'].initial = AcademicSession.get_current()
        self.fields['term'].initial = Term.get_current()
        # Only show active class arms
        self.fields['class_arm'].queryset = ClassArm.objects.filter(
            session=AcademicSession.get_current()
        ).select_related('level')


class StudentSearchForm(forms.Form):
    """Form for searching students"""
    
    query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Search by name, admission number...'
        })
    )
    class_arm = forms.ModelChoiceField(
        queryset=ClassArm.objects.none(),
        required=False,
        empty_label="All Classes",
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_session = AcademicSession.get_current()
        if current_session:
            self.fields['class_arm'].queryset = ClassArm.objects.filter(
                session=current_session
            ).select_related('level').order_by('level__order', 'name')


class BulkStudentImportForm(forms.Form):
    """Form for bulk importing students from Excel file"""
    file = forms.FileField(
        label='Upload File',
        help_text='Upload Excel file (.xlsx)',
        widget=forms.FileInput(attrs={'class': 'form-input', 'accept': '.xlsx'})
    )
    class_arm = forms.ModelChoiceField(
        queryset=ClassArm.objects.all(),
        label='Class Arm',
        help_text='Default class for imported students',
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    session = forms.ModelChoiceField(
        queryset=AcademicSession.objects.all(),
        label='Academic Session',
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    term = forms.ModelChoiceField(
        queryset=Term.objects.all(),
        label='Term',
        widget=forms.Select(attrs={'class': 'form-input'})
    )
