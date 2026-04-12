from django.urls import path
from . import views

app_name = 'schemes'

urlpatterns = [
    path('', views.scheme_list, name='scheme_list'),
    path('upload/', views.scheme_create, name='scheme_create'),
    path('<int:pk>/edit/', views.scheme_edit, name='scheme_edit'),
    path('<int:pk>/delete/', views.scheme_delete, name='scheme_delete'),
    
    # AJAX
    path('ajax/load-subjects/', views.load_subjects, name='ajax_load_subjects'),
]
