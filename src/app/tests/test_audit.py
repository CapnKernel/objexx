from django.conf import settings
from django.urls import reverse
from pytest_django.asserts import assertContains, assertRedirects

from ..models import ExternalBarcode, Item, ItemHistory


class TestAuditPage:
    def test_audit_page_shows_children(self, authed_client):
        """GET to audit page shows all direct children."""
        container = Item.objects.create(name='Shelf')
        child1 = Item.objects.create(name='Item A', parent=container)
        child2 = Item.objects.create(name='Item B', parent=container)

        response = authed_client.get(reverse('app:audit_list_hx', kwargs={'pk': container.pk}))

        assertContains(response, 'Item A')
        assertContains(response, 'Item B')
        assertContains(response, child1.barcode_string)
        assertContains(response, child2.barcode_string)

    def test_audit_page_empty_container(self, authed_client):
        """Audit page for an empty container shows appropriate message."""
        container = Item.objects.create(name='Empty Shelf')

        response = authed_client.get(reverse('app:audit_list_hx', kwargs={'pk': container.pk}))

        assertContains(response, 'This container is empty')

    def test_audit_page_shows_progress(self, authed_client):
        """Audit page shows progress bar with correct counts."""
        container = Item.objects.create(name='Shelf')
        Item.objects.create(name='Item A', parent=container)
        Item.objects.create(name='Item B', parent=container)
        Item.objects.create(name='Item C', parent=container)

        response = authed_client.get(reverse('app:audit_list_hx', kwargs={'pk': container.pk}))

        assertContains(response, '0 / 3 scanned')


class TestAuditScanning:
    def test_scan_valid_child(self, authed_client):
        """POST with a valid child barcode removes it from unscanned list."""
        container = Item.objects.create(name='Shelf')
        child1 = Item.objects.create(name='Item A', parent=container)
        child2 = Item.objects.create(name='Item B', parent=container)

        response = authed_client.post(
            reverse('app:audit_list_hxpost', kwargs={'pk': container.pk}),
            {'barcode': child1.barcode_string, 'scanned_ids': ''},
            HTTP_HX_REQUEST='true',
        )

        # Should show 1 / 2 scanned
        assertContains(response, '1 / 2 scanned')
        # Item B should still appear in unscanned list
        assertContains(response, 'Item B')
        # Item A should appear in scanned count
        assertContains(response, 'Scanned Items (1)')

    def test_scan_updates_last_scanned_at(self, authed_client):
        """Scanning a child updates its last_scanned_at."""
        container = Item.objects.create(name='Shelf')
        child = Item.objects.create(name='Item A', parent=container)

        assert child.last_scanned_at is None

        authed_client.post(
            reverse('app:audit_list_hxpost', kwargs={'pk': container.pk}),
            {'barcode': child.barcode_string, 'scanned_ids': ''},
            HTTP_HX_REQUEST='true',
        )

        child.refresh_from_db()
        assert child.last_scanned_at is not None

    def test_scan_multiple_children(self, authed_client):
        """Scanning multiple children accumulates scanned_ids."""
        container = Item.objects.create(name='Shelf')
        child1 = Item.objects.create(name='Item A', parent=container)
        child2 = Item.objects.create(name='Item B', parent=container)
        child3 = Item.objects.create(name='Item C', parent=container)

        # Scan first child
        response = authed_client.post(
            reverse('app:audit_list_hxpost', kwargs={'pk': container.pk}),
            {'barcode': child1.barcode_string, 'scanned_ids': ''},
            HTTP_HX_REQUEST='true',
        )
        assertContains(response, '1 / 3 scanned')

        # Extract scanned_ids from response
        scanned_ids = _extract_scanned_ids(response)
        assert str(child1.pk) in scanned_ids

        # Scan second child
        response = authed_client.post(
            reverse('app:audit_list_hxpost', kwargs={'pk': container.pk}),
            {'barcode': child2.barcode_string, 'scanned_ids': scanned_ids},
            HTTP_HX_REQUEST='true',
        )
        assertContains(response, '2 / 3 scanned')

    def test_scan_non_child_item_shows_warning(self, authed_client):
        """POST with a non-child item barcode shows a warning."""
        container = Item.objects.create(name='Shelf')
        other_item = Item.objects.create(name='Other Item')  # No parent
        Item.objects.create(name='Child', parent=container)

        authed_client.post(
            reverse('app:audit_list_hxpost', kwargs={'pk': container.pk}),
            {'barcode': other_item.barcode_string, 'scanned_ids': ''},
            HTTP_HX_REQUEST='true',
        )

        # Messages are stored in the framework and fetched by the HTMX
        # messages-partial endpoint, not rendered in the audit-list partial.
        msg_response = authed_client.get(reverse('app:messages_partial'))
        assertContains(msg_response, 'is not in')
        assertContains(msg_response, 'Set it aside')

    def test_scan_unknown_barcode_shows_error(self, authed_client):
        """POST with an unrecognized barcode shows an error."""
        container = Item.objects.create(name='Shelf')
        Item.objects.create(name='Child', parent=container)

        authed_client.post(
            reverse('app:audit_list_hxpost', kwargs={'pk': container.pk}),
            {'barcode': 'UNKNOWN123', 'scanned_ids': ''},
            HTTP_HX_REQUEST='true',
        )

        # Messages are stored in the framework and fetched by the HTMX
        # messages-partial endpoint, not rendered in the audit-list partial.
        msg_response = authed_client.get(reverse('app:messages_partial'))
        assertContains(msg_response, 'Unknown barcode')

    def test_all_items_scanned(self, authed_client):
        """When all items are scanned, shows completion message."""
        container = Item.objects.create(name='Shelf')
        child = Item.objects.create(name='Item A', parent=container)

        response = authed_client.post(
            reverse('app:audit_list_hxpost', kwargs={'pk': container.pk}),
            {'barcode': child.barcode_string, 'scanned_ids': ''},
            HTTP_HX_REQUEST='true',
        )

        assertContains(response, 'All items accounted for')
        assertContains(response, 'Back to Item')
        assertContains(response, 'Finish audit')

    def test_finish_audit_logs_history(self, authed_client):
        """Finishing an audit with all items scanned creates an AUDIT ItemHistory record."""
        container = Item.objects.create(name='Shelf')
        child = Item.objects.create(name='Item A', parent=container)

        # Finish the audit via audit_confirm_lost_hxpost with the child scanned
        response = authed_client.post(
            reverse('app:audit_confirm_lost_hxpost', kwargs={'pk': container.pk}),
            {'scanned_ids': str(child.pk)},
            HTTP_HX_REQUEST='true',
        )

        assertContains(response, 'Items Found')

        history = ItemHistory.objects.filter(item=container, action='AUDIT')
        assert history.count() == 1
        assert history.first().metadata['scanned'] == [child.pk]

        # The child was not moved
        child.refresh_from_db()
        assert child.parent == container


