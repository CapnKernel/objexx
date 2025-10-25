from django.shortcuts import render
from .models import Item


def inventory_dashboard(request):
    """Main inventory management dashboard"""
    total_items = Item.objects.filter(deleted=False).count()
    context = {'total_items': total_items}
    return render(request, 'app/dash.html', context)


def total_items_partial(request):
    """HTMX endpoint for total items partial"""
    total_items = Item.objects.filter(deleted=False).count()
    context = {'total_items': total_items}
    return render(request, 'app/dash.html#total-items-card', context)
