const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Settings
  getSettings: () => ipcRenderer.invoke('get-settings'),
  saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),

  // Tickets
  createAttendee: (data) => ipcRenderer.invoke('create-attendee', data),
  listTickets: (eventCode = null) => ipcRenderer.invoke('list-tickets', eventCode),
  getEventCodes: () => ipcRenderer.invoke('get-event-codes'),
  getTicket: (ticketNumber) => ipcRenderer.invoke('get-ticket', ticketNumber),
  updateTicket: (ticketNumber, fields) => ipcRenderer.invoke('update-ticket', ticketNumber, fields),
  deleteTickets: (ticketNumbers) => ipcRenderer.invoke('delete-tickets', ticketNumbers),
  markPrinted: (ticketNumbers, printed) => ipcRenderer.invoke('mark-printed', ticketNumbers, printed),
  checkIn: (identifier) => ipcRenderer.invoke('check-in', identifier),
  getStats: () => ipcRenderer.invoke('get-stats'),
  getOrderSummary: () => ipcRenderer.invoke('get-order-summary'),
  getCheckedInTickets: () => ipcRenderer.invoke('get-checked-in-tickets'),

  // PDF Generation
  generateTicketsPDF: (tickets, template) => ipcRenderer.invoke('generate-tickets-pdf', tickets, template),
  generateLabelsPDF: (attendees, template) => ipcRenderer.invoke('generate-labels-pdf', attendees, template),
  previewTicketsPDF: (tickets, template) => ipcRenderer.invoke('preview-tickets-pdf', tickets, template),
  previewLabelsPDF: (attendees, template) => ipcRenderer.invoke('preview-labels-pdf', attendees, template),
  printTicketsPDF: (tickets, template) => ipcRenderer.invoke('print-tickets-pdf', tickets, template),
  printLabelsPDF: (attendees, template) => ipcRenderer.invoke('print-labels-pdf', attendees, template),
  generateTestPattern: () => ipcRenderer.invoke('generate-test-pattern'),

  // CSV Import/Export
  importCSV: () => ipcRenderer.invoke('import-csv'),
  importCSVFile: (filePath) => ipcRenderer.invoke('import-csv-file', filePath),
  exportTicketsCSV: () => ipcRenderer.invoke('export-tickets-csv'),
  exportCheckInsCSV: () => ipcRenderer.invoke('export-checkins-csv'),
  exportOrderSummaryCSV: () => ipcRenderer.invoke('export-order-summary-csv'),
  exportLabelsMailMerge: (attendees) => ipcRenderer.invoke('export-labels-mailmerge', attendees),

  // Utilities
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  showMessage: (options) => ipcRenderer.invoke('show-message', options),

  // Templates
  saveTemplate: (name, type, elements) => ipcRenderer.invoke('save-template', name, type, elements),
  getTemplate: (templateId) => ipcRenderer.invoke('get-template', templateId),
  getTemplatesByType: (type) => ipcRenderer.invoke('get-templates-by-type', type),
  getTemplateByName: (name, type) => ipcRenderer.invoke('get-template-by-name', name, type),
  deleteTemplate: (templateId) => ipcRenderer.invoke('delete-template', templateId),

  // Event Management
  ensureEvent: (eventCode, eventName) => ipcRenderer.invoke('ensure-event', eventCode, eventName),
  isEventLocked: (eventCode) => ipcRenderer.invoke('is-event-locked', eventCode),
  lockEvent: (eventCode) => ipcRenderer.invoke('lock-event', eventCode),
  unlockEvent: (eventCode) => ipcRenderer.invoke('unlock-event', eventCode),

  // Manual Update Checking
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  getUpdateInfo: () => ipcRenderer.invoke('get-update-info'),
  checkForUpdates: () => ipcRenderer.invoke('check-for-updates'),
  onUpdateAvailable: (callback) => ipcRenderer.on('update-available', (event, info) => callback(info))
});