class TestAuditConfirmLost:
    def test_confirm_lost_shows_form(self, authed_client):
        """GET with show_confirm shows the confirm-lost form."""
        container = Item.objects.create(name='Shelf')
        Item.objects.create(name='Item A', parent=container)
        Item.objects.create(name='Item B', parent=container)

        response = authed_client.get(
            reverse('app:audit_confirm_lost_hx', kwargs={'pk': container.pk}),
            {'show_confirm': '1', 'scanned_ids': ''},
            HTTP_HX_REQUEST='true',
        )

        assertContains(response, 'Complete Audit')
        assertContains(response, 'Move 2 unscanned items to lost box')

    def test_confirm_lost_to_existing_box(self, authed_client):
        """Moving unscanned items to an existing lost box."""
        # Create root Lost item and a lost box
        lost_root = Item.objects.create(name='Lost', parent=None)
        lost_box = Item.objects.create(name='Lost-1-Jul-2026a', parent=lost_root)

        container = Item.objects.create(name='Shelf')
        child1 = Item.objects.create(name='Item A', parent=container)
        child2 = Item.objects.create(name='Item B', parent=container)

        # Scan child1, leave child2 unscanned
        response = authed_client.post(
            reverse('app:audit_confirm_lost_hxpost', kwargs={'pk': container.pk}),
            {
                'lost_box': str(lost_box.pk),
                'scanned_ids': str(child1.pk),
            },
            HTTP_HX_REQUEST='true',
        )

        # Returns the completion partial
        assertContains(response, 'Items moved to Lost')

        # Verify child2 was moved
        child2.refresh_from_db()
        assert child2.parent == lost_box
        assert child2.previously_in == container

        # Verify child1 was NOT moved
        child1.refresh_from_db()
        assert child1.parent == container

    def test_confirm_lost_with_new_box(self, authed_client):
        """Creating a new lost box and moving items to it."""
        # Create root Lost item
        lost_root = Item.objects.create(name='Lost', parent=None)

        container = Item.objects.create(name='Shelf')
        child = Item.objects.create(name='Item A', parent=container)

        response = authed_client.post(
            reverse('app:audit_confirm_lost_hxpost', kwargs={'pk': container.pk}),
            {
                'lost_box': 'new',
                'scanned_ids': '',
            },
            HTTP_HX_REQUEST='true',
        )

        # Returns the completion partial
        assertContains(response, 'Items moved to Lost')

        # Verify a new lost box was created
        lost_boxes = list(lost_root.children.all())
        assert len(lost_boxes) == 1

        # Verify child was moved to the new lost box
        child.refresh_from_db()
        assert child.parent == lost_boxes[0]
        assert child.previously_in == container

    def test_confirm_lost_no_items(self, authed_client):
        """Submitting confirm-lost with no unscanned items shows completion."""
        container = Item.objects.create(name='Shelf')

        response = authed_client.post(
            reverse('app:audit_confirm_lost_hxpost', kwargs={'pk': container.pk}),
            {
                'lost_box': 'new',
                'scanned_ids': '',
            },
            HTTP_HX_REQUEST='true',
        )

        # Returns the completion partial
        assertContains(response, 'Back to Item')

    def test_confirm_lost_invalid_box(self, authed_client):
        """Submitting with an invalid lost box ID shows error."""
        container = Item.objects.create(name='Shelf')
        child = Item.objects.create(name='Item A', parent=container)

        response = authed_client.post(
            reverse('app:audit_confirm_lost_hxpost', kwargs={'pk': container.pk}),
            {
                'lost_box': '99999',
                'scanned_ids': '',
            },
        )

        assertRedirects(response, reverse('app:item_detail', kwargs={'pk': container.pk}))

        # Verify child was NOT moved
        child.refresh_from_db()
        assert child.parent == container

    def test_confirm_lists_set_aside_items(self, authed_client):
        """Confirming lists set-aside items in the completion partial without moving them."""
        container = Item.objects.create(name='Shelf')
        other = Item.objects.create(name='Other Container')
        set_aside_item = Item.objects.create(name='Found Item', parent=other)

        response = authed_client.post(
            reverse('app:audit_confirm_lost_hxpost', kwargs={'pk': container.pk}),
            {
                'lost_box': 'new',
                'scanned_ids': '',
                'unresolved': set_aside_item.barcode_string,
            },
            HTTP_HX_REQUEST='true',
        )

        # Returns the completion partial, not a redirect
        assertContains(response, 'Scans to review')
        assertContains(response, 'Found Item')

        # Set-aside item is NOT moved
        set_aside_item.refresh_from_db()
        assert set_aside_item.parent == other

    def test_confirm_lists_unknown_barcodes(self, authed_client):
        """Confirming lists unknown barcodes in the completion partial without creating items."""
        container = Item.objects.create(name='Shelf')

        barcode = 'UNKNOWN123'
        response = authed_client.post(
            reverse('app:audit_confirm_lost_hxpost', kwargs={'pk': container.pk}),
            {
                'lost_box': 'new',
                'scanned_ids': '',
                'unresolved': barcode,
            },
            HTTP_HX_REQUEST='true',
        )

        # Returns the completion partial, not a redirect
        assertContains(response, 'Unknown Barcodes')
        assertContains(response, barcode)


