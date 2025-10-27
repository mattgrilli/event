# Event & Sales Manager

A professional desktop application for managing school events, ticketing, and fundraising sales. Built for PTAs, schools, and organizations that need efficient participant tracking, label printing, and check-in management.

## Features

### Dual Operating Modes

**Ticketing Mode** - Traditional event ticketing with check-in
- Generate numbered tickets with unique QR codes
- Real-time check-in with barcode scanner support
- Track attendance and export check-in reports
- Perfect for: school dances, carnivals, raffles, field trips

**Sales Mode** - Fundraising and order management
- Track bulk orders (e.g., 5 pretzels per student)
- Quantity tracking and order summaries
- Print labels for bag/envelope labeling
- Perfect for: pretzel sales, cookie dough, wrapping paper, school supplies

### Core Features

- **Multi-Event Support** - Filter and manage multiple events simultaneously
- **Envelope Labels** - Avery 5160 compatible label printing (30 per sheet)
- **CSV/Excel Import** - Bulk import participant data
- **Custom Fields** - Configure which fields to collect (classroom, teacher, grade, etc.)
- **Customizable Branding** - Set organization name, event name, and accent colors
- **Quantity Management** - Sales mode shows quantities in tables and on labels
- **Check-In System** - QR code scanning or manual ticket entry
- **Export Reports** - CSV export for tickets, check-ins, and order summaries

## Installation

### For End Users (Recommended)

**Coming Soon**: Download the installer for your platform:
- Windows: `Event-Sales-Manager-Setup.exe`
- macOS: `Event-Sales-Manager.dmg`
- Linux: `Event-Sales-Manager.AppImage`

Run the installer and launch the app - no additional setup required!

### For Developers

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd event
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Run in development mode**
   ```bash
   npm start
   ```

4. **Build installers**
   ```bash
   npm run build
   ```

## Quick Start

### First Time Setup

1. **Launch the app** and go to the **Settings** tab
2. **Choose your mode**:
   - **Ticketing Mode** for events with check-in
   - **Sales Mode** for fundraising/bulk orders
3. **Configure organization details**:
   - Organization Name (e.g., "Lincoln Elementary PTA")
   - Event Name (e.g., "Fall Carnival" or "Pretzel Sale")
   - Event Code (e.g., "EVT" or "PRETZEL") - appears on ticket codes
4. **Enable custom fields** you need:
   - Classroom/Room
   - Teacher
   - Grade
   - Address, Email, Phone (for labels)
5. **Click Save Settings**

### Registering Participants

**Manual Entry**:
1. Go to **Manage** tab
2. Fill in participant details (first name, last name, custom fields)
3. Set quantity (how many tickets/items)
4. Click **Generate**

**Bulk Import**:
1. Prepare a CSV or Excel file (see format below)
2. Click **Import CSV/Excel**
3. Select your file
4. Review import summary

### Printing

**Tickets** (Ticketing Mode):
1. Select tickets in the table or use "Print All Unprinted"
2. Choose ticket template (Default Layout or custom)
3. Click **Print Selected** or **Preview Selected**
4. Each ticket shows: name, QR code, ticket number, event info

**Labels** (Both Modes):
1. Go to **Labels** tab
2. Select participants or use "Print Labels for All"
3. Load Avery 5160 label sheets in printer
4. Click **Print Labels** or **Preview Labels**
5. In **Sales Mode**, labels show quantity (e.g., "Qty: 5")

### Check-In (Ticketing Mode Only)

1. Go to **Check-In** tab
2. Scan QR codes with barcode scanner, OR
3. Type ticket code or number and press Enter
4. System shows check-in confirmation
5. Export check-ins anytime with **Export Check-Ins** button

## Working with Multiple Events

The **Event Filter** dropdown (top of Manage and Labels tabs) lets you work with one event at a time:

1. **Change Event Code** in Settings when starting a new event
2. Generate tickets - they'll have the new event code prefix
3. **Select the event** from the dropdown to filter tables
4. View only tickets/participants for that specific event

**Example**:
- Fall Carnival tickets: `FALL-ABC123`
- Pretzel Sale orders: `PRETZEL-XYZ789`
- Filter dropdown shows: "All Events", "FALL", "PRETZEL"

## CSV Import Format

### Ticketing Mode

**Minimum required**:
```csv
Quantity,First,Last
1,Julia,McSweeney
1,Emmett,Potts
```

**With custom fields**:
```csv
Quantity,First,Last,Classroom,Teacher
1,Julia,McSweeney,101,Ms. Johnson
2,Emmett,Potts,202,Mr. Smith
```

### Sales Mode

**Bulk orders**:
```csv
Quantity,First,Last,Classroom,Teacher
5,Julia,McSweeney,101,Ms. Johnson
12,Emmett,Potts,202,Mr. Smith
```

