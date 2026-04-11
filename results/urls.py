from django.urls import path
from . import views

app_name = "results"

urlpatterns = [
    path('manage/', views.report_card_management, name='report_card_management'),
    path('student/<int:student_id>/update/', views.update_student_results, name='update_student_results'),
    path('generate/', views.generate_class_report_cards, name='generate_class_report_cards'),
    path('card/<int:pk>/view/', views.view_report_card, name='view_report_card'),
    path('student/<int:student_id>/transcript/', views.view_transcript, name='view_transcript'),
    path('all-results/', views.all_student_results, name='all_student_results'),
    path('releases/', views.manage_releases, name='manage_releases'),
    path('releases/toggle/', views.toggle_release, name='toggle_release'),
    path('my-results/', views.student_report_card_list, name='student_report_card_list'),
]
