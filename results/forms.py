from django import forms
from .models import ReportCard, StudentDomainRating

class ReportCardCommentForm(forms.ModelForm):
    class Meta:
        model = ReportCard
        fields = ['attendance_present', 'attendance_total', 'teacher_comment']
        widgets = {
            'attendance_present': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'attendance_total': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'teacher_comment': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Enter class teacher comment...'}),
        }

class DomainRatingForm(forms.ModelForm):
    class Meta:
        model = StudentDomainRating
        fields = ['rating']
        widgets = {
            'rating': forms.Select(attrs={'class': 'form-input'}),
        }
class PrincipalReportCardForm(forms.ModelForm):
    class Meta:
        model = ReportCard
        fields = ['principal_comment']
        widgets = {
            'principal_comment': forms.Textarea(attrs={
                'class': 'form-input', 
                'rows': 4, 
                'placeholder': 'Enter official principal/vice-principal remark...'
            }),
        }
