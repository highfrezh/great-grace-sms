# Generated migration for SubjectTeacherAssignment unique constraint

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0004_subject_code_alter_classsubject_class_level_and_more'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='subjectteacherassignment',
            unique_together={('subject', 'class_arm', 'session', 'term')},
        ),
    ]
