# Quick Start Guide

## For Your Wife (Non-Technical User)

### Installing the App

**Windows:**
1. Double-click the `.exe` installer file
2. Follow the installation wizard
3. Launch "Event & Sales Manager" from Start Menu

**Mac:**
1. Open the `.dmg` file
2. Drag the app icon to Applications folder
3. Launch from Applications or Spotlight

### First Time Setup

1. **Open the app** - You'll see a dark themed window (much prettier than the old version!)

2. **Go to Settings tab** (click "Settings" at the top)
   - Choose your mode:
     - **Ticketing Mode** - For events where you need to check people in
     - **Sales Mode** - For selling products like pretzels or popcorn
   - Fill in:
     - Organization Name (e.g., "Lincoln Elementary PTA")
     - Event Name (e.g., "Fall Festival 2024")
     - Event Code (short code like "FALL" - will appear on tickets)
   - Pick your favorite color for the theme
   - Click **Save Settings**

### Adding Participants

**Option 1: Type them in one by one**
1. Go to "Manage" tab
2. Fill in the form:
   - First Name
   - Last Name
   - Classroom (if you want)
   - Quantity (how many tickets)
3. Click "Generate"

**Option 2: Import from a spreadsheet** (EASIER for lots of people!)
1. Create a CSV or Excel file with columns:
   ```
   Quantity,Student Name,Classroom
   2,Julia McSweeney,101
   4,Emmett Potts,202
   ```
2. Click "Import CSV/Excel"
3. Choose your file
4. Done! All participants imported

### Printing Tickets

1. Go to "Manage" tab
2. Click "Print All Unprinted"
3. Choose where to save the PDF
4. Open the PDF and print it

Each ticket will have:
- Student name
- Unique ticket code
- QR code (if enabled)
- Your organization and event name

### Printing Envelope Labels

1. Go to "Labels" tab
2. Load Avery 5160 labels in your printer
   - You can buy these at any office supply store
   - 30 labels per sheet
3. Click "Print Labels for All"
4. Choose where to save the PDF
5. Open and print on the label sheets

### Check-In (During Event) - Ticketing Mode Only

1. Go to "Check-In" tab
2. Have someone scan the QR codes with a barcode scanner
   - Or type the ticket codes manually
3. Press Enter after each scan
4. You'll see:
   - ✓ Green = Checked in successfully
   - • Orange = Already checked in (shows when)
   - ✗ Red = Ticket not found

### Exporting Reports

**All tickets:**
- Click "Export CSV" on Manage tab

**Who checked in:**
- Click "Export Check-Ins" on Check-In tab

**Order summary by teacher** (Sales Mode):
- Click "Export Order Summary" on Manage tab

## Common Tasks

### Changing the Color Theme
Settings → Accent Color → Pick a color → Save Settings

### Editing Someone's Info
1. Click on their row in the table (Manage tab)
2. Click "Edit Selected"
3. Change their info
4. It updates automatically

### Deleting Tickets
1. Click on row(s) in the table
   - Hold Ctrl (Windows) or Cmd (Mac) to select multiple
2. Click "Delete Selected"
3. Confirm

### Searching for Someone
Use the search box at the top right of the table - just start typing their name

## Tips

- **The database saves automatically** - No need to click save
- **Want to start fresh?** Delete the database file (see technical docs)
- **Backup your data** - Use "Export CSV" before big events
- **Test print labels** on regular paper first to check alignment
- **Label alignment off?** Go to Settings → Label Printing Settings → try the "Tight" or "Spaced" presets

## Getting Help

- Click the "Help" tab in the app for detailed CSV format instructions
- Check the "About" tab for contact information
- Email Matthew if something breaks: him@mattgrilli.com

## Why This is Better Than the Old Version

✓ **Looks professional** - Dark mode, modern design
✓ **Easier to read** - Better fonts, spacing, colors
✓ **Faster** - Everything loads quicker
✓ **Better search** - Find people instantly
✓ **Clearer buttons** - Know exactly what each button does
✓ **No ugly tkinter windows** - Looks like a real app!

Enjoy! 🎉
