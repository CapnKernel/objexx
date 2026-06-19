import csv
from io import StringIO
from django import forms
from django.core.exceptions import ValidationError
from .models import Item


class ItemCreateForm(forms.ModelForm):
    """Form for creating new items"""

    external_barcodes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={'rows': 3, 'placeholder': 'Scan external barcodes here, one per line...', 'class': 'form-control'}
        ),
        help_text='Enter external barcodes (UPC, serial numbers, etc.), one per line',
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
        # Only show non-deleted items as parent options
        self.fields['parent'].queryset = Item.objects.filter(deleted=False)
        self.fields['parent'].required = False


class CSVImportForm(forms.Form):
    """Form for displaying the CSV textarea in the browser"""

    csv_data = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 10, 'cols': 80}),
        label='CSV Data',
        help_text='Paste CSV data with headers: ID, In, Name, Desc',
    )
    save = forms.BooleanField(required=False, initial=False, widget=forms.HiddenInput())
