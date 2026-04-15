from django import forms
from django.contrib.auth import get_user_model
from accounts.models import Role
from .models import StaffProfile

User = get_user_model()


class StaffUserForm(forms.ModelForm):
    """Form for the User part of staff creation"""

    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.exclude(name__in=['STUDENT', 'PARENT']),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Assign Roles"
    )
    
    # Add phone_number field
    phone_number = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. 08012345678',
            'class': 'form-input'
        }),
        label="Phone Number",
        help_text="This will be used as the default password"
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username', 'phone_number', 'roles']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'placeholder': 'First name',
                'class': 'form-input'
            }),
            'last_name': forms.TextInput(attrs={
                'placeholder': 'Last name',
                'class': 'form-input'
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'Email address',
                'class': 'form-input'
            }),
            'username': forms.TextInput(attrs={
                'placeholder': 'Username for login',
                'class': 'form-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['email'].required = True
        self.fields['phone_number'].required = True  # Make phone_number required


class StaffProfileForm(forms.ModelForm):
    """Form for the StaffProfile part"""

    class Meta:
        model = StaffProfile
        fields = [
            'gender', 'date_of_birth', 'marital_status',
            'address', 'state_of_origin', 'religion',
            'profile_picture', 'employment_date', 'employment_type',
            'highest_qualification', 'qualification_subject',
            'institution', 'year_obtained', 'teaching_certificate',
            'next_of_kin_name', 'next_of_kin_relationship',
            'next_of_kin_phone', 'next_of_kin_address',
            'bank_name', 'account_name', 'account_number',
        ]
        widgets = {
            'gender': forms.Select(attrs={'class': 'form-input'}),
            'date_of_birth': forms.DateInput(attrs={
                'type': 'date', 'class': 'form-input'
            }),
            'marital_status': forms.Select(attrs={'class': 'form-input'}),
            'address': forms.Textarea(attrs={
                'rows': 2, 'class': 'form-input',
                'placeholder': 'Home address'
            }),
            'state_of_origin': forms.TextInput(attrs={
                'placeholder': 'e.g. Lagos',
                'class': 'form-input'
            }),
            'religion': forms.TextInput(attrs={
                'placeholder': 'e.g. Christianity',
                'class': 'form-input'
            }),
            'employment_date': forms.DateInput(attrs={
                'type': 'date', 'class': 'form-input'
            }),
            'employment_type': forms.Select(attrs={'class': 'form-input'}),
            'highest_qualification': forms.Select(attrs={'class': 'form-input'}),
            'qualification_subject': forms.TextInput(attrs={
                'placeholder': 'e.g. B.Sc Mathematics',
                'class': 'form-input'
            }),
            'institution': forms.TextInput(attrs={
                'placeholder': 'e.g. University of Lagos',
                'class': 'form-input'
            }),
            'year_obtained': forms.NumberInput(attrs={
                'placeholder': 'e.g. 2015',
                'class': 'form-input'
            }),
            'teaching_certificate': forms.TextInput(attrs={
                'placeholder': 'e.g. PGDE, NCE',
                'class': 'form-input'
            }),
            'next_of_kin_name': forms.TextInput(attrs={
                'placeholder': 'Full name',
                'class': 'form-input'
            }),
            'next_of_kin_relationship': forms.TextInput(attrs={
                'placeholder': 'e.g. Spouse, Parent',
                'class': 'form-input'
            }),
            'next_of_kin_phone': forms.TextInput(attrs={
                'placeholder': 'Phone number',
                'class': 'form-input'
            }),
            'next_of_kin_address': forms.Textarea(attrs={
                'rows': 2, 'class': 'form-input',
                'placeholder': 'Next of kin address'
            }),
            'bank_name': forms.TextInput(attrs={
                'placeholder': 'e.g. First Bank',
                'class': 'form-input'
            }),
            'account_name': forms.TextInput(attrs={
                'placeholder': 'Account name',
                'class': 'form-input'
            }),
            'account_number': forms.TextInput(attrs={
                'placeholder': '10-digit account number',
                'class': 'form-input'
            }),
        }


class StaffSelfUpdateForm(forms.ModelForm):
    """Form for staff to update their own limited profile info"""
    class Meta:
        model = StaffProfile
        fields = ['profile_picture', 'address']
        widgets = {
            'profile_picture': forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
            'address': forms.Textarea(attrs={
                'rows': 2, 'class': 'form-input',
                'placeholder': 'Home address'
            }),
        }