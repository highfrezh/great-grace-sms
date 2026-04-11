import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from academics.models import Subject, ClassArm
from academics.forms import SubjectSearchForm
from django.db.models import Q

print('--- Verification Script ---')
all_subjects = Subject.objects.all()
print(f'Total subjects: {all_subjects.count()}')

if all_subjects.exists():
    s1 = all_subjects.first()
    print(f'Testing filter with: "{s1.name}"')
    
    # Simulate view logic
    query = s1.name[:4]
    filtered = Subject.objects.filter(Q(name__icontains=query) | Q(code__icontains=query)).distinct()
    print(f'Match for "{query}": {filtered.count()} found')
    
    if filtered.filter(pk=s1.pk).exists():
        print('SUCCESS: Text filtering logic verified.')
    else:
        print('FAILURE: Text filtering logic failed.')

    # Test status filtering
    active_count = Subject.objects.filter(is_active=True).count()
    inactive_count = Subject.objects.filter(is_active=False).count()
    print(f'Active: {active_count}, Inactive: {inactive_count}')
    
    # Test Class Arm filtering if any
    if ClassArm.objects.exists():
        ca = ClassArm.objects.first()
        from academics.models import ClassArmSubject
        # Check if any subject is linked to this arm
        linked_subjects = Subject.objects.filter(class_arms__class_arm=ca).distinct()
        print(f'Subjects linked to {ca}: {linked_subjects.count()}')

print('--- Verification End ---')