class TestAuditRecheck:
    """Rechecking unresolved scans reflects items created or associated elsewhere."""

    def test_recheck_unknown_barcode_now_part_of_item(self, authed_client):
        """An unknown barcode that later gets associated with an item is reported on recheck."""
        container = Item.objects.create(name='Shelf')
        Item.objects.create(name='Child', parent=container)
        existing = Item.objects.create(name='Existing Item')

        barcode = 'UNKNOWN123'
        # Scan the unknown barcode
        response = authed_client.post(
            reverse('app:audit_list_hxpost', kwargs={'pk': container.pk}),
            {'barcode': barcode, 'scanned_ids': ''},
            HTTP_HX_REQUEST='true',
        )
        assertContains(response, 'Unknown Barcodes')
        assertContains(response, barcode)

        # Associate the barcode with an existing item (simulating another tab)
        ExternalBarcode.objects.create(code=barcode, item=existing)

        # Recheck
        response = authed_client.post(
            reverse('app:audit_complete_hxpost', kwargs={'pk': container.pk}),
            {'recheck': '1', 'scanned_ids': '', 'unresolved': barcode},
            HTTP_HX_REQUEST='true',
        )
        assertContains(response, f'Now part of Existing Item ({existing.barcode_string})')

    def test_recheck_possible_item_now_exists(self, authed_client):
        """A possible internal barcode that later gets created is reported on recheck."""
        container = Item.objects.create(name='Shelf')
        Item.objects.create(name='Child', parent=container)

        barcode = f'{settings.BARCODE_PREFIX}999999'
        # Scan the possible internal barcode
        response = authed_client.post(
            reverse('app:audit_list_hxpost', kwargs={'pk': container.pk}),
            {'barcode': barcode, 'scanned_ids': ''},
            HTTP_HX_REQUEST='true',
        )
        assertContains(response, 'Possible New Items')
        assertContains(response, barcode)

        # Create the item (simulating another tab)
        new_item = Item.objects.create(name='New Item', pk=999999)

        # Recheck
        response = authed_client.post(
            reverse('app:audit_complete_hxpost', kwargs={'pk': container.pk}),
            {'recheck': '1', 'scanned_ids': '', 'unresolved': barcode},
            HTTP_HX_REQUEST='true',
        )
        assertContains(response, f'Now part of New Item ({new_item.barcode_string})')

    def test_recheck_external_barcode_added_to_created_item(self, authed_client):
        """An external barcode added to a newly-created item is reported on recheck."""
        container = Item.objects.create(name='Shelf')
        Item.objects.create(name='Child', parent=container)

        internal_barcode = f'{settings.BARCODE_PREFIX}999999'
        external_barcode = 'UNKNOWN123'

        # Scan the internal (possible) barcode
        response = authed_client.post(
            reverse('app:audit_list_hxpost', kwargs={'pk': container.pk}),
            {'barcode': internal_barcode, 'scanned_ids': ''},
            HTTP_HX_REQUEST='true',
        )
        assertContains(response, 'Possible New Items')

        # Scan the external (unknown) barcode
        response = authed_client.post(
            reverse('app:audit_list_hxpost', kwargs={'pk': container.pk}),
            {'barcode': external_barcode, 'scanned_ids': ''},
            HTTP_HX_REQUEST='true',
        )
        assertContains(response, 'Unknown Barcodes')

        # Create the item and add the external barcode to it (simulating another tab)
        new_item = Item.objects.create(name='New Item', pk=999999)
        ExternalBarcode.objects.create(code=external_barcode, item=new_item)

        # Recheck with both unresolved barcodes
        response = authed_client.post(
            reverse('app:audit_complete_hxpost', kwargs={'pk': container.pk}),
            {'recheck': '1', 'scanned_ids': '', 'unresolved': f'{internal_barcode},{external_barcode}'},
            HTTP_HX_REQUEST='true',
        )
        # Both the internal barcode and the external barcode now resolve to the new item
        assertContains(response, f'Now part of New Item ({new_item.barcode_string})')

    def test_recheck_is_idempotent(self, authed_client):
        """Rechecking twice produces the same derived lists in the context."""
        container = Item.objects.create(name='Shelf')
        existing = Item.objects.create(name='Existing Item')
        barcode = 'UNKNOWN123'
        ExternalBarcode.objects.create(code=barcode, item=existing)

        url = reverse('app:audit_complete_hxpost', kwargs={'pk': container.pk})
        params = {'recheck': '1', 'scanned_ids': '', 'unresolved': barcode}

        first = authed_client.post(url, params, HTTP_HX_REQUEST='true')
        second = authed_client.post(url, params, HTTP_HX_REQUEST='true')

        for key in ('set_aside_items', 'unknown_barcodes', 'possible_barcodes'):
            assert first.context[key] == second.context[key], (
                f'{key} changed between rechecks: {first.context[key]!r} != {second.context[key]!r}'
            )


def _extract_scanned_ids(response):
    """Extract the scanned_ids value from an HTMX response."""
    import json
    import re

    # The audit template stores scanned_ids in the hx-vals attribute as JSON
    match = re.search(r"hx-vals='({[^}]+})'", response.content.decode())
    if match:
        try:
            vals = json.loads(match.group(1))
            return vals.get('scanned_ids', '')
        except (json.JSONDecodeError, KeyError):
            return ''
    return ''
