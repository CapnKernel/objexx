# Objexx - Physical Inventory Management System

Objexx is a Django-based inventory management system designed specifically for tracking physical items in labs, workshops, and maker spaces. It combines barcode scanning with hierarchical container management to provide a complete solution for organizing and locating physical assets.

## 🎯 What Problem Does This Solve?

Traditional inventory systems often struggle with the physical reality of items being stored inside other items. Objexx addresses this by:

- **Tracking containment relationships** - Items can be stored inside containers, which can themselves be stored in larger containers
- **Barcode-first workflow** - Designed around scanning physical barcodes rather than manual data entry
- **Real-world scanning patterns** - Supports the common workflow of scanning an item, then scanning an action barcode
- **Flexible barcode support** - Works with both internal system barcodes and external manufacturer barcodes

## 🏗️ Architecture & Design Philosophy

### Hierarchical Item Model
Items in Objexx form a tree structure where any item can be a container for other items. This mirrors real-world storage scenarios where:
- Tools are stored in toolboxes
- Components are stored in bins
- Bins are stored on shelves
- Shelves are in rooms or buildings

### Barcode-Centric Design
The system is built around barcode scanning as the primary interaction method:

- **Internal Barcodes**: System-generated barcodes in format `PREFIX123` (e.g., `OBJ123`)
- **External Barcodes**: Manufacturer barcodes (UPC, serial numbers, etc.)
- **Action Barcodes**: Special barcodes that trigger actions on the last scanned item (e.g., `V=AUDIT`)

### Key Features

#### 📱 Barcode Scanning Workflow
```
Scan Item → View Details → Scan Action → Perform Action
```

The system maintains context between scans, allowing you to scan an item and then scan an action barcode to perform operations on that item.

#### 🔄 Container Management
- **Tree View**: Visual hierarchy of contained items
- **Move Operations**: Change item locations while maintaining data integrity
- **Soft Deletion**: Remove items without losing historical data

#### 📊 Multi-format Barcode Support
- **Internal System Barcodes**: `OBJ123`, `OBJ456`
- **External Barcodes**: UPC codes, serial numbers, distributor codes
- **Action Barcodes**: `V=MOVE`, `V=AUDIT`, `V=DELETE`

#### 🎨 Modern Web Interface
- **HTMX Integration**: Dynamic updates without full page reloads
- **Bootstrap 5**: Responsive, mobile-friendly design
- **Tree Visualization**: Clear display of containment relationships

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL (recommended) or SQLite
- Barcode scanner (USB or Bluetooth)

### Installation
```bash
cd pyproj/
python3 -m venv env
source env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Generate secret key
sed -i "3c\SECRET_KEY = \"$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')\"" .env

# Configure local settings
cp conf/local_settings.py.template conf/local_settings.py
# Edit conf/local_settings.py based on your deployment type

# Setup database
./manage.py migrate
./manage.py createsuperuser

# Start development server
./manage.py runserver
```

## 🎮 Usage Examples

### Basic Item Workflow
1. **Scan New Item**: System detects unknown barcode and prompts for item creation
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
pyproj/
├── app/                    # Main inventory application
│   ├── models.py          # Item, ExternalBarcode, ItemHistory models
│   ├── views.py           # Scan handling, item management views
│   ├── actions.py         # Barcode-triggered actions
│   └── templates/app/     # HTML templates
├── authuser/              # Custom authentication app
├── conf/                  # Django settings and configuration
└── static/css/           # Stylesheets
```

## 🎯 Who Is This For?

Objexx is ideal for:
- **Research Labs**: Track equipment, chemicals, and supplies
- **Maker Spaces**: Organize tools, components, and projects
- **Workshops**: Manage tools, materials, and inventory
- **Small Businesses**: Track physical assets and inventory
- **Educational Institutions**: Equipment and supply management

## 🤔 Why This Approach?

### Real-World Inspired
The system design reflects how people actually work with physical items:
- Items are scanned, not manually looked up
- Actions follow physical workflows (scan item, scan action)
- Containment mirrors real storage relationships

### Data Integrity
- **Soft Deletion**: Never lose historical data
- **Audit Trail**: Track all important changes
- **Cycle Prevention**: Prevent impossible containment relationships

### Extensible Design
- **Action System**: Easy to add new barcode-triggered actions
- **Barcode Types**: Support for multiple barcode formats
- **Container Hierarchy**: Unlimited nesting depth

## 🔧 Configuration

### Barcode Prefixes
Set in `settings.py`:
```python
BARCODE_PREFIX = "OBJ"        # Internal barcode format: OBJ123
BARCODE_VERB_PREFIX = "V="    # Action barcode format: V=AUDIT
```

### Database
Configure in `conf/local_settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'objexx',
        'USER': 'objexx_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

## 📄 License

[Add your license here]

## 🤝 Contributing

[Add contribution guidelines here]

---

**Objexx** - Because physical things need digital organization too.
