from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [

    # Sessions
    path('sessions/', views.session_list, name='session_list'),
    path('sessions/create/', views.session_create, name='session_create'),
    path('sessions/<int:pk>/edit/', views.session_edit, name='session_edit'),
    path('sessions/<int:pk>/set-current/', views.session_set_current, name='session_set_current'),
    path('sessions/<int:pk>/delete/', views.session_delete, name='session_delete'),

    # Terms
    path('terms/', views.term_list, name='term_list'),
    path('terms/create/', views.term_create, name='term_create'),
    path('terms/<int:pk>/edit/', views.term_edit, name='term_edit'),
    path('terms/<int:pk>/set-current/', views.term_set_current, name='term_set_current'),
    path('terms/<int:pk>/delete/', views.term_delete, name='term_delete'),

    # Class Levels
    path('class-levels/', views.class_level_list, name='class_level_list'),
    path('class-levels/create/', views.class_level_create, name='class_level_create'),
    path('class-levels/<int:pk>/edit/', views.class_level_edit, name='class_level_edit'),

    # Class Arms
    path('classes/', views.class_arm_list, name='class_arm_list'),
    path('classes/create/', views.class_arm_create, name='class_arm_create'),
    path('classes/<int:pk>/edit/', views.class_arm_edit, name='class_arm_edit'),
    path('class-levels/<int:pk>/delete/', views.class_level_delete, name='class_level_delete'),
    path('classes/<int:pk>/delete/', views.class_arm_delete, name='class_arm_delete'),

    # Subjects
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/create/', views.subject_create, name='subject_create'),
    path('subjects/<int:pk>/edit/', views.subject_edit, name='subject_edit'),
    path('subjects/<int:pk>/delete/', views.subject_delete, name='subject_delete'),
    path('subjects/<int:pk>/toggle/', views.subject_toggle, name='subject_toggle'),

    # Subject Teacher Assignments
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/create/', views.assignment_create, name='assignment_create'),
    path('assignments/<int:pk>/edit/', views.assignment_edit, name='assignment_edit'),
    path('assignments/<int:pk>/delete/', views.assignment_delete, name='assignment_delete'),

]