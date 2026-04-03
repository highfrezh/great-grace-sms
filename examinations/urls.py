from django.urls import path
from . import views

app_name = 'examinations'

urlpatterns = [

    # ── Exam Configuration (Principal/VP) ──────────────
    path('config/', views.exam_configuration_list, name='exam_config_list'),
    path('config/create/', views.exam_configuration_create, name='exam_config_create'),
    path('config/<int:pk>/', views.exam_configuration_detail, name='exam_config_detail'),
    path('config/<int:pk>/edit/', views.exam_configuration_edit, name='exam_config_edit'),

    # ── Teacher Exam Management (Simplified Workflow) ─
    path('teacher/', views.teacher_exam_list, name='teacher_exam_list'),
    path('teacher/create/', views.teacher_exam_create, name='teacher_exam_create'),
    path('teacher/<int:pk>/', views.teacher_exam_detail, name='teacher_exam_detail'),
    path('teacher/<int:pk>/edit/', views.teacher_exam_edit, name='teacher_exam_edit'),
    path('teacher/<int:pk>/publish/', views.teacher_exam_publish, name='teacher_exam_publish'),
    path('teacher/<int:pk>/delete/', views.teacher_exam_delete, name='teacher_exam_delete'),
    path('teacher/<int:exam_pk>/add-questions/', views.teacher_add_questions, name='teacher_add_questions'),

    # ── Exam Management ───────────────────────────────
    path('', views.exam_list, name='exam_list'),
    path('create/', views.exam_create, name='exam_create'),
    path('<int:pk>/', views.exam_detail, name='exam_detail'),
    path('<int:pk>/edit/', views.exam_edit, name='exam_edit'),
    path('<int:pk>/delete/', views.exam_delete, name='exam_delete'),
    path('<int:pk>/submit-for-vetting/', views.exam_submit_vetting, name='exam_submit_vetting'),
    path('<int:pk>/vet/', views.exam_vet, name='exam_vet'),
    path('<int:pk>/approve/', views.exam_approve, name='exam_approve'),
    path('<int:pk>/activate/', views.exam_activate, name='exam_activate'),
    path('<int:pk>/close/', views.exam_close, name='exam_close'),
    path('<int:pk>/preview/', views.exam_preview, name='exam_preview'),

    # ── CBT Questions ─────────────────────────────────
    path('<int:exam_pk>/questions/', views.question_list, name='question_list'),
    path('<int:exam_pk>/questions/create/', views.question_create, name='question_create'),
    path('<int:exam_pk>/questions/<int:pk>/edit/', views.question_edit, name='question_edit'),
    path('<int:exam_pk>/questions/<int:pk>/delete/', views.question_delete, name='question_delete'),

    # ── Theory Questions ──────────────────────────────
    path('<int:exam_pk>/theory/', views.theory_question_list, name='theory_question_list'),
    path('<int:exam_pk>/theory/create/', views.theory_question_create, name='theory_question_create'),
    path('<int:exam_pk>/theory/<int:pk>/edit/', views.theory_question_edit, name='theory_question_edit'),
    path('<int:exam_pk>/theory/<int:pk>/delete/', views.theory_question_delete, name='theory_question_delete'),

    # ── CBT Exam Taking (Student) ─────────────────────
    path('<int:pk>/take/', views.exam_take, name='exam_take'),
    path('<int:pk>/submit/', views.exam_submit, name='exam_submit'),
    path('<int:pk>/autosave/', views.exam_autosave, name='exam_autosave'),
    path('<int:pk>/result/', views.exam_result_student, name='exam_result_student'),

    # ── Theory Score Entry (Teacher) ──────────────────
    path('<int:pk>/theory-scores/', views.theory_score_entry, name='theory_score_entry'),
    path('<int:pk>/theory-scores/bulk/', views.theory_score_bulk, name='theory_score_bulk'),

    # ── CA Score Entry ────────────────────────────────
    path('<int:pk>/ca-scores/', views.ca_score_entry, name='ca_score_entry'),

    # ── Results ───────────────────────────────────────
    path('<int:pk>/results/', views.exam_results, name='exam_results'),
    path('<int:pk>/results/publish/', views.exam_publish_results, name='exam_publish_results'),

]