In Sales Mode, Quantity = number of items ordered (creates that many ticket records for quantity tracking).

### Column Name Variations

The app recognizes these column names (case-insensitive):

- **Quantity**: `Quantity`, `Qty`, `Count`
- **First Name**: `First`, `First Name`, `FirstName`
- **Last Name**: `Last`, `Last Name`, `LastName`
- **Full Name**: `Name`, `Student Name`, `Full Name` (will be split automatically)
- **Classroom**: `Classroom`, `Room`, `Class`
- **Teacher**: `Teacher`, `Instructor`
- **Grade**: `Grade`, `Grade Level`
- **Address**: `Address`, `Street Address`
- **Email**: `Email`, `Email Address`
- **Phone**: `Phone`, `Phone Number`

## Envelope Labels

### Label Template

**Avery 5160** (or compatible)
- 30 labels per sheet (3 columns × 10 rows)
- Label size: 2.625" × 1"
- Available at office supply stores and Amazon

### Compatible Brands
- Avery 5160
- Office Depot/OfficeMax (equivalent)
- Staples (equivalent template)
- Amazon Basics address labels (2.625" × 1")

### What Gets Printed

**Ticketing Mode**:
- Student name (bold, centered)
- Selected label fields (classroom, teacher, grade, etc.)
- Event name

**Sales Mode**:
- Student name (bold, centered)
- Selected label fields (classroom, teacher, etc.)
- **Quantity ordered** (e.g., "Qty: 5")

**Note**: Labels are deduplicated - one label per student regardless of ticket quantity.

### Adjusting Label Alignment

If labels don't line up perfectly with your printer:

1. Go to **Settings** tab
2. Scroll to **Label Printing Adjustments**
3. Use presets (Default, Tight, Spaced) or adjust manually:
   - **Vertical Gap** - space between rows
   - **Horizontal Gap** - space between columns
   - **Top Margin** - shift all labels down
   - **Left Margin** - shift all labels right
4. Click **Save Settings**
5. Test print on regular paper first!

## Settings & Configuration

### Mode Settings

**Ticketing Mode**:
- Enables Check-In tab
- Prints QR codes on tickets
- Labels show event name
- Focus on attendance tracking

**Sales Mode**:
- Hides Check-In tab (not applicable)
- Shows quantity column in tables
- Labels show quantity ordered
- Export order summaries by teacher/classroom

### Custom Fields

Enable only the fields you need:
- **Classroom/Room** - Organizes participants by class
- **Teacher** - Groups orders by teacher (great for sales mode)
- **Grade** - Track which grades participated
- **Address** - For mailing labels or parent contact
- **Email** - Electronic communication
- **Phone** - Phone contact
- **Notes** - Special instructions or notes

**Label Fields**: Choose which fields appear on printed labels.

### Branding

- **Organization Name** - Appears on tickets
- **Event Name** - Appears on tickets and labels
- **Event Code** - Prefix for ticket codes (e.g., "EVT-ABC123")
- **Accent Color** - Custom color picker for branding

## Typical Workflows

### Ticketing Mode: School Dance

1. **Settings**: Set mode to "Ticketing", event name "Fall Dance", event code "DANCE"
2. **Import**: Upload student roster CSV
3. **Print**: Print all tickets and envelope labels
4. **Distribute**: Send labels home for families to write names on envelopes
5. **Day of Event**:
   - Check-In tab active
   - Scan QR codes as students arrive
   - Track attendance in real-time
6. **After Event**: Export check-ins for attendance records

### Sales Mode: Pretzel Fundraiser

1. **Settings**: Set mode to "Sales", event name "Pretzel Sale", event code "PRETZEL"
2. **Import**: Upload order form CSV with quantities (e.g., 5 pretzels, 12 pretzels)
3. **View Quantities**: Manage tab shows "Qty" column with order amounts
4. **Print Labels**: Labels show "Qty: 5", "Qty: 12", etc. for labeling bags
5. **Sort by Teacher**: Filter or export to group orders by classroom
6. **Distribution**: Use labels to mark pretzel bags before sending to classrooms
7. **Reports**: Export order summary CSV grouped by teacher

## Database & Data Storage

### Database Location

