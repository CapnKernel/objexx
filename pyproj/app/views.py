import re
from urllib.parse import urlencode

from django.conf import settings
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse


from .models import ExternalBarcode, Item


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


def scan_redirect(request):
    """Handle barcode scanning - redirect to item or new item page"""
    code = request.GET.get('barcode', '').strip()

    # If q is empty or missing, return 404
    if not code:
        raise Http404("No barcode provided")

    # Try to find item by internal barcode using regex
    match = re.match(f"^{re.escape(settings.BARCODE_PREFIX)}(\\d+)$", code)
    if match:
        try:
            item = Item.objects.get(id=match.group(1))
            # return redirect('app:item_detail', pk=item.id)
            return redirect(item)
        except Item.DoesNotExist:
            pass

    # Try to find item by external barcode
    try:
        external_barcode = ExternalBarcode.objects.get(code=code)
        return redirect(external_barcode.item)
    except ExternalBarcode.DoesNotExist:
        pass

    # If no item found (could be new!), redirect to new item page
    url = reverse('app:new_item', query={'barcode': code})
    return HttpResponseRedirect(url)


def new_item(request):
    """Display a form for creating a new item"""
    barcode = request.GET.get('barcode', '').strip()
    context = {'barcode': barcode}
    return render(request, 'app/new_item.html', context)


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
