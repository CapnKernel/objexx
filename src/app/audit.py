"""Views for the item audit workflow.

Each page/partial gets its own URL and view, so the template can point each
htmx request at exactly the endpoint that renders the fragment it wants to
swap.  The shared audit state (``scanned_ids`` and ``unresolved``) is carried
between partials via hidden fields / query params and re-parsed on every
request by :func:`_audit_context`.

Naming follows the django-htmx-fun pattern: ``_page`` views return a full
page (GET only), ``_hx`` views return an HTML fragment via GET, and
``_hxpost`` views return an HTML fragment via POST.  One URL per method.

Pages/partials:
  * ``audit_page``            — the scanning page (GET), full page.  On load it
                                ``hx-get``s the ``#audit-list`` fragment.
  * ``audit_list_hx``         — the scanning fragment (GET), ``#audit-list``.
  * ``audit_list_hxpost``     — scan/unscan actions (POST), ``#audit-list``.
  * ``audit_confirm_lost_hx`` — the "declare lost" form (GET),
                                ``#audit-confirm-lost``.
  * ``audit_confirm_lost_hxpost`` — the "declare lost" submission (POST),
                                ``#audit-complete``.
  * ``audit_complete_hxpost`` — the review/recheck page (POST),
                                ``#audit-complete``.
"""

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django_htmx.http import HttpResponseClientRedirect

from .models import Item, ItemHistory


def _ids_to_items(id_str):
    """Convert a comma-separated string of item IDs into a list of Items."""
    ids = [x.strip() for x in id_str.split(',') if x.strip().isdigit()]
    return list(Item.objects.filter(pk__in=ids))


def _classify_unresolved(item, unresolved_barcodes):
    """Separate unresolved barcodes into set-aside, unknown and possible.

    Returns a dict with keys 'set_aside_items', 'unknown_barcodes' and
    'possible_barcodes', each holding tuples of (value, message) where value
    is an Item (for set-aside) or a barcode string (for unknown/possible),
    and message explains the current status.  Messages are derived from the
    current DB state on every request, so a recheck naturally reflects
    items created or associated in another tab.
    """
    set_aside = []
    unknown = []
    possible = []
    for barcode in unresolved_barcodes:
        found = Item.from_any_barcode(barcode)
        if found:
            if found.parent == item:
                set_aside.append((found, f'Now present in {item.name}'))
            else:
                set_aside.append((found, f'Now part of {found.name} ({found.barcode_string})'))
        elif Item.get_possible_item_id_from_internal_barcode(barcode):
            possible.append((barcode, 'Possible new item'))
        else:
            unknown.append((barcode, 'Unknown barcode'))
    return {
        'set_aside_items': set_aside,
        'unknown_barcodes': unknown,
        'possible_barcodes': possible,
    }


def _audit_context(request, item):
    """Parse the shared audit state and build the base template context.

    The state is carried between partials via two hidden fields:
      * scanned_ids  — ids of children confirmed present.
      * unresolved   — comma-separated barcodes that were scanned but not
                       confirmed as present (set-aside, unknown, possible).
    The unresolved list is the single source of truth; the three display
    categories are re-derived from it on every request.
    """
    scanned_items = _ids_to_items(request.POST.get('scanned_ids', request.GET.get('scanned_ids', '')))
    unresolved_barcodes = [
        b.strip() for b in request.POST.get('unresolved', request.GET.get('unresolved', '')).split(',') if b.strip()
    ]

    children = item.children.all()
    context = _classify_unresolved(item, unresolved_barcodes)
    context.update(
        {
            'item': item,
            'children': children,
            'unscanned': [c for c in children if c not in scanned_items],
            'scanned_items': scanned_items,
            'unresolved': unresolved_barcodes,
        }
    )
    return context


def _get_auditable_item(request, pk):
    """Fetch the item and reject auditing anything in the Lost hierarchy."""
    item = get_object_or_404(Item, pk=pk)
    lost_item = Item.get_lost_item()
    if lost_item and lost_item.is_ancestor_of(item):
        messages.error(request, 'Cannot audit items in the Lost hierarchy.')
        return None
    return item


def _redirect_to_item(request, pk):
    """Redirect to the item detail page.

    For htmx requests this is a client-side redirect (``HX-Redirect``) so the
    browser navigates instead of swapping a full page into the target; for
    plain requests it is a normal HTTP redirect.
    """
    url = reverse('app:item_detail', kwargs={'pk': pk})
    if request.htmx:
        return HttpResponseClientRedirect(url)
    return redirect(url)


@require_GET
def audit_page(request, pk):
    """Render the audit scanning page (the full page).

    The page shell is returned immediately; the ``#audit-list`` fragment is
    fetched separately via ``hx-get`` on load (see ``audit_list_hx``).
    """
    item = _get_auditable_item(request, pk)
    if item is None:
        return redirect('app:item_detail', pk=pk)

    context = {'item': item}
    return render(request, 'app/audit.html', context)


