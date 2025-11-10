import csv
from datetime import datetime, timedelta
from io import StringIO
import re
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import ExternalBarcode, Item
from .forms import CSVImportForm, ItemCreateForm


def inventory_dashboard(request):
    """Main inventory management dashboard"""
    return render(request, 'app/dash.html')


def dash_stats(request):
    """HTMX endpoint for dashboard statistics"""
    total_items = Item.objects.filter(deleted=False).count()
    # Count containers (items that have children)
    container_count = Item.objects.filter(deleted=False, children__isnull=False).distinct().count()
    context = {'total_items': total_items, 'container_count': container_count}
    return render(request, 'app/dash.html#dash-stats-cards', context)


def scan_redirect(request):
    """Handle barcode scanning - redirect to item, to action page, or new item page"""
    code = request.GET.get('barcode', '').strip()

    # If q is empty or missing, return 404
    if not code:
        raise Http404("No barcode provided")

    if item := Item.from_any_barcode(code):
        # If either way we found an item, redirect to its detail page
        # Update last_scanned_at timestamp with UTC datetime
        item.last_scanned_at = datetime.now(ZoneInfo('UTC'))
        item.save()
        # Store the scanned item ID in session for action views
        # FIXME: Ditch use of session by modifying the scan barcode text input form to have a hidden field
        # for the last scanned barcode, if and only if the last thing we scanned was a valid barcode.
        request.session['last_scanned_item_id'] = item.id
        return redirect(item)

    # So we don't have an item.  Check if this is an action barcode (e.g., V=AUDIT)
    action_match = re.match(f"^{re.escape(settings.BARCODE_VERB_PREFIX)}(.+)$", code)
    if action_match:
        action_name = action_match.group(1).lower()
        id_of_last_scanned_item = request.session.get('last_scanned_item_id')
        if id_of_last_scanned_item:
            try:
                # Verify the item exists
                Item.objects.get(id=id_of_last_scanned_item)
                # Redirect to the action URL instead of calling the function directly
                url = reverse('app:item_action', kwargs={"pk": id_of_last_scanned_item, "action": action_name})
                return redirect(url)
            except Item.DoesNotExist:
                raise Http404(f"Item {id_of_last_scanned_item} for action '{action_name}' not found")
        # No last scanned item found - return 400 Bad Request
        return HttpResponseBadRequest(f"Action '{action_name}' requires a previously scanned item")

    # Perhaps it's a barcode in our internal format, but we've never seen it before
    if Item.get_possible_item_id_from_internal_barcode(code):
        # Redirect to new item page with this ID pre-filled
        url = reverse('app:new_item', query={'barcode': code})
        return HttpResponseRedirect(url)

    # Perhaps it's a search (starts with '/')
    if code.startswith('/'):
        query = code[1:]  # Strip leading '/'
        url = reverse('app:item_list') + '?' + urlencode({'q': query})
        return HttpResponseRedirect(url)

    # Perhaps it's an external barcode we haven't seen before for an existing item
    url = reverse('app:new_external_barcode', query={'barcode': code})
    return HttpResponseRedirect(url)


def item_action(request, pk, action_name):
    """Generic handler for item actions."""
    action_func = _action_registry.get(action_name)
    if action_func:
        return action_func(request, pk)
    raise Http404(f"Action '{action_name}' not found")


def create_new_external_barcodes_for_item(item, external_barcodes_text):
    """Helper function to create ExternalBarcode objects from textarea input"""
    barcodes = [b.strip() for b in external_barcodes_text.split('\n') if b.strip()]
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
    barcode = request.GET.get('barcode', '').strip()
    if not barcode:
        return HttpResponseBadRequest("Internal barcode for item is required")
    possible_new_id = Item.get_possible_item_id_from_internal_barcode(barcode)
    if not possible_new_id:
        return HttpResponseBadRequest("Internal barcode for item is not in required format")
    item = Item.from_barcode(barcode)
    if item:
        return HttpResponseBadRequest("Item already exists")

    errors = None

    if request.method == 'POST':
        # FIXME: Where do we patch the id from the barcode into the item?
        form = ItemCreateForm(request.POST or None)
        if form.is_valid():
            with transaction.atomic():
                item = form.save(commit=False)
                item.last_scanned_at = datetime.now(ZoneInfo('UTC'))
                # Here's where we patch in the id so it doesn't have an existing one
                item.pk = possible_new_id
                item.save()

                # Save the selected parent to session for next time
                parent = form.cleaned_data.get('parent')
                if parent:
                    request.session['last_used_parent_id'] = parent.id
                elif 'last_used_parent_id' in request.session:
                    # If no parent selected, remove the stored parent
                    del request.session['last_used_parent_id']

                # Handle external barcodes from the textarea
                external_barcodes_text = form.cleaned_data.get('external_barcodes', '').strip()
                if external_barcodes_text:
                    create_new_external_barcodes_for_item(item, external_barcodes_text)

                return redirect(item)
        else:
            errors = form.errors
    else:
        # GET request - check for external barcode parameter
        external_barcode = request.GET.get('external', '').strip()
        initial_data = {}
        if external_barcode:
            initial_data['external_barcodes'] = external_barcode

        # Set parent from session if available
        last_parent_id = request.session.get('last_used_parent_id')
        if last_parent_id:
            try:
                last_parent = Item.objects.get(id=last_parent_id, deleted=False)
                initial_data['parent'] = last_parent
            except Item.DoesNotExist:
                # If the parent no longer exists, remove it from session
                if 'last_used_parent_id' in self.request.session:
                    del request.session['last_used_parent_id']

        form = ItemCreateForm(initial=initial_data)

    context = {
        'barcode': barcode,
        'form': form,
    }
    return render(request, 'app/new_item.html', context)


