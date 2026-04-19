import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from academics.models import AcademicSession, Term, Subject, ClassArm
from examinations.models import Exam, ObjectiveQuestion

def seed_exams():
    print("Cleaning up old duplicate seeded terms if any...")
    Term.objects.filter(name__in=['1', '2', '3']).delete()

    print("Seeding exams...")
    
    # 1. Ensure Session
    session = AcademicSession.objects.filter(name="2025/2026").first()
    if not session:
        session = AcademicSession.objects.create(name="2025/2026", start_date="2025-09-01", end_date="2026-07-30")
    
    # 2. Existing Terms
    term_mapping = [
        ('FIRST', "First Term"),
        ('SECOND', "Second Term"),
        ('THIRD', "Third Term")
    ]
    terms = []
    for term_choice, term_name in term_mapping:
        term, _ = Term.objects.get_or_create(
            session=session,
            name=term_choice,
            defaults={'start_date': "2025-09-01", 'end_date': "2025-12-15"}
        )
        terms.append(term)
        
    # Get JSS1 class arms
    from academics.models import ClassLevel, SubjectTeacherAssignment
    jss1_level = ClassLevel.objects.filter(name__icontains="JSS 1").first()
    if not jss1_level:
        print("Could not find JSS 1 level! Aborting.")
        return
        
    jss1_arms = list(ClassArm.objects.filter(level=jss1_level, session=session))
    
    subjects_data = {
        "AGRICULTURAL SCIENCE": [
            ("Which of the following is a farming system?", "Crop rotation", "Mining", "Fishing", "Hunting", "A"),
            ("Which part of a plant is primarily responsible for photosynthesis?", "Root", "Stem", "Leaf", "Flower", "C"),
            ("A farm implement used for tilling the soil is ___", "Cutlass", "Hoe", "Plough", "Wheelbarrow", "C"),
            ("The rearing of birds for meat and egg is called ___", "Apiculture", "Aquaculture", "Poultry", "Horticulture", "C"),
            ("Which of these is NOT a cash crop?", "Cocoa", "Rubber", "Maize", "Cotton", "C")
        ],
        "ENGLISH": [
            ("Identify the noun in this sentence: 'The quick brown fox'", "quick", "brown", "fox", "The", "C"),
            ("A word that describes an action is called a ___", "Noun", "Pronoun", "Adverb", "Verb", "D"),
            ("Choose the correct spelling:", "Accomodation", "Accommodation", "Acommodation", "Accomodasion", "B"),
            ("What is the past tense of 'Go'?", "Goed", "Went", "Gone", "Going", "B"),
            ("The antonym of 'Beautiful' is ___", "Ugly", "Pretty", "Nice", "Good", "A")
        ],
        "FRENCH": [
            ("What is 'Good morning' in French?", "Bonsoir", "Bonjour", "Au revoir", "Merci", "B"),
            ("How do you say 'Thank you' in French?", "Merci", "S'il vous plaît", "Pardon", "Oui", "A"),
            ("What does 'Maison' mean?", "Car", "House", "Dog", "Tree", "B"),
            ("Translate 'I am reading' to French.", "Je mange", "Je lis", "Je dors", "Je parle", "B"),
            ("The French word for 'Red' is ___", "Bleu", "Jaune", "Rouge", "Vert", "C")
        ],
        "MATHEMATICS": [
            ("What is the derivative of $x^2$?", "$2x$", "$x$", "$2$", "$x^2$", "A"),
            ("Solve for $x$ if $2x + 4 = 10$", "$x = 2$", "$x = 3$", "$x = 4$", "$x = 5$", "B"),
            ("Evaluate $\\int_0^1 x\\ dx$", "0", "0.5", "1", "1.5", "B"),
            ("What is the value of $\\pi$ to 2 decimal places?", "3.12", "3.14", "3.16", "3.18", "B"),
            ("Find the area of a circle with radius $r=3$.", "$6\\pi$", "$9\\pi$", "$12\\pi$", "$3\\pi$", "B")
        ],
        "YORUBA": [
            ("Kí ni ìtumọ̀ 'Baálé' ni èdè Gẹ̀ẹ́sì?", "Head of the family/town", "Mother", "Stranger", "King", "A"),
            ("Sọ 'Omi' sí èdè Gẹ̀ẹ́sì.", "Fire", "Water", "Earth", "Air", "B"),
            ("Báwo la ṣe ń kí èèyàn lálẹ́ ni èdè Yorùbá?", "Ẹ káàárọ̀", "Ẹ káàsán", "Ẹ káalẹ́", "Ẹ kúulé", "C"),
            ("Kí ni orúkọ ẹranko tí ó ń jẹ́ 'Aja'?", "Cat", "Dog", "Goat", "Sheep", "B"),
            ("Kí ni ìtumọ̀ 'Ilé-ìwé'?", "Market", "Church", "School", "Hospital", "C")
        ]
    }
    
    for subject_name, questions in subjects_data.items():
        subject = Subject.objects.filter(name__iexact=subject_name).first()
        if not subject:
            subject = Subject.objects.create(name=subject_name)
            
        # Get the intended teacher for JSS 1 for this subject
        assignment = SubjectTeacherAssignment.objects.filter(subject=subject, class_level=jss1_level).first()
        exam_teacher = None
        if assignment and assignment.teacher:
            try:
                exam_teacher = assignment.teacher.staff_profile
            except Exception:
                from staff.models import StaffProfile
                exam_teacher = StaffProfile.objects.create(
                    user=assignment.teacher,
                    gender='MALE'
                )
        
        for term in terms:
            exam_title = f"{jss1_level.name} {term.get_name_display()} {subject.name} Examination"
            
            # Check if exam exists
            exam = Exam.objects.filter(subject=subject, session=session, term=term).first()
            if not exam:
                exam = Exam.objects.create(
                    subject=subject,
                    session=session,
                    term=term,
                    title=exam_title,
                    duration_minutes=60,
                    status=Exam.ExamStatus.APPROVED,
                    teacher=exam_teacher
                )
                print(f"Created Exam: {exam_title}")
            else:
                exam.title = exam_title
                exam.teacher = exam_teacher
                exam.save()
                
            exam.class_arms.set(jss1_arms)
                
            # Clear old questions
            exam.objectives.all().delete()

            
            # Insert questions
            for q_text, opt_a, opt_b, opt_c, opt_d, ans in questions:
                ObjectiveQuestion.objects.create(
                    exam=exam,
                    question_text=q_text,
                    option_a=opt_a,
                    option_b=opt_b,
                    option_c=opt_c,
                    option_d=opt_d,
                    correct_option=ans
                )
            print(f"  Added 5 questions for {subject.name} - {term.get_name_display()}")
            
if __name__ == '__main__':
    seed_exams()
    print("Seeding complete!")
