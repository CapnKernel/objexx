from django.conf import settings
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains, assertRedirects

from ..models import Item


def _barcode(item_id):
    """Build an internal barcode string for the given item id."""
    return f'{settings.BARCODE_PREFIX}{item_id}'


class TestNewItemPage:
    def test_page_renders_form(self, authed_client):
        """GET to the new item page renders the create form with the scanned barcode."""
        barcode = _barcode(999999)
        response = authed_client.get(reverse('app:new_item'), {'barcode': barcode})

        assertContains(response, 'Create New Item')
        assertContains(response, barcode)

    def test_page_redirects_to_existing_item(self, authed_client):
        """GET with a barcode that already exists redirects to that item."""
        item = Item.objects.create(name='Existing')

        response = authed_client.get(reverse('app:new_item'), {'barcode': item.barcode_string})

        assertRedirects(response, reverse('app:item_detail', kwargs={'pk': item.pk}))

    def test_page_rejects_non_internal_barcode(self, authed_client):
        """GET with a barcode not in the internal format shows an error."""
        response = authed_client.get(reverse('app:new_item'), {'barcode': 'UNKNOWN123'})

        assertContains(response, 'not in the required internal format')

    def test_page_requires_barcode(self, authed_client):
        """GET without a barcode shows an error."""
        response = authed_client.get(reverse('app:new_item'))

        assertContains(response, 'scan an unused internal barcode')


class TestNewItemHxpost:
    def test_creates_item_with_barcode_id(self, authed_client):
        """POST creates an item whose id matches the internal barcode."""
        barcode = _barcode(999999)

        response = authed_client.post(
            reverse('app:new_item_hxpost') + f'?barcode={barcode}',
            {'name': 'New Item'},
            HTTP_HX_REQUEST='true',
        )

        item = Item.objects.get(pk=999999)
        assert item.name == 'New Item'
        assert response.status_code == 200
        assert response['HX-Redirect'] == reverse('app:item_detail', kwargs={'pk': item.pk})

    def test_creates_item_with_parent(self, authed_client):
        """POST with a parent sets the parent on the created item."""
        parent = Item.objects.create(name='Shelf')
        barcode = _barcode(999998)

        authed_client.post(
            reverse('app:new_item_hxpost') + f'?barcode={barcode}',
            {'name': 'Child', 'parent': parent.pk},
            HTTP_HX_REQUEST='true',
        )

        item = Item.objects.get(pk=999998)
        assert item.parent == parent

    def test_creates_external_barcodes(self, authed_client):
        """POST with external barcodes associates them with the new item."""
        barcode = _barcode(999997)

        authed_client.post(
            reverse('app:new_item_hxpost') + f'?barcode={barcode}',
            {'name': 'New Item', 'external_barcodes': 'UPC123\nSER456'},
            HTTP_HX_REQUEST='true',
        )

        item = Item.objects.get(pk=999997)
        codes = set(item.external_barcodes.values_list('code', flat=True))
        assert codes == {'UPC123', 'SER456'}

    def test_invalid_form_returns_partial(self, authed_client):
        """POST with an invalid form returns the form partial and creates nothing."""
        barcode = _barcode(999996)

        response = authed_client.post(
            reverse('app:new_item_hxpost') + f'?barcode={barcode}',
            {'name': ''},  # name is required
            HTTP_HX_REQUEST='true',
        )

        assert response.status_code == 200
        assertContains(response, 'Create Item')
        assert not Item.objects.filter(pk=999996).exists()

    def test_action_barcode_prevents_creation(self, authed_client):
        """POST with an action barcode among the external barcodes creates nothing."""
        barcode = _barcode(999995)
        action_barcode = f'{settings.BARCODE_VERB_PREFIX}AUDIT'

        response = authed_client.post(
            reverse('app:new_item_hxpost') + f'?barcode={barcode}',
            {'name': 'New Item', 'external_barcodes': action_barcode},
            HTTP_HX_REQUEST='true',
        )

        # The item must not be created, and the form partial is returned.
        assert response.status_code == 200
        assertContains(response, 'Create Item')  # "Create Item" will exist in the partial if item wasn't created.
        assert not Item.objects.filter(pk=999995).exists()
        # The action barcode is dropped from the returned form.
        assertNotContains(response, action_barcode)
        # A per-barcode message is emitted (fetched via the messages partial).
        # The apostrophes are HTML-escaped, so match on the surrounding text.
        msg_response = authed_client.get(reverse('app:messages_partial'))
        assertContains(msg_response, f'Action barcode {action_barcode} cannot be added as an external barcode.')

    def test_get_returns_405(self, authed_client):
        """GET to the hxpost endpoint is not allowed."""
        response = authed_client.get(reverse('app:new_item_hxpost'))

        assert response.status_code == 405