def new_external_barcode(request):
    """Display a form for creating a new item with an external barcode"""
    external_barcode_str = request.GET.get('barcode', '').strip()
    if not external_barcode_str:
        return HttpResponseBadRequest("External barcode is required")

    if request.method == 'POST':
        item_barcode = request.POST.get('item_barcode', '').strip()
        if not item_barcode:
            return HttpResponseBadRequest("Item barcode is required")
        # Check if item with this barcode already exists
        item = Item.from_barcode(item_barcode)
        if not item:
            # Check if this could be a valid new item barcode
            possible_new_id = Item.get_possible_item_id_from_internal_barcode(item_barcode)
            if possible_new_id:
                # Redirect to new_item with both barcode and external parameters
                url = reverse('app:new_item', query={'barcode': item_barcode, 'external': external_barcode_str})
                return HttpResponseRedirect(url)
            return HttpResponseBadRequest("Item not found")

        create_new_external_barcodes_for_item(item, external_barcode_str)
        item.last_scanned_at = datetime.now(ZoneInfo('UTC'))
        item.save()

        return redirect(item)

    lcsc = None
    match = re.search(r'pc:(C\d+),', external_barcode_str)
    if match:
        lcsc = match.group(1)  # Extract LCSC part

    context = {
        'lcsc': lcsc,
        'barcode': external_barcode_str,
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
    updated_when_scanned = abs(item.updated_at - item.last_scanned_at) < timedelta(seconds=1)
    context = {
        'item': item,
        'tree_structure': tree_structure,
        'updated_when_scanned': updated_when_scanned,
    }

    return render(request, 'app/item_detail.html', context)


def import_items(request):
    """Handle CSV import of items"""
    # FIXME: Move this to a separate file, e.g., import_items.py
    if request.method == 'POST':
        form = CSVImportForm(request.POST)
        ctx = {'form': form}

        if form.is_valid():
            csv_data = form.cleaned_data['csv_data']
            save_requested = form.cleaned_data['save']
            ctx['csv_data'] = csv_data

            try:
                # Parse CSV data
                reader = csv.DictReader(StringIO(csv_data), delimiter='\t')

                # Validate headers
                expected_headers = {'ID', 'In', 'Name', 'Desc'}
                actual_headers = set(reader.fieldnames)
                if not expected_headers.issubset(actual_headers):
                    form.add_error(
                        'csv_data', f"Missing required headers: {', '.join(expected_headers - actual_headers)}"
                    )
                    return render(request, 'app/import.html', {'form': form})

                # Process and validate each row
                validated_items = []
                errors = []
                last_parent = None
                total_items = 0
                root_items = 0
                child_items = 0
                created_count = 0

                with transaction.atomic():
                    for i, row in enumerate(reader):
                        n = i + 2  # Account for header row
                        # Map CSV fields to model fields
                        mapper = {'ID': 'id', 'Name': 'name', 'Desc': 'description', 'In': 'parent_id'}
                        print(f'{row=}')

                        data = {v: (row[k] if row[k] else '').strip() for k, v in mapper.items()}

                        if not data['name'].strip():
                            continue  # Skip rows without a name

                        # Determine parent based on 'In' field
                        in_field = data['parent_id']
                        parent = None
                        if in_field == '-root-':
                            parent = None
                            last_parent = None
                        elif in_field.isdigit():
                            parent = in_field
                            last_parent = parent
                        elif not in_field:
                            parent = last_parent
                        else:
                            errors.append(f"Line {n}: Invalid 'In' field value: {in_field}")
                            continue

                        # Update parent in data
                        data['parent_id'] = parent

                        validated_items.append(data)
                        total_items += 1
                        if data['parent_id']:
                            child_items += 1
                        else:
                            root_items += 1
                        if save_requested:
                            # If save was requested, save the items
                            try:
                                item = Item.objects.get(pk=data['id'])
                            except Item.DoesNotExist:
                                item = Item()
                                item.id = data['id']
                            for k, v in data.items():
                                if k != 'id':
                                    setattr(item, k, v)
                            item.save()
                            created_count += 1

                    if errors:
                        if save_requested:
                            transaction.set_rollback(True)

                        # Show errors and allow correction
                        ctx['errors'] = errors
                    else:
                        # All validation passed
                        ctx['validated_items'] = validated_items
                        ctx['stats'] = {
                            'total_items': total_items,
                            'root_items': root_items,
                            'child_items': child_items,
                        }
                        ctx['save'] = True

                        if save_requested:
                            # Redirect to item list with success message
                            msg = {
                                'message': f'Successfully imported {created_count} items',
                                'message_type': 'success',
                            }
                            url = reverse('app:item_list', query=msg)
                            return redirect(url)

                return render(request, 'app/import.html', ctx)

            except Exception as e:
                form.add_error('csv_data', f"Error parsing CSV: {e}")
                return render(request, 'app/import.html', ctx)

        # Form is invalid
        return render(request, 'app/import.html', ctx)

    else:
        # GET request - show empty form
        form = CSVImportForm()
        return render(request, 'app/import.html', {'form': form})
