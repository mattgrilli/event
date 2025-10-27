# Event & Sales Manager - Electron App

A beautiful, modern Electron app for managing event tickets and product sales. This is a complete refactor of the Python/tkinter version with a professional dark mode UI.

## Features

- **Event Ticketing Mode**: Generate tickets with QR codes, check-in system, attendance tracking
- **Product Sales Mode**: Manage orders, print distribution labels, export order summaries
- **Professional UI**: Beautiful dark mode interface with customizable accent colors
- **Label Printing**: Avery 5160 compatible envelope labels
- **CSV/Excel Import & Export**: Easily import participant data and export reports
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Easy Distribution**: Build installers for your wife to install easily

## Installation

### Prerequisites

- Node.js 18+ ([Download](https://nodejs.org/))

### Setup

1. **Install Dependencies**

```bash
npm install
```

2. **Run the App**

```bash
npm start
```

For development with auto-reload:

```bash
npm run dev
```

## Building for Distribution

### Build for All Platforms

```bash
npm run build
```

### Build for Specific Platforms

**macOS:**
```bash
npm run build:mac
```

This creates:
- `.dmg` installer (drag and drop to Applications)
- `.zip` portable version

**Windows:**
```bash
npm run build:win
```

This creates:
- NSIS installer (`.exe` - standard Windows installer)
- Portable version (no installation required)

**Linux:**
```bash
npm run build:linux
```

This creates:
- AppImage (portable, works on most distributions)
- Debian package (`.deb` for Ubuntu/Debian)

### Distribution Files

After building, find your distributable files in the `dist` folder:

- **For your wife (Windows)**: Use the `.exe` installer in `dist/`
- **For your wife (Mac)**: Use the `.dmg` file in `dist/`

## Project Structure

```
event-sales-manager/
├── src/
│   ├── main/              # Electron main process (Node.js backend)
│   │   ├── main.js        # App entry point
│   │   ├── database.js    # SQLite database layer
│   │   ├── pdf-generator.js  # PDF generation for tickets/labels
│   │   └── csv-handler.js    # CSV import/export
│   ├── preload/           # Preload scripts (secure IPC)
│   │   └── preload.js
│   └── renderer/          # Frontend UI
│       ├── index.html     # Main HTML
│       └── app.js         # Frontend JavaScript
├── public/
│   └── css/
│       └── styles.css     # Beautiful dark mode styles
├── package.json
└── README.md
```

## How It Works

### Architecture

The app uses Electron's architecture:

1. **Main Process** (`src/main/main.js`):
   - Manages the application window
   - Handles database operations (SQLite)
   - Generates PDFs for tickets and labels
   - Manages file dialogs and system integration

2. **Renderer Process** (`src/renderer/`):
   - The UI that users interact with
   - Modern HTML/CSS/JavaScript
   - Communicates with main process via IPC (Inter-Process Communication)

3. **Preload Script** (`src/preload/preload.js`):
   - Secure bridge between renderer and main process
   - Exposes only specific APIs to the frontend

### Database

- **SQLite** database stored in user's app data folder
- Automatically created on first run
- Same schema as Python version (backward compatible)
- File location:
  - Windows: `%APPDATA%/event-sales-manager/pta_tickets.db`
  - macOS: `~/Library/Application Support/event-sales-manager/pta_tickets.db`
  - Linux: `~/.config/event-sales-manager/pta_tickets.db`

### PDF Generation

- Uses `pdfkit` for PDF creation
- QR codes generated with `qrcode` library
- Supports both ticket printing and Avery 5160 labels

## UI Improvements Over tkinter

### Dark Mode First
- Professional dark theme that's easy on the eyes
- Customizable accent color (defaults to orange)
- High contrast for better readability

### Modern Layout
- Clean tabbed interface
- Responsive tables with sorting and filtering
- Smooth transitions and hover effects
- Better spacing and typography

### Better UX
- Live search/filter on tables
- Multi-select with Ctrl+Click and Shift+Click
- Inline editing with better dialogs
- Clear visual feedback for actions
- Professional color-coded check-in log

### Professional Styling
- Consistent button styles
- Clear visual hierarchy
- Better form layouts
- Custom scrollbars
- Info boxes and help text

## Usage

### Quick Start

1. **Configure Settings**
   - Go to Settings tab
   - Choose mode: Ticketing or Sales
   - Set organization name, event name
   - Customize accent color
   - Enable/disable QR codes
   - Save settings

2. **Import Participants** (Optional)
   - Prepare CSV/Excel file (see Help tab for format)
   - Click "Import CSV/Excel"
   - Review imported data

3. **Generate Tickets**
   - Use "Register Participant" form to add individually
   - Or import bulk via CSV
   - Each participant gets unique ticket codes

4. **Print Materials**
   - Click "Print All Unprinted" for tickets
   - Click "Print Labels for All" for envelope labels
   - PDFs are generated and saved where you choose

5. **Check-In** (Ticketing Mode)
   - Go to Check-In tab
   - Scan QR codes or type ticket codes
   - Real-time log shows check-in status

### Ticketing Mode vs Sales Mode

**Ticketing Mode:**
- For events like dances, shows, carnivals
- Includes QR codes on tickets
- Check-in functionality enabled
- Tracks attendance

**Sales Mode:**
- For product sales (pretzels, popcorn, etc.)
- No QR codes or check-in
- Teacher field for distribution
- Order summary reports by teacher

## Customization

### Accent Color
- Go to Settings → Accent Color
- Use color picker or enter hex code
- Updates entire app theme instantly

### Label Printing Adjustments
- Settings → Label Printing Settings
- Adjust margins and gaps for your specific printer
- Use "Show Borders" to test alignment
- Quick presets: Default, Tight, Spaced

## Troubleshooting

### App Won't Start
- Make sure Node.js is installed
- Run `npm install` to ensure all dependencies are installed
- Check console for error messages

### Database Issues
- Database file: Located in system app data folder
- To reset: Delete `pta_tickets.db` and restart app
- To backup: Copy `pta_tickets.db` to safe location

### PDF Issues
- Make sure you have write permissions to save location
- Test with different save locations
- Check console for PDF generation errors

### Labels Not Aligned
- Use "Show Borders" option to test
- Adjust margins and gaps in settings
- Print test page on regular paper first
- Every printer is slightly different

## Development

### Tech Stack
- **Electron**: Desktop app framework
- **better-sqlite3**: Fast SQLite database
- **pdfkit**: PDF generation
- **qrcode**: QR code generation
- **xlsx**: Excel file support
- **csv-parser**: CSV import

### Adding Features

1. **Add IPC Handler** in `src/main/main.js`:
```javascript
ipcMain.handle('my-new-feature', async (event, data) => {
  // Handle the request
  return result;
});
```

2. **Expose in Preload** in `src/preload/preload.js`:
```javascript
myNewFeature: (data) => ipcRenderer.invoke('my-new-feature', data)
```

3. **Call from Renderer** in `src/renderer/app.js`:
```javascript
const result = await window.electronAPI.myNewFeature(data);
```

### Building Icons

Place icons in `build/` folder:
- `icon.icns` - macOS icon
- `icon.ico` - Windows icon
- `icon.png` - Linux icon (512x512 PNG)

## License

MIT License - Created by Matthew Grilli

## Support

For issues or questions:
- Email: him@mattgrilli.com
- Check the Help tab in the app for usage guides

---

**Built with ❤️ for PTAs everywhere**

Now with a UI that doesn't look like trash! 🎉
