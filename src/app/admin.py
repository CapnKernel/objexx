from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from .models import Item, ExternalBarcode, ItemHistory


class ExternalBarcodeInline(admin.TabularInline):
    """Inline admin for ExternalBarcode to show on Item admin page"""

    model = ExternalBarcode
    extra = 1
    readonly_fields = ['created_at', 'admin_link']
    fields = ['admin_link', 'code', 'barcode_type', 'notes', 'created_at']

    def admin_link(self, obj):
        """Create a link to the external barcode's admin page"""
        if obj.pk:
            url = reverse('admin:app_externalbarcode_change', args=[obj.pk])
            return format_html('<a href="{}">Edit</a>', url)
        return "-"

    admin_link.short_description = "Admin"


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'barcode_string', 'name', 'parent', 'deleted', 'created_at']
    list_filter = ['deleted', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ExternalBarcodeInline]

    def save_model(self, request, obj, form, change):
        """Override save_model to set custom ID if provided in query parameter"""
        if not change and 'id' in request.GET:  # Only for new objects, not edits
            try:
                custom_id = int(request.GET['id'])
                # Check if ID is available
                if not Item.objects.filter(id=custom_id).exists():
                    obj.id = custom_id
            except (ValueError, TypeError):
                # If ID is not a valid integer, let Django auto-generate it
                pass

        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        """Override response_add to handle redirect after adding with specific ID"""
        if '_addanother' in request.POST:
            # If "Save and add another" was clicked, redirect back to add page with same ID
            return HttpResponseRedirect(reverse('admin:app_item_add') + f'?id={obj.id}')
        elif '_continue' in request.POST:
            # If "Save and continue editing" was clicked, redirect to change page
            return HttpResponseRedirect(reverse('admin:app_item_change', args=[obj.id]))
        else:
            # Default: redirect to changelist
            return HttpResponseRedirect(reverse('admin:app_item_changelist'))


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
