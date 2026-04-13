from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('principal/', views.principal_dashboard, name='principal_dashboard'),
    path('password-change/', views.password_change_view, name='password_change'),
]