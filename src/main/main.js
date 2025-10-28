const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const { autoUpdater } = require('electron-updater');
const path = require('path');
const os = require('os');
const fs = require('fs');
const EventDatabase = require('./database');
const PDFGenerator = require('./pdf-generator');
const CSVHandler = require('./csv-handler');

let mainWindow;
let database;
let csvHandler;

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

  // Initialize auto-updater
  initializeAutoUpdater();

  // Check for updates after window loads
  setTimeout(() => {
    autoUpdater.checkForUpdates();
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

// Auto-Updater Configuration
function initializeAutoUpdater() {
  // Configure auto-updater
  autoUpdater.autoDownload = false; // Don't auto-download, ask user first
  autoUpdater.autoInstallOnAppQuit = true;

  // Log for debugging
  autoUpdater.logger = require('electron-log');
  autoUpdater.logger.transports.file.level = 'info';

  // Update available
  autoUpdater.on('update-available', (info) => {
    console.log('Update available:', info);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('update-available', {
        version: info.version,
        releaseNotes: info.releaseNotes,
        releaseDate: info.releaseDate
      });
    }
  });

  // Update not available
  autoUpdater.on('update-not-available', (info) => {
    console.log('Update not available');
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('update-not-available');
    }
  });

  // Download progress
  autoUpdater.on('download-progress', (progressObj) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('update-download-progress', {
        percent: progressObj.percent,
        transferred: progressObj.transferred,
        total: progressObj.total,
        bytesPerSecond: progressObj.bytesPerSecond
      });
    }
  });

  // Update downloaded
  autoUpdater.on('update-downloaded', (info) => {
    console.log('Update downloaded');
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('update-downloaded', {
        version: info.version
      });
    }
  });

  // Error occurred
  autoUpdater.on('error', (err) => {
    console.error('Update error:', err);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('update-error', {
        message: err.message
      });
    }
  });
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
// Auto-Updater IPC Handlers
ipcMain.handle('check-for-updates', async () => {
  try {
    const result = await autoUpdater.checkForUpdates();
    return { success: true, updateInfo: result?.updateInfo };
  } catch (error) {
    console.error('Error checking for updates:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('download-update', async () => {
  try {
    await autoUpdater.downloadUpdate();
    return { success: true };
  } catch (error) {
    console.error('Error downloading update:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('install-update', async () => {
  autoUpdater.quitAndInstall(false, true);
  return { success: true };
});
