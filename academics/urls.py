from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [

    # Sessions
    path('sessions/', views.session_list, name='session_list'),
    path('sessions/create/', views.session_create, name='session_create'),
    path('sessions/<int:pk>/edit/', views.session_edit, name='session_edit'),
    path('sessions/<int:pk>/set-current/', views.session_set_current, name='session_set_current'),

    # Terms
    path('terms/', views.term_list, name='term_list'),
    path('terms/create/', views.term_create, name='term_create'),
    path('terms/<int:pk>/edit/', views.term_edit, name='term_edit'),
    path('terms/<int:pk>/set-current/', views.term_set_current, name='term_set_current'),

    # Class Levels
    path('class-levels/', views.class_level_list, name='class_level_list'),
    path('class-levels/create/', views.class_level_create, name='class_level_create'),
    path('class-levels/<int:pk>/edit/', views.class_level_edit, name='class_level_edit'),

    # Class Arms
    path('classes/', views.class_arm_list, name='class_arm_list'),
    path('classes/create/', views.class_arm_create, name='class_arm_create'),
    path('classes/<int:pk>/edit/', views.class_arm_edit, name='class_arm_edit'),

    # Subjects
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/create/', views.subject_create, name='subject_create'),
    path('subjects/<int:pk>/edit/', views.subject_edit, name='subject_edit'),

]