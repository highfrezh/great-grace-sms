from examinations.models import Exam
from django.db.models import Count

# Find duplicates
duplicates = Exam.objects.values('subject', 'teacher', 'session', 'term').annotate(count=Count('id')).filter(count__gt=1)
print("=== DUPLICATES FOUND ===")
for dup in duplicates:
    print(dup)
    
print("\n=== DETAILED EXAM INFO ===")
for dup in duplicates:
    exams = Exam.objects.filter(subject=dup['subject'], teacher=dup['teacher'], session=dup['session'], term=dup['term']).order_by('id')
    print("Duplicate group:")
    print("  Subject ID:", dup['subject'])
    print("  Teacher ID:", dup['teacher']) 
    print("  Session:", dup['session'])
    print("  Term:", dup['term'])
    for exam in exams:
        print("    -> Exam ID:", exam.id, "Title:", exam.title)
