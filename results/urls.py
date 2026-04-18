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
    path('card/<int:pk>/admin-update/', views.admin_update_report_card, name='admin_update_report_card'),
    path('my-results/', views.student_report_card_list, name='student_report_card_list'),

    # Analytics APIs
    path('api/student-performance/<int:session_id>/', views.student_performance_summary_api, name='student_performance_summary_api'),
    path('api/insights/student/<int:session_id>/<int:term_id>/<int:student_id>/', views.student_performance_api, name='student_performance_api'),
    path('api/insights/class/<int:session_id>/<int:term_id>/<int:class_arm_id>/', views.class_performance_api, name='class_performance_api'),
    path('api/insights/school/<int:session_id>/<int:term_id>/', views.school_performance_api, name='school_performance_api'),
    # UI Routes
    path('insights/staff/', views.staff_performance_insights, name='staff_performance_insights'),
    path('insights/student/', views.student_performance_insights, name='student_performance_insights'),
    
    # Generic Analytics API
    path('api/performance/class/<int:class_arm_id>/', views.class_performance_summary_api, name='class_performance_summary_api'),
]
