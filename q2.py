from examinations.models import Exam; from django.db.models import Count; duplicates = Exam.objects.values('subject', 'teacher', 'session', 'term').annotate(count=Count('id')).filter(count__gt=1); print("FOUND:", list(duplicates))
for dup in duplicates:
    qs = Exam.objects.filter(subject=dup['subject'], teacher=dup['teacher'], session=dup['session'], term=dup['term'])
    for e in qs:
        print(f"ID:{e.id} Title:{e.title}")
