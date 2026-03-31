from django.db import migrations


def populate_roles(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    roles = [
        'PRINCIPAL',
        'VICE_PRINCIPAL',
        'CLASS_TEACHER',
        'SUBJECT_TEACHER',
        'EXAMINER',
        'PARENT',
        'STUDENT',
    ]
    for role_name in roles:
        Role.objects.get_or_create(name=role_name)


def reverse_roles(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Role.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_user_role'),  
    ]

    operations = [
        migrations.RunPython(populate_roles, reverse_roles),
    ]