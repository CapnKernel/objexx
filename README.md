# Objexx - A small inventory management system

Objexx is a Django-based inventory management system which tracks physical items in labs, workshops, and maker spaces. It combines barcode scanning with hierarchical container management to organise and locate physical assets.

## 🎯 What Problem Does This Solve?

Objexx is built around:

- **Tracking containment relationships** - Items can be stored inside other items, which can themselves be stored
    in larger containers
- **A barcode-first workflow** - As much as possible, you scan barcodes rather than keying in item IDs
- **Performing actions on items** - Scan an item, then scan an action barcode to do something to that item
- **Flexible barcode support** - Objexx also records an item's external barcodes, such as UPC or order or shipping numbers

## 🏗️ Architecture & Design Philosophy

### Hierarchical Item Model

In the real world, items are often stored in other items.  For example:

- Components are stored in boxes
- Boxes are stored on shelves
- Shelves are in rooms or buildings

Items in Objexx form a tree structure where any item can be a container for other items.

### Barcode-centric Design

You should be able to do most of what you want by just scanning barcodes, with keyboard as last resort for things like descriptions.

There are three kinds of barcodes:

- **Internal Barcodes**: These are what you'd print on sticky labels, and apply to your stuff.  Each internal barcode has a system-defined prefix, followed by a unique number, such as `T=1241`.
- **External Barcodes**: Manufacturer barcodes (UPC, serial numbers, shipping etc.)
- **Action Barcodes**: Special barcodes that trigger actions on the last scanned item (e.g., `V=AUDIT`).  These can be printed on a card and kept nearby.

#### 📱 General Barcode Scanning Workflow
```
Scan Item → View Details → Scan Action → Perform Action
```

Objexx maintains context between scans, allowing you to scan an item and then scan an action barcode to perform operations on that item.

#### 🔄 Container Management
- **Tree View**: Visual hierarchy of contained items
- **Move Operations**: Change item locations while maintaining data integrity
- **Soft Deletion**: Remove items without losing historical data

#### 🎨 Modern Web Interface
- **HTMX Integration**: Dynamic updates without full page reloads
- **Bootstrap 5**: Responsive, mobile-friendly design

## Caveat: Work in progress
This is a super-young project.  Features are still being added, and the UI/UX is still rough around the edges.  If you want to contribute, please do!

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- A Django-supported database
- Barcode scanner (USB or Bluetooth, one that emulates a code being typed on a keyboard, followed by Enter)

### Installation
```bash
git clone https://github.com/CapnKernel/objexx.git
cd objexx/src
python3 -m venv env
source env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 🔧 Configuration

Settings are stored in `conf/local_settings.py`, which is initially generated from `conf/local_settings.py.template`.  You'll need to copy the template then generate the secret key:
```bash
# Create local settings file from template.  Contains settings such as
# DEBUG, DATABASES, ALLOWED_HOSTS, MEDIA_ROOT, etc.
cp conf/local_settings.py.template conf/local_settings.py
# Generate secret key and patch into conf/local_settings.py
sed -i "s/^\(SECRET_KEY = \).*$/\\1\"$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())' | sed 's/[&\/]/\\&/g')\"/" conf/local_settings.py
```

In `conf/local_settings.py`, you should also edit `ADMINS`.  There are more settings to configure later
if and when you want to deploy somewhere.

To change barcode prefixes, edit `BARCODE_PREFIX` and `BARCODE_VERB_PREFIX`.

Then:
```
# Setup database
./manage.py migrate
./manage.py createsuperuser

# Start development server
./manage.py runserver
```

Access the app at http://localhost:8000/


## 🎮 Usage Examples

### Basic Item Workflow
1. **Scan New Item**: Scanning an unknown barcode matching the internal format prompts for item creation
2. **View Item Details**: See item information, location path, and contained items
3. **Move Item**: Scan destination container barcode to relocate item
4. **Audit**: Scan action barcode to mark item as verified

### Container Management
- **Create Container**: Any item can become a container by placing other items inside it
- **View Contents**: Tree view shows all items contained within a container
- **Print Labels**: Generate barcode labels and contents sheets for containers

### Barcode Actions
- `V=MOVE` - Move last scanned item to new location
- `V=AUDIT` - Mark item as audited/verified
- `V=DELETE` - Soft delete item with reason

## 🏛️ Project Structure

```
src/
├── app/                    # Main inventory application
│   ├── models.py          # Item, ExternalBarcode, ItemHistory models
│   ├── views.py           # Scan handling, item management views
│   ├── actions.py         # Barcode-triggered actions
│   └── templates/app/     # HTML templates
├── conf/                  # Django settings and configuration
└── static/css/           # Stylesheets
```

## 🎯 Who Is This For?

Objexx is ideal for:
- **Hobbyists**: Organize personal collections and tools
- **Research Labs**: Track equipment, chemicals, and supplies
- **Maker Spaces**: Organize tools, components, and projects
- **Workshops**: Manage tools, materials, and inventory
- **Small Businesses**: Track physical assets and inventory

### Data Integrity
- **Soft Deletion**: Never lose historical data
- **Audit Trail**: Track all important changes
- **Cycle Prevention**: Prevent impossible containment relationships

### Extensible Design
- **Action System**: Easy to add new barcode-triggered actions
- **Barcode Types**: Support for multiple barcode formats
- **Container Hierarchy**: Unlimited nesting depth

## 📄 License

MIT license.  https://opensource.org/license/mit


## 🤝 Contributing

Changes welcome.

[Add contribution guidelines here]

