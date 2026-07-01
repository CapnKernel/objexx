import re
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import ExternalBarcodeForm, ItemCreateForm
from .models import ExternalBarcode, Item


def top(request):
    """Main inventory management dashboard"""
    return render(request, 'app/top.html')


def dash_stats(request):
    """HTMX endpoint for dashboard statistics"""
    total_items = Item.objects.filter(deleted=False).count()
    # Count containers (items that have children)
    container_count = Item.objects.filter(deleted=False, children__isnull=False).distinct().count()
    context = {'total_items': total_items, 'container_count': container_count}
    return render(request, 'app/top.html#dash-stats-cards', context)


def scan_redirect(request):
    """Handle barcode scanning - redirect to item, to action page, or new item page"""
    code = request.GET.get('barcode', '').strip()

    # If q is empty or missing, return 404
    if not code:
        raise Http404('No barcode provided')

    if item := Item.from_any_barcode(code):
        # If either way we found an item, update last_scanned_at and
        # redirect to its detail page
        item.last_scanned_at = timezone.now()
        item.save()
        return redirect(item)

    # So we don't have an item.  Check if this is an action barcode (e.g., V=AUDIT)
    action_match = re.match(f'^{re.escape(settings.BARCODE_VERB_PREFIX)}(.+)$', code)
    if action_match:
        action_name = action_match.group(1).lower()

        item_id = request.GET['item']
        if item_id:
            try:
                # Verify the item exists
                Item.objects.get(id=item_id)
                # Redirect to the action URL instead of calling the function directly
                url = reverse('app:item_action', kwargs={'pk': item_id, 'action': action_name})
                # print(f"Action redirection to {url}")
                return redirect(url)
            except Item.DoesNotExist:
                raise Http404(f"Item {item_id} for action '{action_name}' not found")

        # No last scanned item found - return 400 Bad Request
        return HttpResponseBadRequest(f"Action '{action_name}' requires an item to operate on")

    # Perhaps it's a barcode in our internal format, but we've never seen it before
    if Item.get_possible_item_id_from_internal_barcode(code):
        # Redirect to new item page with this ID pre-filled
        url = reverse('app:new_item', query={'barcode': code})
        return redirect(url)

    # Perhaps it's a search (starts with '/')
    if code.startswith('/'):
        query = code[1:]  # Strip leading '/'
        url = reverse('app:item_list') + '?' + urlencode({'q': query})
        return redirect(url)

    # Perhaps it's an external barcode we haven't seen before for an existing item
    url = reverse('app:new_external_barcode', query={'barcode': code})
    return redirect(url)


def create_new_external_barcodes_for_item(item, external_barcodes_text):
    """Helper function to create ExternalBarcode objects from textarea input"""
    # Don't move these to actions.py, because they don't rely on action barcodes.
    if isinstance(external_barcodes_text, str):
        barcodes = [b.strip() for b in external_barcodes_text.split('\n') if b.strip()]
    else:
        barcodes = list(external_barcodes_text)
    with transaction.atomic():
        for barcode_value in barcodes:
            if item.external_barcodes.filter(code=barcode_value).exists():
                continue  # Skip existing barcodes
            data = {
                'code': barcode_value,
                'item': item,
                'barcode_type': ExternalBarcode.guess_type_from_str(barcode_value),
            }
            external_barcode_object = ExternalBarcode(**data)
            external_barcode_object.save()


