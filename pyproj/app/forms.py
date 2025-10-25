import csv
from io import StringIO
from django import forms
from django.core.exceptions import ValidationError
from .models import Item


class CSVImportForm(forms.Form):
    """Form for displaying the CSV textarea in the browser"""

    csv_data = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 10, 'cols': 80}),
        label='CSV Data',
        help_text='Paste CSV data with headers: ID, In, Name, Desc',
    )
    save = forms.BooleanField(required=False, initial=False, widget=forms.HiddenInput())
