from django.urls import path
from . import views

app_name = 'app'

urlpatterns = [
    path('', views.inventory_dashboard, name='dash'),
    path('partials/dash-stats/', views.dash_stats, name='dash_stats'),
    path('item/', views.item_list, name='item_list'),
    path('item/<int:pk>/', views.item_detail, name='item_detail'),
    path('item/new/', views.new_item, name='new_item'),
    path('scan/', views.scan_redirect, name='scan_redirect'),
    path('import/', views.import_items, name='import_items'),
]
