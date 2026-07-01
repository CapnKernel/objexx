import csv
from io import StringIO

from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import CSVImportForm
from .models import Item


def import_items(request):
    """Handle CSV import of items"""
    if request.method == 'POST':
        form = CSVImportForm(request.POST or None)
        ctx = {'form': form}

        if form.is_valid():
            csv_data = form.cleaned_data['csv_data']
            save_requested = form.cleaned_data['save']
            ctx['csv_data'] = csv_data

            try:
                # Parse CSV data
                reader = csv.DictReader(StringIO(csv_data), delimiter='\t')

                # Validate headers
                expected_headers = {'ID', 'In', 'Name', 'Desc'}
                actual_headers = set(reader.fieldnames)
                if not expected_headers.issubset(actual_headers):
                    form.add_error(
                        'csv_data',
                        f'Missing required headers: {", ".join(expected_headers - actual_headers)}',
                    )
                    return render(request, 'app/import.html', {'form': form})

                # Process and validate each row
                validated_items = []
                errors = []
                last_parent = None
                total_items = 0
                root_items = 0
                child_items = 0
                created_count = 0

                with transaction.atomic():
                    for i, row in enumerate(reader):
                        n = i + 2  # Account for header row
                        # Map CSV fields to model fields
                        mapper = {
                            'ID': 'id',
                            'Name': 'name',
                            'Desc': 'description',
                            'In': 'parent_id',
                        }
                        print(f'{row=}')

                        data = {v: (row[k] if row[k] else '').strip() for k, v in mapper.items()}

                        if not data['name'].strip():
                            continue  # Skip rows without a name

                        # Determine parent based on 'In' field
                        in_field = data['parent_id']
                        parent = None
                        if in_field == '-root-':
                            parent = None
                            last_parent = None
                        elif in_field.isdigit():
                            parent = in_field
                            last_parent = parent
                        elif not in_field:
                            parent = last_parent
                        else:
                            errors.append(f"Line {n}: Invalid 'In' field value: {in_field}")
                            continue

                        # Update parent in data
                        data['parent_id'] = parent

                        validated_items.append(data)
                        total_items += 1
                        if data['parent_id']:
                            child_items += 1
                        else:
                            root_items += 1
                        if save_requested:
                            # If save was requested, save the items
                            try:
                                item = Item.objects.get(pk=data['id'])
                            except Item.DoesNotExist:
                                item = Item()
                                item.id = data['id']
                            for k, v in data.items():
                                if k != 'id':
                                    setattr(item, k, v)
                            item.save()
                            created_count += 1

                    if errors:
                        if save_requested:
                            transaction.set_rollback(True)

                        # Show errors and allow correction
                        ctx['errors'] = errors
                    else:
                        # All validation passed
                        ctx['validated_items'] = validated_items
                        ctx['stats'] = {
                            'total_items': total_items,
                            'root_items': root_items,
                            'child_items': child_items,
                        }
                        ctx['save'] = True

                        if save_requested:
                            # Redirect to item list with success message
                            msg = {
                                'message': f'Successfully imported {created_count} items',
                                'message_type': 'success',
                            }
                            url = reverse('app:item_list', query=msg)
                            return redirect(url)

                return render(request, 'app/import.html', ctx)

            except Exception as e:
                form.add_error('csv_data', f'Error parsing CSV: {e}')
                return render(request, 'app/import.html', ctx)

        # Form is invalid
        return render(request, 'app/import.html', ctx)

    else:
        # GET request - show empty form
        form = CSVImportForm()
        return render(request, 'app/import.html', {'form': form})
