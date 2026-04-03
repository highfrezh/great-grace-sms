from django.urls import path
from . import views

app_name = "students"

urlpatterns = [
    path('', views.student_list, name='student_list'),
    path('create/', views.student_create, name='student_create'),
    path('<int:pk>/', views.student_detail, name='student_detail'),
    path('<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('<int:pk>/deactivate/', views.student_deactivate, name='student_deactivate'),
    path('<int:pk>/delete/', views.student_delete, name='student_delete'),
    path('bulk-import/', views.student_bulk_import, name='student_bulk_import'),
    path('attendance/', views.attendance_mark, name='attendance_mark'),
    path('attendance/<int:pk>/', views.attendance_mark, name='attendance_mark'),
    path('attendance/', views.attendance_mark, name='attendance_mark_default'),
]
