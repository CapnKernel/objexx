from .models import Item


class TestGetLostItem:
    """Tests for Item.get_lost_item() — a root-level item named 'Lost'."""

    def test_returns_none_when_no_lost_item(self, db):
        """No root-level 'Lost' item exists → returns None."""
        assert Item.get_lost_item() is None

    def test_returns_lost_item_when_exists(self, db):
        """Single root-level 'Lost' item exists → returns it."""
        lost = Item.objects.create(name='Lost', parent=None)
        result = Item.get_lost_item()
        assert result == lost
        assert result.parent is None
        assert result.deleted is False

    def test_ignores_non_root_lost_item(self, db):
        """Non-root 'Lost' item (with a parent) is ignored; root one is returned."""
        root_lost = Item.objects.create(name='Lost', parent=None)
        container = Item.objects.create(name='Container')
        Item.objects.create(name='Lost', parent=container)
        result = Item.get_lost_item()
        assert result == root_lost

    def test_ignores_deleted_lost_item(self, db):
        """Soft-deleted root 'Lost' item is ignored → returns None."""
        lost = Item.objects.create(name='Lost', parent=None)
        lost.soft_delete('Testing')
        assert Item.get_lost_item() is None

    def test_returns_none_on_multiple_root_lost(self, db):
        """Multiple root-level 'Lost' items → returns None (data integrity issue)."""
        Item.objects.create(name='Lost', parent=None)
        Item.objects.create(name='Lost', parent=None)
        assert Item.get_lost_item() is None
