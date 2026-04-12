from django import forms
from .models import SchemeOfWork
from academics.models import ClassArmSubject, Subject

class SchemeOfWorkForm(forms.ModelForm):
    class Meta:
        model = SchemeOfWork
        fields = ['session', 'term', 'class_arm', 'subject', 'attachment', 'description']
        widgets = {
            'session': forms.Select(attrs={'class': 'form-select'}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'class_arm': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional brief notes...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Initially, the subject queryset should be empty if no class_arm is selected
        # unless we are editing an existing scheme or re-rendering after a validation error
        self.fields['subject'].queryset = Subject.objects.none()

        if 'class_arm' in self.data:
            try:
                class_arm_id = int(self.data.get('class_arm'))
                subject_ids = ClassArmSubject.objects.filter(class_arm_id=class_arm_id).values_list('subject_id', flat=True)
                self.fields['subject'].queryset = Subject.objects.filter(id__in=subject_ids).order_by('name')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            subject_ids = ClassArmSubject.objects.filter(class_arm=self.instance.class_arm).values_list('subject_id', flat=True)
            self.fields['subject'].queryset = Subject.objects.filter(id__in=subject_ids).order_by('name')

    def clean_attachment(self):
        file = self.cleaned_data.get('attachment')
        if file:
            extension = file.name.split('.')[-1].lower()
            if extension not in ['pdf', 'docx', 'doc', 'pptx']:
                raise forms.ValidationError("Only PDF, DOCX, DOC, or PPTX files are allowed.")
        return file
