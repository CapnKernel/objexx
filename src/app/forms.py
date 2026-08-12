import csv
from io import StringIO

from django import forms
from django.core.exceptions import ValidationError

from .models import Item


class ItemCreateForm(forms.ModelForm):
    """Form for creating new items"""

    # External barcodes are carried as hidden state (pre-filled from the scan
    # flow) and displayed read-only in the template; they are not editable here.
    external_barcodes = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = Item
        fields = ['name', 'description', 'parent']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'parent': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = Item.objects.all()
        self.fields['parent'].required = False


class ExternalBarcodeForm(forms.Form):
    """Form for associating external barcodes with an item"""

    barcode = forms.CharField(
        label='Scan a barcode',
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'aria-label': 'Scan barcode',
                'autofocus': True,
            }
        ),
        help_text='Scan an external barcode to add it to the list, or scan an item barcode.',
    )

    pending_barcodes = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )


class CSVImportForm(forms.Form):
    """Form for displaying the CSV textarea in the browser"""

    csv_data = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 10, 'cols': 80}),
        label='CSV Data',
        help_text='Paste CSV data with headers: ID, In, Name, Desc',
    )
    save = forms.BooleanField(required=False, initial=False, widget=forms.HiddenInput())
