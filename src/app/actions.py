from datetime import datetime
import re
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import path, reverse  # , Resolver404, get_resolver
from .models import Item


# Registry to store action functions
_action_registry = {}

# # Registry to store action URL patterns
# _action_urlpatterns = []


def action(func):
    """Decorator to mark a function as an action and register it."""
    action_name = func.__name__.lower()
    _action_registry[action_name] = func

    return func


def handle_action(request, pk, action):
    """Handle an action for a specific item."""
    action_name = action.lower()
    action_func = _action_registry.get(action_name)
    if action_func:
        return action_func(request, pk)
    else:
        return HttpResponse(f"Action '{action_name}' not found", status=404)


@action
def move(request, pk):
    """Move an item to a different container."""
    src_item = get_object_or_404(Item, pk=pk)

    context = {
        'item': src_item,
    }

    if request.method == 'POST':
        destination_barcode = request.POST.get('barcode', '').strip()

        # Determine destination from barcode
        if not destination_barcode:
            context['error'] = "Creating top-level items can't be done with this form."

            return render(request, 'app/move.html', context)

        # Find destination item by barcode
        destination_item = Item.from_barcode(destination_barcode)
        if not destination_item:
            context['error'] = f"Destination item with barcode '{destination_barcode}' not found"
            return render(request, 'app/move.html', context)

        # Check if moving would create a cycle
        if src_item.is_ancestor_of(destination_item):
            context['error'] = f"Cannot move item into its own descendant: {destination_item.path}"
            return render(request, 'app/move.html', context)

        with transaction.atomic():
            destination_item.last_scanned_at = src_item.last_scanned_at = datetime.now(ZoneInfo('UTC'))
            src_item.parent = destination_item

            destination_item.save()
            src_item.save()

            # FIXME: Create an ItemHistory record for the move.

            # FIXME: Add a toast to say result.
            # One toast for "didn't move" and one for "moved to X".

        return redirect(src_item)

    return render(request, 'app/move.html', context)


def move_container_options(request, pk):
    """HTMX endpoint for container options in move form"""
    item = get_object_or_404(Item, pk=pk)
    show_all = 'show_all' in request.GET
    barcode_input = request.GET.get('barcode_input', '').strip()

    # Get IDs of all children items
    our_children = [child.id for child in item.get_all_children()]

    # Get all items that can hold items (excluding the current item and its descendants)
    items = Item.objects.filter(deleted=False)
    # Exclude ourself.
    items = items.exclude(id=item.id)
    # Exclude our descendants (this will prevent graph cycles, which would be ugly!)
    if our_children:
        items = items.exclude(id__in=our_children)

    # Filter to only containers if requested
    if not show_all:
        items = items.filter(children__isnull=False).distinct()

    # Sort items by path
    items = sorted(items, key=lambda c: c.path)

    context = {
        'item': item,
        'items': items,
        'barcode_input': barcode_input,
    }

    return render(request, 'app/move.html#item-move-partial', context)


@action
def delete(request, pk):
    """A placeholder view for deleting items."""
    return HttpResponse(f"Delete action executed for item {pk}")


@action
def audit(request, pk):
    """A placeholder view for auditing items."""
    return HttpResponse(f"Audit action executed for item {pk}")


@action
def bulk_move(request, pk):
    """A placeholder view for bulk moving items."""
    return HttpResponse(f"Bulk move action executed for item {pk}")


@action
def queue_print(request, pk):
    """A placeholder view for queuing print jobs."""
    return HttpResponse(f"Print job queued for item {pk}")
