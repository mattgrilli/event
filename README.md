# PTA Ticket Manager

A professional ticketing system for school events with QR codes, envelope labels, and real-time check-in.

## Quick Start

### Installation

1. **Install Python** (3.8 or higher)
   - Download from [python.org](https://www.python.org/downloads/)

2. **Install Required Packages**
   ```bash
   pip install qrcode pillow reportlab
   ```

3. **Optional: For Excel Import**
   ```bash
   pip install pandas openpyxl
   ```

### Running the App

```bash
python pta_tickets.py
```

## Features

- ✅ Generate custom tickets with QR codes
- ✅ Print Avery 5160 envelope labels
- ✅ Real-time check-in with scanner support
- ✅ Import from CSV/Excel
- ✅ Export attendance reports
- ✅ Customizable branding and colors

## CSV Import Format

### Required Columns

**Option 1: Full Name**
```csv
Quantity,Student Name
2,Julia McSweeney
4,Emmett Potts
```

**Option 2: First/Last Name**
```csv
Quantity,First,Last
2,Julia,McSweeney
4,Emmett,Potts
```

### Optional Column

Add classroom/room numbers for label sorting:

```csv
Quantity,Student Name,Classroom
2,Julia McSweeney,101
2,Haley DiPaolo,202
4,Emmett Potts,101
```

### Column Name Variations

The app accepts these variations (case-insensitive):
- **Quantity**: `Quantity`, `Qty`
- **Name**: `Student Name`, `Name`, `Full Name`
- **First**: `First`, `First Name`
- **Last**: `Last`, `Last Name`
- **Classroom**: `Classroom`, `Room`, `Class`

## Envelope Labels

### Label Template

**Avery 5160** (or compatible)
- 30 labels per sheet (3 columns × 10 rows)
- Label size: 2.625" × 1"
- Available at office supply stores

### Compatible Brands
- Avery 5160
- Office Depot/OfficeMax (same size)
- Staples (equivalent template)
- Amazon Basics address labels

### What Gets Printed

Labels show:
1. **Student name** (bold, centered)
2. **Room number** (if provided in CSV)
3. **Event name** (from Settings)

**Note**: One label per student, regardless of ticket quantity.

## Workflow

### Typical Event Setup

1. **Import Data**
   - Prepare CSV with student names and quantities
   - Go to Manage tab → Click "Import CSV/Excel"

2. **Customize Settings**
   - Go to Settings tab
   - Update Organization Name, Event Name
   - Choose accent color with color picker
   - Save settings

3. **Print Materials**
   - Click "Print All Unprinted" for tickets
   - Click "Print Envelope Labels" for labels
   - Load label sheets in printer

4. **Day of Event**
   - Go to Check-In tab
   - Scan QR codes or enter ticket IDs
   - Export check-ins for attendance report

## Tips

- **Privacy**: Tickets show name only (no room numbers)
- **Distribution**: Labels show room numbers for easy sorting
- **Search**: Use Filter box to find specific tickets
- **Backup**: Export CSV regularly to save your data
- **Check-In**: Accepts both QR codes and manual ticket IDs

## Troubleshooting

### Import Issues
- Ensure CSV has headers in first row
- Check that column names match (case doesn't matter)
- Verify Quantity column contains numbers

### Label Printing
- Use Avery 5160 template or compatible
- Check printer settings: "Actual Size" (no scaling)
- Test print on regular paper first

### QR Codes Not Working
- Ensure "Include QR Codes" is enabled in Settings
- Make sure scanner is set to "keyboard mode"
- Try entering ticket ID manually if scanner fails

## Database

All data is stored in `pta_tickets.db` (SQLite database) in the same folder as the app.

**To start fresh**: Delete `pta_tickets.db` and restart the app.

**To backup**: Copy `pta_tickets.db` to a safe location.

## Support

Created by Matthew Grilli  
Email: him@mattgrilli.com

---

Built with ❤️ for PTAs everywhere