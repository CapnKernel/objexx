from django.urls import path
from . import views

app_name = 'app'

urlpatterns = [
    path('', views.inventory_dashboard, name='dash'),
    path('partials/total-items/', views.total_items_partial, name='total_items_partial'),
    path('item/', views.item_list, name='item_list'),
    path('item/<int:pk>/', views.item_detail, name='item_detail'),
]
