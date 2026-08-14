import logging
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class Item(models.Model):
    """
    Represents any item in the lab - from tools to components to containers.
    Uses recursive parent-child relationship for containment.
    """

    @staticmethod
    def from_barcode(barcode_string):
        """
        Attempt to find an Item from an internal barcode string.
        Returns the Item if found, None otherwise.
        """
        match = re.match(f'^{re.escape(settings.BARCODE_PREFIX)}(\\d+)$', barcode_string)
        if match:
            try:
                return Item.objects.get(id=match.group(1))
            except Item.DoesNotExist:
                pass

        return None

    @staticmethod
    def get_lost_item():
        """
        Find and return the root-level 'Lost' item.
        A 'Lost' item is a root item (no parent) named 'Lost'.
        Returns the Item if found, None otherwise.
        """

        try:
            lost_item = Item.objects.get(name='Lost', parent=None)
            logger.info(f'Found Lost item: {lost_item} (id={lost_item.id})')
            return lost_item
        except Item.DoesNotExist:
            logger.warning("Lost item not found (no root-level item named 'Lost' exists)")
            return None
        except Item.MultipleObjectsReturned:
            logger.error("Multiple root-level items named 'Lost' found — data integrity issue")
            return None

    @staticmethod
    def create_lost_box():
        """
        Create a new lost box item as a child of the root 'Lost' item.
        The name follows the pattern 'Lost-{date}-{letter}' where date is in
        'd-mmm-yyyy' format (e.g., 'Lost-14-Feb-2026a') and letter increments
        from 'a' upwards based on existing items for today's date.
        Returns the newly created Item, or None if the Lost item doesn't exist.
        """

        lost_item = Item.get_lost_item()
        if lost_item is None:
            logger.error("Cannot create lost box: no root 'Lost' item exists")
            return None

        # Use Django timezone-aware localtime for the date
        today = timezone.localtime(timezone.now()).date()
        # Linux strftime: %-d = no-padded day, %b = abbreviated month, %Y = 4-digit year
        date_prefix = today.strftime('Lost-%-d-%b-%Y')

        # Find the last (alphabetically highest) existing child of Lost for today
        latest_lost_box = lost_item.children.filter(name__istartswith=date_prefix).order_by('name').last()

        # Determine the next letter
        if latest_lost_box:
            suffix = latest_lost_box.name[-1]  # e.g., 'c' from 'Lost-14-Feb-2026c'
            next_letter = chr(ord(suffix[0]) + 1)
        else:
            next_letter = 'a'  # First box for today

        new_name = f'{date_prefix}{next_letter}'
        new_item = Item.objects.create(name=new_name, parent=lost_item)
        logger.info(f'Created lost box: {new_item} (id={new_item.id})')
        return new_item

    @staticmethod
    def get_possible_item_id_from_internal_barcode(barcode_string):
        match = re.match(f'^{re.escape(settings.BARCODE_PREFIX)}(\\d+)$', barcode_string)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def from_any_barcode(barcode_string):
        """
        Attempt to find an Item from any barcode string (internal or external).
        Returns the Item if found, None otherwise.  This will fail if more than
        one item shares the same external barcode.
        """
        # Try internal barcode first
        item = Item.from_barcode(barcode_string)
        if item:
            return item

        # Try external barcodes
        try:
            external_barcode = ExternalBarcode.objects.get(code=barcode_string)
            return external_barcode.item
        except ExternalBarcode.DoesNotExist:
            pass

        return None

    name = models.CharField(max_length=255, help_text='Common name for the item')
    description = models.TextField(blank=True, help_text='Additional details about the item')

    # Recursive Relationship for Containment
    # Null parent means the item is not contained within another item, ie, a root item such as a shed
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        help_text='The item that this item is stored in',
    )

    # Previous Location
    previously_in = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moved_to',
        help_text='The container this item was previously stored in',
    )

    # Barcode Printing Tracking
    barcode_printed_at = models.DateTimeField(
        null=True, blank=True, help_text="When the item's barcode label was last printed"
    )
    contents_printed_at = models.DateTimeField(
        null=True, blank=True, help_text="When the container's contents list was last printed (containers only)"
    )

    # Scanning Tracking
    last_scanned_at = models.DateTimeField(null=True, blank=True, help_text='When this item was last scanned')

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['parent']),
            models.Index(fields=['barcode_printed_at']),
            models.Index(fields=['contents_printed_at']),
        ]

    def __str__(self):
        return f'{self.name} ({self.barcode_string})'

    @property
    def is_container(self):
        """Returns True if this item contains other items"""
        return self.children.exists()

    @property
    def needs_barcode_printed(self):
        """Returns True if this item needs a barcode label printed"""
        return self.barcode_printed_at is None

    @property
    def needs_contents_printed(self):
        """Returns True if this container needs a contents sheet printed"""
        return self.is_container and self.contents_printed_at is None

    @property
    def path(self):
        """Returns the full location path as a string"""
        path = []
        current = self
        while current:
            path.insert(0, current.name)
            current = current.parent
        return ' > '.join(path) if path else 'Unfiled'

    @property
    def barcode_string(self):
        """Returns the full barcode string including prefix"""
        prefix = settings.BARCODE_PREFIX
        return f'{prefix}{self.id}'

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse('app:item_detail', kwargs={'pk': self.pk})

    def mark_barcode_printed(self):
        """Mark the item's barcode as printed"""
        self.barcode_printed_at = timezone.now()
        self.save()

    def mark_contents_printed(self):
        """Mark the container's contents sheet as printed"""
        if self.is_container:
            self.contents_printed_at = timezone.now()
            self.save()

    def mark_scanned(self):
        """Record that this item was just scanned"""
        self.last_scanned_at = timezone.now()
        self.save()

    def move_to(self, new_parent):
        """Move this item to a new parent container.

        Records the previous location in ``previously_in`` and saves the change.
        """
        self.previously_in = self.parent
        self.parent = new_parent
        self.save()

    def get_all_children(self, include_self=False):
        """Get all descendants of this item (for containers)"""
        children = []
        if include_self:
            children.append(self)

        for child in self.children.all():
            children.append(child)
            children.extend(child.get_all_children())

        return children

    def get_contained_tree(self):
        """Get a tree structure of all contained items"""

        def build_tree(item):
            tree = {'item': item, 'children': []}
            for child in item.children.order_by('id'):
                tree['children'].append(build_tree(child))
            return tree

        return build_tree(self)

    def is_ancestor_of(self, other_item):
        """Check if this item is an ancestor of another item (to prevent cycles)"""
        if self == other_item:
            return True  # An item is considered its own ancestor

        # Walk up the parent chain of other_item to see if we find self
        current = other_item
        while current and current.parent:
            if current.parent == self:
                return True
            current = current.parent

        return False


