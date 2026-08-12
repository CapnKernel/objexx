from datetime import date, datetime
from unittest.mock import patch

from django.utils import timezone

from ..models import Item


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

    def test_ignores_non_root_lost_item(self, db):
        """Non-root 'Lost' item (with a parent) is ignored; root one is returned."""
        root_lost = Item.objects.create(name='Lost', parent=None)
        container = Item.objects.create(name='Container')
        Item.objects.create(name='Lost', parent=container)
        result = Item.get_lost_item()
        assert result == root_lost

    def test_returns_none_on_multiple_root_lost(self, db):
        """Multiple root-level 'Lost' items → returns None (data integrity issue)."""
        Item.objects.create(name='Lost', parent=None)
        Item.objects.create(name='Lost', parent=None)
        assert Item.get_lost_item() is None


FROZEN_DATE = date(2026, 2, 14)
FROZEN_DATETIME = datetime(2026, 2, 14, 10, 30, 0, tzinfo=timezone.get_current_timezone())
FROZEN_DATE_PREFIX = FROZEN_DATE.strftime('Lost-%-d-%b-%Y')


@patch.object(timezone, 'now', return_value=FROZEN_DATETIME)
@patch.object(timezone, 'localtime', return_value=FROZEN_DATETIME)
class TestCreateLostBox:
    """Tests for Item.create_lost_box() — creating dated lost box items."""

    def test_returns_none_when_no_lost_item(self, mock_localtime, mock_now, db):
        """No root 'Lost' item exists → returns None."""
        assert Item.create_lost_box() is None

    def test_creates_first_box_with_suffix_a(self, mock_localtime, mock_now, db):
        """First lost box for today gets suffix 'a'."""
        Item.objects.create(name='Lost', parent=None)
        box = Item.create_lost_box()
        assert box.name == f'{FROZEN_DATE_PREFIX}a'
        assert box.parent is not None
        assert box.parent.name == 'Lost'

    def test_increments_letter_for_subsequent_boxes(self, mock_localtime, mock_now, db):
        """Second and third boxes get suffixes 'b' and 'c'."""
        Item.objects.create(name='Lost', parent=None)
        box_a = Item.create_lost_box()
        box_b = Item.create_lost_box()
        box_c = Item.create_lost_box()
        assert box_a.name == f'{FROZEN_DATE_PREFIX}a'
        assert box_b.name == f'{FROZEN_DATE_PREFIX}b'
        assert box_c.name == f'{FROZEN_DATE_PREFIX}c'

    def test_ignores_boxes_from_other_dates(self, mock_localtime, mock_now, db):
        """Boxes from other dates don't affect the suffix for today."""
        Item.objects.create(name='Lost', parent=None)
        lost = Item.get_lost_item()
        Item.objects.create(name='Lost-1-Jan-2020z', parent=lost)
        Item.objects.create(name='Lost-27-Oct-3999z', parent=lost)
        box = Item.create_lost_box()
        assert box.name == f'{FROZEN_DATE_PREFIX}a'

    def test_sets_lost_item_as_parent(self, mock_localtime, mock_now, db):
        """Created box has the Lost item as its parent."""
        lost = Item.objects.create(name='Lost', parent=None)
        box = Item.create_lost_box()
        assert box.parent == lost
