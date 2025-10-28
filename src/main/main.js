const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const os = require('os');
const fs = require('fs');
const https = require('https');
const EventDatabase = require('./database');
const PDFGenerator = require('./pdf-generator');
const CSVHandler = require('./csv-handler');

let mainWindow;
let database;
let csvHandler;
let updateInfo = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    backgroundColor: '#0f1216',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, '../preload/preload.js')
    },
    titleBarStyle: 'default',
    show: false
  });

  mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  // Initialize database
  database = new EventDatabase();
  csvHandler = new CSVHandler();

  createWindow();

  // Check for updates after window loads
  setTimeout(() => {
    checkForUpdates();
  }, 3000); // Wait 3 seconds after app starts

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    if (database) {
      database.close();
    }
    app.quit();
  }
});

// Update Checking
function checkForUpdates() {
  const packageJson = require('../../package.json');
  const currentVersion = packageJson.version;
  const repoOwner = 'mattgrilli'; // Update with your GitHub username
  const repoName = 'event'; // Update with your repo name

  const options = {
    hostname: 'api.github.com',
    path: `/repos/${repoOwner}/${repoName}/releases/latest`,
    method: 'GET',
    headers: {
      'User-Agent': 'Event-Sales-Manager-App'
    }
  };

  const req = https.request(options, (res) => {
    let data = '';

    res.on('data', (chunk) => {
      data += chunk;
    });

    res.on('end', () => {
      try {
        if (res.statusCode === 200) {
          const release = JSON.parse(data);
          const latestVersion = release.tag_name.replace(/^v/, ''); // Remove 'v' prefix if present

          if (compareVersions(latestVersion, currentVersion) > 0) {
            // New version available
            updateInfo = {
              available: true,
              currentVersion,
              latestVersion,
              downloadUrl: release.html_url,
              releaseNotes: release.body
            };

            // Notify renderer if window is ready
            if (mainWindow && !mainWindow.isDestroyed()) {
              mainWindow.webContents.send('update-available', updateInfo);
            }
          } else {
            updateInfo = {
              available: false,
              currentVersion
            };
          }
        }
      } catch (error) {
        console.error('Error checking for updates:', error);
        updateInfo = {
          available: false,
          currentVersion,
          error: error.message
        };
      }
    });
  });

  req.on('error', (error) => {
    console.error('Error checking for updates:', error);
    updateInfo = {
      available: false,
      currentVersion,
      error: error.message
    };
  });

  req.end();
}

function compareVersions(v1, v2) {
  const parts1 = v1.split('.').map(Number);
  const parts2 = v2.split('.').map(Number);

  for (let i = 0; i < 3; i++) {
    const part1 = parts1[i] || 0;
    const part2 = parts2[i] || 0;

    if (part1 > part2) return 1;
    if (part1 < part2) return -1;
  }

  return 0;
}

// IPC Handlers

// Settings
ipcMain.handle('get-settings', async () => {
  return database.getAllSettings();
});

ipcMain.handle('save-settings', async (event, settings) => {
  for (const [key, value] of Object.entries(settings)) {
    database.setSetting(key, value);
  }
  return { success: true };
});

// Tickets
ipcMain.handle('create-attendee', async (event, data) => {
  const { firstName, lastName, quantity, customFields } = data;
  return database.createAttendeeWithTickets(firstName, lastName, quantity, customFields);
});

ipcMain.handle('list-tickets', async (event, eventCode = null) => {
  return database.listTickets(eventCode);
});

ipcMain.handle('get-event-codes', async () => {
  return database.getEventCodes();
});

ipcMain.handle('get-ticket', async (event, ticketNumber) => {
  return database.getTicket(ticketNumber);
});

ipcMain.handle('update-ticket', async (event, ticketNumber, fields) => {
  return database.updateTicket(ticketNumber, fields);
});

ipcMain.handle('delete-tickets', async (event, ticketNumbers) => {
  database.deleteTickets(ticketNumbers);
  return { success: true };
});

ipcMain.handle('mark-printed', async (event, ticketNumbers, printed) => {
  database.markPrinted(ticketNumbers, printed);
  return { success: true };
});

ipcMain.handle('check-in', async (event, identifier) => {
  return database.checkIn(identifier);
});

ipcMain.handle('get-stats', async () => {
  return database.getStats();
});

ipcMain.handle('get-order-summary', async () => {
  return database.getOrderSummary();
});

ipcMain.handle('get-checked-in-tickets', async () => {
  return database.getCheckedInTickets();
});

// PDF Generation
ipcMain.handle('generate-tickets-pdf', async (event, tickets, template) => {
  const settings = database.getAllSettings();
  const pdfGenerator = new PDFGenerator(settings);

  const result = await dialog.showSaveDialog(mainWindow, {
    title: 'Save Tickets PDF',
    defaultPath: 'tickets.pdf',
    filters: [{ name: 'PDF', extensions: ['pdf'] }]
  });

  if (result.canceled) {
    return { canceled: true };
  }

  await pdfGenerator.generateTicketsPDF(tickets, result.filePath, template);

  // Mark as printed
  const ticketNumbers = tickets.map(t => t.ticket_number);
  database.markPrinted(ticketNumbers, true);

  return { success: true, path: result.filePath };
});

