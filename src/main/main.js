const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
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

ipcMain.handle('list-tickets', async () => {
  return database.listTickets();
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
ipcMain.handle('generate-tickets-pdf', async (event, tickets) => {
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

  await pdfGenerator.generateTicketsPDF(tickets, result.filePath);

  // Mark as printed
  const ticketNumbers = tickets.map(t => t.ticket_number);
  database.markPrinted(ticketNumbers, true);

  return { success: true, path: result.filePath };
});

ipcMain.handle('generate-labels-pdf', async (event, attendees) => {
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

  await pdfGenerator.generateLabelsPDF(attendees, result.filePath);
  return { success: true, path: result.filePath };
});

// PDF Preview (opens in default PDF viewer)
ipcMain.handle('preview-tickets-pdf', async (event, tickets) => {
  const settings = database.getAllSettings();
  const pdfGenerator = new PDFGenerator(settings);

  // Generate to temp file
  const tempPath = path.join(os.tmpdir(), `tickets-preview-${Date.now()}.pdf`);
  await pdfGenerator.generateTicketsPDF(tickets, tempPath);

  // Open with default PDF viewer
  await shell.openPath(tempPath);

  return { success: true, path: tempPath };
});

ipcMain.handle('preview-labels-pdf', async (event, attendees) => {
  const settings = database.getAllSettings();
  const pdfGenerator = new PDFGenerator(settings);

  // Generate to temp file
  const tempPath = path.join(os.tmpdir(), `labels-preview-${Date.now()}.pdf`);
  await pdfGenerator.generateLabelsPDF(attendees, tempPath);

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