@require_GET
def audit_list_hx(request, pk):
    """Render the audit-list fragment (the scanning view)."""
    item = _get_auditable_item(request, pk)
    if item is None:
        return _redirect_to_item(request, pk)

    context = _audit_context(request, item)
    return render(request, 'app/audit.html#audit-list', context)


@require_POST
def audit_list_hxpost(request, pk):
    """Handle a scan or unscan and return the audit-list partial."""
    item = _get_auditable_item(request, pk)
    if item is None:
        return _redirect_to_item(request, pk)

    context = _audit_context(request, item)
    scanned_items = context['scanned_items']
    children = context['children']
    unresolved_barcodes = context['unresolved']

    unscan_id = request.POST.get('unscan', '').strip()
    if unscan_id and unscan_id.isdigit():
        scanned_items[:] = [c for c in scanned_items if c.pk != int(unscan_id)]
    else:
        barcode = request.POST.get('barcode', '').strip()
        scanned_item = Item.from_any_barcode(barcode)

        if scanned_item and scanned_item.parent == item:
            if scanned_item not in scanned_items:
                scanned_items.append(scanned_item)
            scanned_item.mark_scanned()
            messages.success(request, f'Scanned: {scanned_item.name}')
        else:
            # Not a present child — record it in the unresolved list.
            if barcode not in unresolved_barcodes:
                unresolved_barcodes.append(barcode)
            if scanned_item:
                messages.warning(
                    request, f'{scanned_item.name} is not in {item.name}. Set it aside for later processing.'
                )
            elif Item.get_possible_item_id_from_internal_barcode(barcode):
                messages.info(request, f'Possible new item: {barcode}')
            else:
                messages.warning(request, f'Unknown barcode: {barcode}')

    # Re-derive the display categories from the updated unresolved list
    context.update(_classify_unresolved(item, unresolved_barcodes))
    context['unscanned'] = [c for c in children if c not in scanned_items]
    return render(request, 'app/audit.html#audit-list', context)


@require_GET
def audit_confirm_lost_hx(request, pk):
    """Render the confirm-lost partial."""
    item = _get_auditable_item(request, pk)
    if item is None:
        return redirect('app:item_detail', pk=pk)

    context = _audit_context(request, item)
    context['unscanned'] = [c for c in context['children'] if c not in context['scanned_items']]
    lost_item = Item.get_lost_item()
    context['lost_boxes'] = list(lost_item.children.order_by('-last_updated_at')) if lost_item else []
    return render(request, 'app/audit.html#audit-confirm-lost', context)


@require_POST
def audit_confirm_lost_hxpost(request, pk):
    """Move unscanned items to a lost box and show the audit-complete summary.

    The only DB change is moving unscanned items to the lost box, done
    atomically in one transaction. Set-aside items and unknown barcodes
    are listed in the completion partial for the user to deal with later.
    """
    item = _get_auditable_item(request, pk)
    if item is None:
        return _redirect_to_item(request, pk)

    context = _audit_context(request, item)
    scanned_items = context['scanned_items']
    children = context['children']

    lost_box_id = request.POST.get('lost_box', '')
    unscanned = [c for c in children if c not in scanned_items]

    # Resolve/create the lost box if there are unscanned items to move
    lost_box = None
    if unscanned:
        if lost_box_id == 'new':
            lost_box = Item.create_lost_box()
            if lost_box is None:
                messages.error(request, 'Cannot create lost box: root Lost item not found.')
                return _redirect_to_item(request, pk)
        else:
            try:
                lost_box = Item.objects.get(pk=int(lost_box_id))
            except (ValueError, Item.DoesNotExist):
                messages.error(request, 'Invalid lost box selected.')
                return _redirect_to_item(request, pk)

        with transaction.atomic():
            for child in unscanned:
                child.move_to(lost_box)

    # Build completion summary
    parts = []
    if unscanned:
        parts.append(f'Moved {len(unscanned)} item(s) to {lost_box.name}')
    if not parts:
        parts.append('No unscanned items to move')
    summary = '. '.join(parts) + '.'

    # Log the audit itself, even if no items were moved.
    ItemHistory.objects.create(
        item=item,
        action='AUDIT',
        description=f'Audited {item.name}: {summary}',
        metadata={
            'scanned': [c.id for c in scanned_items],
            'moved': [c.id for c in unscanned],
        },
    )

    messages.success(request, summary)

    context['unscanned'] = unscanned
    context['lost_box'] = lost_box
    return render(request, 'app/audit.html#audit-complete', context)


@require_POST
def audit_complete_hxpost(request, pk):
    """Render the audit-complete partial for review/recheck.

    The classification is already derived in the base context, so no
    re-derivation is needed here.
    """
    item = _get_auditable_item(request, pk)
    if item is None:
        return _redirect_to_item(request, pk)

    context = _audit_context(request, item)
    context['lost_box'] = None
    return render(request, 'app/audit.html#audit-complete', context)
