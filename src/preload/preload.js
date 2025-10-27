const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Settings
  getSettings: () => ipcRenderer.invoke('get-settings'),
  saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),

  // Tickets
  createAttendee: (data) => ipcRenderer.invoke('create-attendee', data),
  listTickets: () => ipcRenderer.invoke('list-tickets'),
  getTicket: (ticketNumber) => ipcRenderer.invoke('get-ticket', ticketNumber),
  updateTicket: (ticketNumber, fields) => ipcRenderer.invoke('update-ticket', ticketNumber, fields),
  deleteTickets: (ticketNumbers) => ipcRenderer.invoke('delete-tickets', ticketNumbers),
  markPrinted: (ticketNumbers, printed) => ipcRenderer.invoke('mark-printed', ticketNumbers, printed),
  checkIn: (identifier) => ipcRenderer.invoke('check-in', identifier),
  getStats: () => ipcRenderer.invoke('get-stats'),
  getOrderSummary: () => ipcRenderer.invoke('get-order-summary'),
  getCheckedInTickets: () => ipcRenderer.invoke('get-checked-in-tickets'),

  // PDF Generation
  generateTicketsPDF: (tickets) => ipcRenderer.invoke('generate-tickets-pdf', tickets),
  generateLabelsPDF: (attendees) => ipcRenderer.invoke('generate-labels-pdf', attendees),
  previewTicketsPDF: (tickets) => ipcRenderer.invoke('preview-tickets-pdf', tickets),
  previewLabelsPDF: (attendees) => ipcRenderer.invoke('preview-labels-pdf', attendees),

  // CSV Import/Export
  importCSV: () => ipcRenderer.invoke('import-csv'),
  exportTicketsCSV: () => ipcRenderer.invoke('export-tickets-csv'),
  exportCheckInsCSV: () => ipcRenderer.invoke('export-checkins-csv'),
  exportOrderSummaryCSV: () => ipcRenderer.invoke('export-order-summary-csv'),

  // Utilities
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  showMessage: (options) => ipcRenderer.invoke('show-message', options)
});
