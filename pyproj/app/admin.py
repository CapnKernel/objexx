from django.contrib import admin
from .models import Item, ExternalBarcode, ItemHistory


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'barcode_string', 'name', 'parent', 'deleted', 'created_at']
    list_filter = ['deleted', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ExternalBarcode)
class ExternalBarcodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'item', 'barcode_type', 'created_at']
    list_filter = ['barcode_type', 'created_at']
    search_fields = ['code', 'item__name']
    readonly_fields = ['created_at']


@admin.register(ItemHistory)
class ItemHistoryAdmin(admin.ModelAdmin):
    list_display = ['item', 'action', 'user', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['item__name', 'description']
    readonly_fields = ['timestamp']
