from django.shortcuts import render, get_object_or_404
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


def item_list(request):
    """Display a table of all items with links to details"""
    items = Item.objects.filter(deleted=False).select_related('parent').order_by('name')
    context = {'items': items}
    return render(request, 'app/item_list.html', context)


def item_detail(request, pk):
    """Display details for a specific item"""
    item = get_object_or_404(Item, pk=pk)
    context = {'item': item}
    return render(request, 'app/item_detail.html', context)
