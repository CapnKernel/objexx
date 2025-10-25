from django.urls import path
from . import views

app_name = 'app'

urlpatterns = [
    path('', views.inventory_dashboard, name='inventory_dashboard'),
    path('partials/total-items/', views.total_items_partial, name='total_items_partial'),
]
