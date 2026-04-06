# Generated manually for exam workflow status

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('examinations', '0003_exam_approval_comments_exam_approval_status_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add new status field
        migrations.AddField(
            model_name='exam',
            name='status',
            field=models.CharField(
                choices=[
                    ('DRAFT', 'Draft (Editing)'),
                    ('AWAITING_APPROVAL', 'Awaiting Examiner Approval'),
                    ('APPROVED', 'Approved')
                ],
                default='DRAFT',
                help_text='Exam workflow status',
                max_length=20
            ),
        ),
        # Add rejection reason field
        migrations.AddField(
            model_name='exam',
            name='rejection_reason',
            field=models.TextField(blank=True, help_text='Reason why the exam was rejected by examiner', null=True),
        ),
        # Add rejected_by field
        migrations.AddField(
            model_name='exam',
            name='rejected_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='exams_rejected',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        # Add rejected_at field
        migrations.AddField(
            model_name='exam',
            name='rejected_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
