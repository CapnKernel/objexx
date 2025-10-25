from django.db import models
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model


class Item(models.Model):
    """
    Represents any item in the lab - from tools to components to containers.
    Uses recursive parent-child relationship for containment.
    """

    name = models.CharField(max_length=255, help_text="Common name for the item")
    description = models.TextField(blank=True, help_text="Additional details about the item")

    # Recursive Relationship for Containment
    # Null parent means the item is not contained within another item, ie, a root item such as a shed
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        help_text="The item that this item is stored in",
    )

    # Barcode Printing Tracking
    barcode_printed_at = models.DateTimeField(
        null=True, blank=True, help_text="When the item's barcode label was last printed"
    )
    contents_printed_at = models.DateTimeField(
        null=True, blank=True, help_text="When the container's contents list was last printed (containers only)"
    )

    # Soft Deletion
    deleted = models.BooleanField(default=False, help_text="Whether this item has been deleted")
    deleted_at = models.DateTimeField(null=True, blank=True, help_text="When this item was deleted")
    deletion_reason = models.TextField(blank=True, help_text="Reason for deletion (broken, consumed, etc.)")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['deleted', 'parent']),
            models.Index(fields=['barcode_printed_at']),
            models.Index(fields=['contents_printed_at']),
        ]

    def __str__(self):
        status = " [DELETED]" if self.deleted else ""
        return f"{self.name} ({self.internal_barcode}){status}"

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
        while current and not current.deleted:
            path.insert(0, current.name)
            current = current.parent
        return " > ".join(path) if path else "Unfiled"

    @property
    def barcode_string(self):
        """Returns the full barcode string including prefix"""
        prefix = settings.BARCODE_PREFIX
        return f"{prefix}{self.id}"

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse('item_detail', kwargs={'internal_barcode': self.internal_barcode})

    def soft_delete(self, reason=""):
        """Soft delete this item and all its children recursively"""
        # Recursively soft delete all children
        for child in self.children.all():
            child.soft_delete(f"Parent container deleted: {reason}")

        self.deleted = True
        self.deleted_at = timezone.now()
        self.deletion_reason = reason
        self.save()

    def mark_barcode_printed(self):
        """Mark the item's barcode as printed"""
        self.barcode_printed_at = timezone.now()
        self.save()

    def mark_contents_printed(self):
        """Mark the container's contents sheet as printed"""
        if self.is_container:
            self.contents_printed_at = timezone.now()
            self.save()

    def get_all_children(self, include_self=False):
        """Get all descendants of this item (for containers)"""
        children = []
        if include_self:
            children.append(self)

        for child in self.children.filter(deleted=False):
            children.append(child)
            children.extend(child.get_all_children())

        return children


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
        ('OTHER', 'Other'),
    ]

    code = models.CharField(max_length=255, help_text="The external barcode value")
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='external_barcodes',
        help_text="The item this barcode is associated with",
    )
    barcode_type = models.CharField(
        max_length=50, choices=BARCODE_TYPE_CHOICES, default='UPC', help_text="Type of external barcode"
    )
    notes = models.TextField(blank=True, help_text="Additional context for this barcode association")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['code', 'item']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['barcode_type']),
        ]

    def __str__(self):
        return f"{self.code} ({self.barcode_type}) -> {self.item.name}"


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
    description = models.TextField(help_text="Human-readable description of what changed")
    user = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional structured data about the change")

    class Meta:
        indexes = [
            models.Index(fields=['item', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.timestamp.date()}: {self.action} - {self.item.name}"
