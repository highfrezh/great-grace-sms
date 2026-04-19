from django.urls import path
from . import views

app_name = 'promotions'

urlpatterns = [
    path('', views.promotion_dashboard, name='promotion_dashboard'),
    path('worksheet/<int:class_arm_id>/<int:target_session_id>/', views.promotion_worksheet, name='promotion_worksheet'),
    path('process/', views.process_bulk_promotion, name='process_bulk_promotion'),
]
