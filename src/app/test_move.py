import html

from django.urls import reverse
from pytest_django.asserts import assertRedirects, assertTemplateUsed

from .models import Item


def test_move_sets_parent_and_previously_in(client, django_user_model):
    """Moving an item from one container to another sets parent and previously_in."""
    django_user_model.objects.create_user(email='test@example.com', password='secret123')
    client.login(email='test@example.com', password='secret123')

    # Create containers and an item
    old_container = Item.objects.create(name='Old Container')
    new_container = Item.objects.create(name='New Container')
    item = Item.objects.create(name='Test Item', parent=old_container)

    # Verify initial state
    item.refresh_from_db()
    assert item.parent == old_container
    assert item.previously_in is None

    # Move the item to the new container via the move action
    response = client.post(
        reverse('app:item_action', kwargs={'pk': item.pk, 'action': 'move'}),
        {'barcode': new_container.barcode_string},
    )

    # Should redirect to the item detail page
    assertRedirects(response, reverse('app:item_detail', kwargs={'pk': item.pk}))

    # Verify the move updated both fields
    item.refresh_from_db()
    assert item.parent == new_container
    assert item.previously_in == old_container


def test_move_to_root_fails(client, django_user_model):
    """Moving an item to root level (no parent) is not allowed via the move action."""
    django_user_model.objects.create_user(email='test@example.com', password='secret123')
    client.login(email='test@example.com', password='secret123')

    old_container = Item.objects.create(name='Old Container')
    item = Item.objects.create(name='Test Item', parent=old_container)

    # POST to the move action with an empty barcode (attempting to move to root)
    response = client.post(reverse('app:item_action', kwargs={'pk': item.pk, 'action': 'move'}), {'barcode': ''})

    # Should return the move page with an error message, not redirect
    assertTemplateUsed(response, 'app/move.html')
    assert response.status_code == 200
    assert html.escape("Creating top-level items can't be done with this form.") in response.content.decode()

    # Verify the item's parent was not changed
    item.refresh_from_db()
    assert item.parent == old_container
    assert item.previously_in is None


def test_move_to_nonexistent_barcode_fails(client, django_user_model):
    """Moving an item to a barcode that doesn't match any item shows an error."""
    django_user_model.objects.create_user(email='test@example.com', password='secret123')
    client.login(email='test@example.com', password='secret123')

    old_container = Item.objects.create(name='Old Container')
    item = Item.objects.create(name='Test Item', parent=old_container)

    # POST with a well-formed barcode that doesn't exist in the database
    response = client.post(
        reverse('app:item_action', kwargs={'pk': item.pk, 'action': 'move'}),
        {'barcode': 'T=99999'},
    )

    # Should return the move page with an error message, not redirect
    assertTemplateUsed(response, 'app/move.html')
    assert response.status_code == 200
    assert html.escape("Destination item with barcode 'T=99999' not found") in response.content.decode()

    # Verify the item's parent was not changed
    item.refresh_from_db()
    assert item.parent == old_container
    assert item.previously_in is None


def test_move_to_unknown_foreign_barcode_fails(client, django_user_model):
    """Moving an item to a barcode that isn't a valid barcode format shows an error."""
    django_user_model.objects.create_user(email='test@example.com', password='secret123')
    client.login(email='test@example.com', password='secret123')

    old_container = Item.objects.create(name='Old Container')
    item = Item.objects.create(name='Test Item', parent=old_container)

    # POST with a string that isn't a barcode at all
    response = client.post(
        reverse('app:item_action', kwargs={'pk': item.pk, 'action': 'move'}),
        {'barcode': 'xyzzy'},
    )

    # Should return the move page with an error message, not redirect
    assertTemplateUsed(response, 'app/move.html')
    assert response.status_code == 200
    assert html.escape("Destination item with barcode 'xyzzy' not found") in response.content.decode()

    # Verify the item's parent was not changed
    item.refresh_from_db()
    assert item.parent == old_container
    assert item.previously_in is None


def test_move_to_external_barcode_fails(client, django_user_model):
    """Moving an item using an external barcode (not an internal item barcode) shows an error."""
    django_user_model.objects.create_user(email='test@example.com', password='secret123')
    client.login(email='test@example.com', password='secret123')

    old_container = Item.objects.create(name='Old Container')
    destination = Item.objects.create(name='Destination Container')
    item = Item.objects.create(name='Test Item', parent=old_container)

    # Give the destination an external barcode
    from .models import ExternalBarcode

    ExternalBarcode.objects.create(item=destination, code='UPC1234567890', barcode_type='UPC')

    # POST using the external barcode — move() uses from_barcode() which only
    # parses internal barcodes, so this should fail
    response = client.post(
        reverse('app:item_action', kwargs={'pk': item.pk, 'action': 'move'}),
        {'barcode': 'UPC1234567890'},
    )

    # Should return the move page with an error message, not redirect
    assertTemplateUsed(response, 'app/move.html')
    assert response.status_code == 200
    assert html.escape("Destination item with barcode 'UPC1234567890' not found") in response.content.decode()

    # Verify the item's parent was not changed
    item.refresh_from_db()
    assert item.parent == old_container
    assert item.previously_in is None


def test_move_into_own_descendant_fails(client, django_user_model):
    """Moving an item into one of its own descendants is prevented (cycle detection)."""
    django_user_model.objects.create_user(email='test@example.com', password='secret123')
    client.login(email='test@example.com', password='secret123')

    # Create a hierarchy: grandparent -> parent -> child
    grandparent = Item.objects.create(name='Grandparent')
    parent = Item.objects.create(name='Parent', parent=grandparent)
    child = Item.objects.create(name='Child', parent=parent)

    # Try to move the grandparent into the child (grandparent's own descendant)
    response = client.post(
        reverse('app:item_action', kwargs={'pk': grandparent.pk, 'action': 'move'}),
        {'barcode': child.barcode_string},
    )

    # Should return the move page with an error message, not redirect
    assertTemplateUsed(response, 'app/move.html')
    assert response.status_code == 200
    assert html.escape(f'Cannot move item into its own descendant: {child.path}') in response.content.decode()

    # Verify the grandparent's parent was not changed
    grandparent.refresh_from_db()
    assert grandparent.parent is None
    assert grandparent.previously_in is None
