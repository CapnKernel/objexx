from django.urls import path

from . import actions, audit, import_items, views

app_name = 'app'

urlpatterns = [
    path('', views.top, name='top'),
    path('partials/dash-stats/', views.dash_stats, name='dash_stats'),
    path('partials/messages/', views.messages_partial, name='messages_partial'),
    path('scan/', views.scan_redirect, name='scan_redirect'),
    path('import/', import_items.import_items, name='import_items'),
    path('new_external_barcode/', views.new_external_barcode, name='new_external_barcode'),
    path('item/<int:pk>/audit_page/', audit.audit_page, name='audit_page'),
    path('item/<int:pk>/audit_list_hx/', audit.audit_list_hx, name='audit_list_hx'),
    path('item/<int:pk>/audit_list_hxpost/', audit.audit_list_hxpost, name='audit_list_hxpost'),
    path('item/<int:pk>/audit_confirm_lost_hx/', audit.audit_confirm_lost_hx, name='audit_confirm_lost_hx'),
    path(
        'item/<int:pk>/audit_confirm_lost_hxpost/',
        audit.audit_confirm_lost_hxpost,
        name='audit_confirm_lost_hxpost',
    ),
    path('item/<int:pk>/audit_complete_hxpost/', audit.audit_complete_hxpost, name='audit_complete_hxpost'),
    path('item/<int:pk>/<slug:action>/', actions.item_action, name='item_action'),
    path('item/<int:pk>/', views.item_detail, name='item_detail'),
    path(
        'item/<int:pk>/partials/move-container-options/', actions.move_container_options, name='move_container_options'
    ),
    path('item/new/', views.new_item_page, name='new_item'),
    path('item/new_hxpost/', views.new_item_hxpost, name='new_item_hxpost'),
    path('item/', views.item_list, name='item_list'),
]