class ExternalBarcode(models.Model):
    """
    External barcodes associated with items (UPC, order codes, etc.)
    Same external barcode can point to multiple items.
    """

    BARCODE_TYPE_CHOICES = [
        ('UPC', 'Manufacturer UPC'),
        ('ORDER', 'Purchase Order'),
        ('SERIAL', 'Serial Number'),
        ('DISTRIBUTOR', 'Distributor Part Number'),
        ('SHIPPING', 'Shipping Barcode'),
        ('LCSC', 'LCSC QR Code'),
        ('OTHER', 'Other'),
    ]

    code = models.CharField(max_length=255, help_text='The external barcode value')
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='external_barcodes',
        help_text='The item this barcode is associated with',
    )
    barcode_type = models.CharField(
        max_length=50, choices=BARCODE_TYPE_CHOICES, default='UPC', help_text='Type of external barcode'
    )
    notes = models.TextField(blank=True, help_text='Additional context for this barcode association')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['code', 'item']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['barcode_type']),
        ]

    def __str__(self):
        return f'{self.code} ({self.barcode_type}) -> {self.item.name}'

    @property
    def link(self):
        """Return a URL for this barcode if it has an external product page, else None."""
        if self.barcode_type == 'LCSC':
            lcsc_part = ExternalBarcode.extract_lcsc_part_number(self.code)
            if lcsc_part:
                return f'https://www.lcsc.com/product-detail/{lcsc_part}.html'
        return None

    @staticmethod
    def guess_type_from_str(barcode_string):
        # Guess the barcode type.
        if ExternalBarcode.extract_lcsc_part_number(barcode_string):
            return 'LCSC'
        if re.match(r'^\d{12,13}$', barcode_string):
            # UPC or EAN
            return 'UPC'
        else:
            return 'OTHER'

    @staticmethod
    def is_possible_action_barcode(barcode_string):
        """Check if a barcode string looks like an action barcode (e.g., V=AUDIT)."""
        return bool(re.match(f'^{re.escape(settings.BARCODE_VERB_PREFIX)}', barcode_string))

    @staticmethod
    def extract_lcsc_part_number(barcode_string):
        """Extract LCSC part number (C followed by digits) from a barcode string, if present."""
        match = re.search(r'pc:(C\d+),', barcode_string)
        if match:
            return match.group(1)
        match = re.match(r'C\d+,', barcode_string)
        if match:
            return barcode_string
        return None


class ItemHistory(models.Model):
    """
    Audit trail for important item actions
    """

    ACTION_CHOICES = [
        ('MOVED', 'Moved'),
        ('CREATED', 'Created'),
        ('DELETED', 'Deleted'),
        ('MERGED', 'Merged'),
        ('SPLIT', 'Split'),
        ('CLONED', 'Cloned'),
        ('UPDATED', 'Updated'),
    ]

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='history_entries')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.TextField(help_text='Human-readable description of what changed')
    user = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True, help_text='Additional structured data about the change')

    class Meta:
        indexes = [
            models.Index(fields=['item', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.timestamp.date()}: {self.action} - {self.item.name}'
