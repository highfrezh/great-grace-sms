from django.urls import path
from . import views

app_name = 'staff'

# In staff/urls.py
urlpatterns = [
    path('', views.staff_list, name='staff_list'),
    path('create/', views.staff_create, name='staff_create'),
    path('<int:pk>/', views.staff_detail, name='staff_detail'),
    path('<int:pk>/edit/', views.staff_edit, name='staff_edit'),
    path('<int:pk>/deactivate/', views.staff_deactivate, name='staff_deactivate'),
    path('<int:pk>/activate/', views.staff_activate, name='staff_activate'),
    path('<int:pk>/delete/', views.staff_delete, name='staff_delete'),  # Add this
    path('<int:pk>/reset-password/', views.staff_reset_password, name='staff_reset_password'),
]