All data is stored in a SQLite database (`pta_tickets.db`) located in:
- **Windows**: `%APPDATA%\event-sales-manager\`
- **macOS**: `~/Library/Application Support/event-sales-manager/`
- **Linux**: `~/.config/event-sales-manager/`

### Backup

**To backup your data**:
1. Close the app
2. Copy `pta_tickets.db` from the location above
3. Store in a safe location

**To restore**:
1. Close the app
2. Replace `pta_tickets.db` with your backup copy
3. Restart the app

**To start fresh**:
1. Close the app
2. Delete `pta_tickets.db`
3. Restart the app (creates new database)

### Data Export

Regular CSV exports are recommended:
- **Manage tab** → Export CSV (all tickets/participants)
- **Check-In tab** → Export Check-Ins (attendance report)
- **Manage tab** → Export Order Summary (sales mode - grouped by teacher)

## Tips & Best Practices

### General
- **Test first**: Always preview PDFs before printing
- **Regular exports**: Export CSV regularly to backup participant data
- **Multiple events**: Use event filter dropdown to work on one event at a time
- **Search**: Use search box to quickly find specific participants

### Ticketing Mode
- **Privacy**: Tickets show name only (no room numbers)
- **Distribution**: Use envelope labels for easy sorting by classroom
- **Check-In**: Barcode scanner should be in "keyboard mode" (acts like keyboard input)
- **Manual entry**: Check-In accepts ticket codes or numbers if scanner fails

### Sales Mode
- **Bulk orders**: Import CSV with quantities (system creates multiple ticket records)
- **Quantity display**: Tables and labels automatically show order quantities
- **Teacher reports**: Export order summary to see totals by teacher/classroom
- **Label organization**: Print labels to mark bags/envelopes before distribution

### Label Printing
- **Test print**: Print on regular paper first to check alignment
- **Printer settings**: Use "Actual Size" or "100%" scaling (no fit-to-page)
- **Label sheets**: Buy extra sheets - practice makes perfect
- **Adjustments**: Use Settings → Label Printing Adjustments if alignment is off

## Troubleshooting

### Import Issues

**Problem**: "Could not detect columns"
- Ensure CSV has headers in first row
- Check column names match expected variations
- Verify file is actually CSV (not .xlsx saved as .csv)

**Problem**: "Skipped rows during import"
- Quantity must be a number
- At least First/Last name or Full Name required
- Check for blank rows in CSV

### Label Printing

**Problem**: Labels don't line up with sheet
- Go to Settings → Label Printing Adjustments
- Try "Tight" or "Spaced" presets first
- Test on regular paper before wasting label sheets
- Ensure printer settings: "Actual Size", no scaling

**Problem**: Labels are cut off
- Check printer margins in print dialog
- Some printers can't print to edge - labels may need adjustment
- Try adjusting Top/Left margins in Settings

### QR Codes Not Scanning

**Problem**: Scanner doesn't read QR codes
- Ensure scanner is in "keyboard mode" (check scanner manual)
- Test scanner in a text editor - should type characters
- Try manual entry using ticket code or number
- Check "Include QR Codes" is enabled in Settings

**Problem**: QR code scans but check-in fails
- Verify ticket code matches format (e.g., "EVT-ABC123")
- Check ticket wasn't deleted
- Try entering ticket number instead of code

### Performance

**Problem**: App is slow with many tickets
- Export old events to CSV and start new database for new events
- Use Event Filter to work with one event at a time
- Large imports (1000+) may take a few seconds

## Development

### Tech Stack

- **Electron** - Desktop application framework
- **Node.js** - JavaScript runtime
- **Better-sqlite3** - Fast, embedded database
- **PDFKit** - PDF generation for tickets and labels
- **HTML/CSS/JS** - User interface (no frameworks)

### Project Structure

```
event/
├── src/
│   ├── main/           # Main process (Node.js)
│   │   ├── main.js     # App entry point, IPC handlers
│   │   ├── database.js # SQLite database operations
│   │   └── pdf-generator.js # PDF rendering
│   ├── renderer/       # Renderer process (UI)
│   │   ├── index.html  # Main UI structure
│   │   ├── app.js      # Application logic
│   │   └── designer.js # Template designer (hidden feature)
│   └── preload/        # Preload scripts
│       └── preload.js  # IPC API exposure
├── public/
│   └── css/
│       └── styles.css  # Application styles
├── package.json
└── README.md
```

### Building

**Development**:
```bash
npm start
```

**Package for distribution**:
```bash
npm run build
```

Creates installers in `dist/` directory for current platform.

**Package for all platforms** (requires platform-specific setup):
```bash
npm run build:win   # Windows
npm run build:mac   # macOS
npm run build:linux # Linux
```

### Database Schema

**Tables**:
- `attendees` - Participant information
- `tickets` - Ticket records (one per quantity)
- `settings` - Application settings (key-value)
- `templates` - Custom ticket/label templates (hidden feature)

**Backward Compatible**: Electron version uses same schema as original Python version.

## Support

Created by Matthew Grilli
Email: him@mattgrilli.com

## License

All rights reserved.

---

Built with ❤️ for PTAs and school organizations everywhere