ipcMain.handle('generate-labels-pdf', async (event, attendees, template) => {
  const settings = database.getAllSettings();
  const pdfGenerator = new PDFGenerator(settings);

  const result = await dialog.showSaveDialog(mainWindow, {
    title: 'Save Labels PDF',
    defaultPath: 'labels.pdf',
    filters: [{ name: 'PDF', extensions: ['pdf'] }]
  });

  if (result.canceled) {
    return { canceled: true };
  }

  await pdfGenerator.generateLabelsPDF(attendees, result.filePath, template);
  return { success: true, path: result.filePath };
});

// PDF Preview (opens in default PDF viewer)
ipcMain.handle('preview-tickets-pdf', async (event, tickets, template) => {
  const settings = database.getAllSettings();
  const pdfGenerator = new PDFGenerator(settings);

  // Generate to temp file
  const tempPath = path.join(os.tmpdir(), `tickets-preview-${Date.now()}.pdf`);
  await pdfGenerator.generateTicketsPDF(tickets, tempPath, template);

  // Open with default PDF viewer
  await shell.openPath(tempPath);

  return { success: true, path: tempPath };
});

ipcMain.handle('preview-labels-pdf', async (event, attendees, template) => {
  const settings = database.getAllSettings();
  const pdfGenerator = new PDFGenerator(settings);

  // Generate to temp file
  const tempPath = path.join(os.tmpdir(), `labels-preview-${Date.now()}.pdf`);
  await pdfGenerator.generateLabelsPDF(attendees, tempPath, template);

  // Open with default PDF viewer
  await shell.openPath(tempPath);

  return { success: true, path: tempPath };
});

// CSV Import/Export
ipcMain.handle('import-csv', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Import CSV or Excel',
    filters: [
      { name: 'Spreadsheets', extensions: ['csv', 'xlsx', 'xls'] },
      { name: 'CSV', extensions: ['csv'] },
      { name: 'Excel', extensions: ['xlsx', 'xls'] }
    ],
    properties: ['openFile']
  });

  if (result.canceled) {
    return { canceled: true };
  }

  const importResult = await csvHandler.importFile(result.filePaths[0], database);
  return { success: true, ...importResult };
});

ipcMain.handle('export-tickets-csv', async () => {
  const tickets = database.listTickets();

  const result = await dialog.showSaveDialog(mainWindow, {
    title: 'Export Tickets CSV',
    defaultPath: 'tickets.csv',
    filters: [{ name: 'CSV', extensions: ['csv'] }]
  });

  if (result.canceled) {
    return { canceled: true };
  }

  csvHandler.exportTickets(tickets, result.filePath);
  return { success: true, path: result.filePath };
});

ipcMain.handle('export-checkins-csv', async () => {
  const tickets = database.getCheckedInTickets();

  const result = await dialog.showSaveDialog(mainWindow, {
    title: 'Export Check-Ins CSV',
    defaultPath: 'checkins.csv',
    filters: [{ name: 'CSV', extensions: ['csv'] }]
  });

  if (result.canceled) {
    return { canceled: true };
  }

  csvHandler.exportCheckedIn(tickets, result.filePath);
  return { success: true, path: result.filePath };
});

ipcMain.handle('export-order-summary-csv', async () => {
  const summary = database.getOrderSummary();

  const result = await dialog.showSaveDialog(mainWindow, {
    title: 'Export Order Summary CSV',
    defaultPath: 'order-summary.csv',
    filters: [{ name: 'CSV', extensions: ['csv'] }]
  });

  if (result.canceled) {
    return { canceled: true };
  }

  csvHandler.exportOrderSummary(summary, result.filePath);
  return { success: true, path: result.filePath };
});

// Open external links
ipcMain.handle('open-external', async (event, url) => {
  await shell.openExternal(url);
  return { success: true };
});

// Show message box
ipcMain.handle('show-message', async (event, options) => {
  return await dialog.showMessageBox(mainWindow, options);
});

// Template Management
ipcMain.handle('save-template', async (event, name, type, elements) => {
  const templateId = database.saveTemplate(name, type, elements);
  return { success: true, templateId };
});

ipcMain.handle('get-template', async (event, templateId) => {
  return database.getTemplate(templateId);
});

ipcMain.handle('get-templates-by-type', async (event, type) => {
  return database.getTemplatesByType(type);
});

ipcMain.handle('get-template-by-name', async (event, name, type) => {
  return database.getTemplateByName(name, type);
});

ipcMain.handle('delete-template', async (event, templateId) => {
  database.deleteTemplate(templateId);
  return { success: true };
});

// Event Management
ipcMain.handle('ensure-event', async (event, eventCode, eventName) => {
  database.ensureEvent(eventCode, eventName);
  return { success: true };
});

ipcMain.handle('is-event-locked', async (event, eventCode) => {
  return database.isEventLocked(eventCode);
});

ipcMain.handle('lock-event', async (event, eventCode) => {
  database.lockEvent(eventCode);
  return { success: true };
});

ipcMain.handle('unlock-event', async (event, eventCode) => {
  database.unlockEvent(eventCode);
  return { success: true };
});

// Update Checking
ipcMain.handle('get-update-info', async () => {
  return updateInfo;
});

ipcMain.handle('check-for-updates', async () => {
  checkForUpdates();
  // Wait a bit for the request to complete
  await new Promise(resolve => setTimeout(resolve, 2000));
  return updateInfo;
});