def new_item(request):
    """Display a form for creating a new item with a given internal barcode"""
    error_msg = None
    form = None

    barcode = request.GET.get('barcode', '').strip()
    if not barcode:
        error_msg = 'To create a new item, scan an unused internal barcode.'
    elif ExternalBarcode.is_possible_action_barcode(barcode):
        messages.warning(request, 'Action barcodes cannot be added as external barcodes.')
    else:
        # Existing item?
        item = Item.from_barcode(barcode)
        if item:
            # If external barcodes were passed (e.g., from new_external_barcode),
            # add them to the existing item before redirecting.
            external_barcodes_text = request.GET.get('external_barcodes', '').strip()
            if external_barcodes_text:
                create_new_external_barcodes_for_item(item, external_barcodes_text)
            messages.info(request, f"Item with barcode '{barcode}' already exists")
            return redirect(item)

        possible_new_id = Item.get_possible_item_id_from_internal_barcode(barcode)
        if not possible_new_id:
            error_msg = f"Barcode '{barcode}' is not in the required internal format"

    if not error_msg:
        if request.method == 'POST':
            form = ItemCreateForm(request.POST or None)
            if form.is_valid():
                with transaction.atomic():
                    item = form.save(commit=False)
                    item.last_scanned_at = timezone.now()
                    # Here's where we patch in the id so it doesn't get assigned one when we save
                    item.pk = possible_new_id
                    item.save()

                    # Save the selected parent to session for next time
                    parent = form.cleaned_data.get('parent')
                    if parent:
                        # Save parent as the default for the next new item
                        request.session['last_used_parent_id'] = parent.pk
                    elif 'last_used_parent_id' in request.session:
                        # If no parent selected, remove the stored parent
                        del request.session['last_used_parent_id']

                    # Handle external barcodes from the textarea
                    external_barcodes_text = form.cleaned_data.get('external_barcodes', '').strip()
                    external_barcodes = [b.strip() for b in external_barcodes_text.split('\n') if b.strip()]
                    if any(ExternalBarcode.is_possible_action_barcode(b) for b in external_barcodes):
                        messages.warning(request, 'Action barcodes cannot be added as external barcodes.')
                    else:
                        create_new_external_barcodes_for_item(item, external_barcodes)

                    return redirect(item)
        else:
            # GET request - check for external barcode parameter
            # Generate a form pre-seeded with the barcode we scanned, and an external barcode if given.
            initial_data = {}
            external_barcodes = request.GET.get('external_barcodes', '').strip()
            if external_barcodes:
                initial_data['external_barcodes'] = external_barcodes

            # Set parent from session if available
            last_parent_id = request.session.get('last_used_parent_id')
            if last_parent_id:
                try:
                    last_parent = Item.objects.get(id=last_parent_id, deleted=False)
                    initial_data['parent'] = last_parent
                except Item.DoesNotExist:
                    # If the parent no longer exists, remove it from session
                    if 'last_used_parent_id' in request.session:
                        del request.session['last_used_parent_id']

            form = ItemCreateForm(initial=initial_data)
    else:
        messages.error(request, error_msg)

    context = {
        'barcode': barcode,
        'form': form,
    }
    return render(request, 'app/new_item.html', context)


def new_external_barcode(request):
    """Display a form for creating a new item with an external barcode"""
    if request.method == 'POST':
        form = ExternalBarcodeForm(request.POST or None)
        if form.is_valid():
            barcode = form.cleaned_data['barcode']
            pending_raw = form.cleaned_data.get('pending_barcodes', '').strip()
            pending = [b.strip() for b in pending_raw.split('\n') if b.strip()]

            # Check if the scanned barcode is an item barcode (existing or new)
            item = Item.from_any_barcode(barcode)
            if item:
                # Existing.  Add any pending external barcodes to it.
                create_new_external_barcodes_for_item(item, pending)
                item.last_scanned_at = timezone.now()
                item.save()
                return redirect(item)

            # Is it a candidate for a new item?
            possible_new_id = Item.get_possible_item_id_from_internal_barcode(barcode)
            if possible_new_id:
                url = reverse(
                    'app:new_item',
                    query={'barcode': barcode, 'external_barcodes': '\n'.join(pending)},
                )
                return redirect(url)

            # Not an item barcode — treat as another external barcode
            if barcode in pending:
                messages.warning(request, 'Duplicate external barcode, ignored.')
            else:
                if ExternalBarcode.is_possible_action_barcode(barcode):
                    messages.warning(request, 'Action barcodes cannot be added as external barcodes.')
                else:
                    pending.append(barcode)

            # Re-render with updated pending list
            pending_text = '\n'.join(pending)
            form = ExternalBarcodeForm(initial={'pending_barcodes': pending_text})
    else:
        barcode = request.GET.get('barcode', '').strip()
        pending = [barcode]
        if not barcode:
            messages.error(request, 'External barcode is required')
            return redirect('app:top')
        form = ExternalBarcodeForm(initial={'pending_barcodes': barcode})

    lcsc = None
    for bc in pending:
        lcsc = ExternalBarcode.extract_lcsc_part_number(bc)
        if lcsc:
            break

    back_url = request.META.get('HTTP_REFERER', reverse('app:top'))

    context = {
        'lcsc': lcsc,
        'barcode': barcode,
        'pending_barcodes': pending,
        'form': form,
        'back_url': back_url,
    }

    return render(request, 'app/new_external_barcode.html', context)


def item_list(request):
    query = request.GET.get('q', '').strip()

    items = Item.objects.filter(deleted=False).select_related('parent').order_by('id')
    if query:
        filter = Q(name__icontains=query)
        filter |= Q(description__icontains=query)
        filter |= Q(external_barcodes__code__icontains=query)
        items = items.filter(filter).distinct()

    title = 'Search' if query else 'All Items'

    context = {
        'items': items,
        'q': query,
        'title': title,
        'barcode_value': f'/{query}' if query else '',
    }

    return render(request, 'app/item_list.html', context)


def item_detail(request, pk):
    """Display details for a specific item"""
    item = get_object_or_404(Item, pk=pk)
    tree_structure = item.get_contained_tree() if item.is_container else None
    updated_when_scanned = item.last_scanned_at is not None and abs(
        item.last_updated_at - item.last_scanned_at
    ) < timedelta(seconds=1)
    context = {
        'item': item,
        'tree_structure': tree_structure,
        'updated_when_scanned': updated_when_scanned,
    }

    return render(request, 'app/item_detail.html', context)
