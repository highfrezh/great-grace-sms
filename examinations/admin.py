from django.contrib import admin
from .models import (
    Exam, Question, TheoryQuestion, ExamSubmission,
    StudentAnswer, TheoryScore, ExamResult, ExamDeadlinePenalty,
    ExamConfiguration
)

# ── ExamConfiguration ────────────────────────────────────────
@admin.register(ExamConfiguration)
class ExamConfigurationAdmin(admin.ModelAdmin):
    list_display = (
        'session', 'term', 'total_marks', 'percentages_total',
        'configured_by', 'configured_at'
    )
    list_filter = ('session', 'term', 'configured_at')
    search_fields = ('session__name', 'term__name')
    readonly_fields = ('configured_at', 'configured_by')
    fieldsets = (
        ('Period', {
            'fields': ('session', 'term')
        }),
        ('Mark Distribution (%)', {
            'fields': (
                'ca1_marks_percentage',
                'ca2_marks_percentage',
                'obj_marks_percentage',
                'theory_marks_percentage',
                'total_marks'
            ),
            'description': 'Percentages must sum to 100%'
        }),
        ('Deadlines', {
            'fields': (
                'question_submission_deadline',
                'exam_vetting_deadline',
                'exam_approval_deadline'
            )
        }),
        ('CBT Settings', {
            'fields': (
                'default_exam_duration_minutes',
                'randomize_questions_by_default',
                'show_results_immediately'
            )
        }),
        ('Metadata', {
            'fields': ('configured_by', 'configured_at'),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        """Set configured_by to current user if not already set"""
        if not obj.configured_by:
            obj.configured_by = request.user
        super().save_model(request, obj, form, change)
    
    def percentages_total(self, obj):
        """Display percentage total"""
        total = obj.percentages_total
        color = 'green' if total == 100 else 'red'
        return f'<span style="color: {color}; font-weight: bold;">{total}%</span>'
    percentages_total.short_description = 'Total %'
    percentages_total.allow_tags = True
