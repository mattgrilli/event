// Application State
let currentSettings = {};
let allTickets = [];
let selectedTickets = new Set();

// Initialize App
document.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();
  await loadTickets();
  initializeEventListeners();
  updateUI();
});

// Load Settings
async function loadSettings() {
  currentSettings = await window.electronAPI.getSettings();
  applySettings();
}

function applySettings() {
  const mode = currentSettings.mode || 'ticketing';

  // Update mode badge
  document.getElementById('modeBadge').textContent =
    mode === 'ticketing' ? 'Ticketing Mode' : 'Sales Mode';

  // Update accent color
  const accentColor = currentSettings.ticket_color || '#ff7a00';
  document.documentElement.style.setProperty('--accent', accentColor);

  // Show/hide check-in tab
  const checkinTab = document.getElementById('checkinTab');
  checkinTab.style.display = mode === 'ticketing' ? 'block' : 'none';

  // Show/hide teacher field
  const teacherGroup = document.getElementById('teacherGroup');
  teacherGroup.classList.toggle('hidden', mode !== 'sales');

  // Show/hide export order summary button
  const exportOrderBtn = document.getElementById('exportOrderBtn');
  exportOrderBtn.classList.toggle('hidden', mode !== 'sales');

  // Update table headers
  updateTableHeaders();

  // Update section titles
  document.getElementById('ticketsHeader').textContent =
    mode === 'ticketing' ? 'Tickets' : 'Orders';
  document.getElementById('labelsHeader').textContent = 'Participants';

  // Update settings form
  document.getElementById('modeTicketing').checked = mode === 'ticketing';
  document.getElementById('modeSales').checked = mode === 'sales';
  document.getElementById('orgName').value = currentSettings.organization_name || '';
  document.getElementById('eventName').value = currentSettings.event_name || '';
  document.getElementById('eventCode').value = currentSettings.event_code || 'EVT';
  document.getElementById('accentColor').value = accentColor;
  document.getElementById('accentColorText').value = accentColor;
  document.getElementById('qrEnabled').checked = currentSettings.qr_enabled === 'true';

  // Label settings
  document.getElementById('showBorders').checked = currentSettings.label_show_borders === 'true';
  document.getElementById('vGap').value = currentSettings.label_vertical_gap || '0.0';
  document.getElementById('hGap').value = currentSettings.label_horizontal_gap || '0.0';
  document.getElementById('topMargin').value = currentSettings.label_top_margin || '0.5';
  document.getElementById('leftMargin').value = currentSettings.label_left_margin || '0.1875';
}

function updateTableHeaders() {
  const mode = currentSettings.mode || 'ticketing';
  const isTicketing = mode === 'ticketing';

  const headers = ['Ticket #', 'Code', 'First', 'Last', 'Room'];
  if (mode === 'sales') {
    headers.push('Teacher');
  }
  if (isTicketing) {
    headers.push('Printed', 'Checked In');
  } else {
    headers.push('Printed');
  }

  document.getElementById('tableHeader').innerHTML =
    headers.map(h => `<th>${h}</th>`).join('');

  // Labels table
  const labelsHeaders = ['Ticket #', 'First', 'Last', 'Room'];
  if (mode === 'sales') {
    labelsHeaders.push('Teacher');
  }

  document.getElementById('labelsTableHeader').innerHTML =
    labelsHeaders.map(h => `<th>${h}</th>`).join('');
}

// Load Tickets
async function loadTickets() {
  allTickets = await window.electronAPI.listTickets();
  renderTicketsTable();
  renderLabelsTable();
  await updateStats();
}

function renderTicketsTable() {
  const tbody = document.getElementById('ticketsBody');
  const mode = currentSettings.mode || 'ticketing';
  const isTicketing = mode === 'ticketing';

  tbody.innerHTML = '';

  const filterText = document.getElementById('filterInput').value.toLowerCase();
  const filtered = allTickets.filter(ticket => {
    const searchText = `${ticket.first_name} ${ticket.last_name} ${ticket.ticket_code} ${ticket.classroom || ''} ${ticket.teacher || ''}`.toLowerCase();
    return searchText.includes(filterText);
  });

  filtered.forEach(ticket => {
    const row = document.createElement('tr');
    row.dataset.ticketNumber = ticket.ticket_number;
    row.className = selectedTickets.has(ticket.ticket_number) ? 'selected' : '';

    const cells = [
      ticket.ticket_number,
      ticket.ticket_code,
      ticket.first_name,
      ticket.last_name,
      ticket.classroom || ''
    ];

    if (mode === 'sales') {
      cells.push(ticket.teacher || '');
    }

    cells.push(ticket.printed ? 'Yes' : 'No');

    if (isTicketing) {
      cells.push(ticket.checked_in ? 'Yes' : 'No');
    }

    row.innerHTML = cells.map(c => `<td>${c}</td>`).join('');
    row.addEventListener('click', (e) => handleRowClick(e, ticket.ticket_number));
    tbody.appendChild(row);
  });
}

function renderLabelsTable() {
  const tbody = document.getElementById('labelsBody');
  const mode = currentSettings.mode || 'ticketing';

  tbody.innerHTML = '';

  const filterText = document.getElementById('labelsFilterInput').value.toLowerCase();
  const filtered = allTickets.filter(ticket => {
    const searchText = `${ticket.first_name} ${ticket.last_name} ${ticket.classroom || ''} ${ticket.teacher || ''}`.toLowerCase();
    return searchText.includes(filterText);
  });

  filtered.forEach(ticket => {
    const row = document.createElement('tr');
    row.dataset.ticketNumber = ticket.ticket_number;
    row.className = selectedTickets.has(ticket.ticket_number) ? 'selected' : '';

    const cells = [
      ticket.ticket_number,
      ticket.first_name,
      ticket.last_name,
      ticket.classroom || ''
    ];

    if (mode === 'sales') {
      cells.push(ticket.teacher || '');
    }

    row.innerHTML = cells.map(c => `<td>${c}</td>`).join('');
    row.addEventListener('click', (e) => handleRowClick(e, ticket.ticket_number));
    tbody.appendChild(row);
  });
}

function handleRowClick(e, ticketNumber) {
  if (e.ctrlKey || e.metaKey) {
    // Toggle selection
    if (selectedTickets.has(ticketNumber)) {
      selectedTickets.delete(ticketNumber);
    } else {
      selectedTickets.add(ticketNumber);
    }
  } else if (e.shiftKey && selectedTickets.size > 0) {
    // Range selection (simplified)
    const allRows = Array.from(document.querySelectorAll('#ticketsBody tr, #labelsBody tr'));
    const indices = allRows.map(r => parseInt(r.dataset.ticketNumber));
    const lastSelected = Math.max(...selectedTickets);
    const start = Math.min(lastSelected, ticketNumber);
    const end = Math.max(lastSelected, ticketNumber);

    indices.forEach(num => {
      if (num >= start && num <= end) {
        selectedTickets.add(num);
      }
    });
  } else {
    // Single selection
    selectedTickets.clear();
    selectedTickets.add(ticketNumber);
  }

  renderTicketsTable();
  renderLabelsTable();
}

async function updateStats() {
  const stats = await window.electronAPI.getStats();
  const mode = currentSettings.mode || 'ticketing';
  const label = mode === 'ticketing' ? 'Tickets' : 'Orders';

  let statsText = `Total ${label}: ${stats.total} | Printed: ${stats.printed} | Unprinted: ${stats.unprinted}`;
  if (mode === 'ticketing') {
    statsText += ` | Checked-In: ${stats.checkedIn}`;
  }

  document.getElementById('statsBar').textContent = statsText;
}

// Event Listeners
function initializeEventListeners() {
  // Tabs
  document.querySelectorAll('.tab-button').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // Register Form
  document.getElementById('registerForm').addEventListener('submit', handleRegister);

  // Import/Export
  document.getElementById('importBtn').addEventListener('click', handleImport);
  document.getElementById('exportBtn').addEventListener('click', handleExport);
  document.getElementById('exportOrderBtn').addEventListener('click', handleExportOrderSummary);

  // Ticket Actions
  document.getElementById('editBtn').addEventListener('click', handleEdit);
  document.getElementById('deleteBtn').addEventListener('click', handleDelete);
  document.getElementById('printSelectedBtn').addEventListener('click', () => handlePrintTickets(false));
  document.getElementById('printAllBtn').addEventListener('click', () => handlePrintTickets(true));

  // Label Actions
  document.getElementById('printLabelsSelectedBtn').addEventListener('click', () => handlePrintLabels(false));
  document.getElementById('printLabelsAllBtn').addEventListener('click', () => handlePrintLabels(true));

  // Check-In
  document.getElementById('checkinInput').addEventListener('keypress', handleCheckInKeyPress);
  document.getElementById('exportCheckinsBtn').addEventListener('click', handleExportCheckIns);

  // Settings
  document.getElementById('settingsForm').addEventListener('submit', handleSaveSettings);
  document.getElementById('accentColor').addEventListener('input', (e) => {
    document.getElementById('accentColorText').value = e.target.value;
  });
  document.getElementById('accentColorText').addEventListener('input', (e) => {
    if (/^#[0-9A-Fa-f]{6}$/.test(e.target.value)) {
      document.getElementById('accentColor').value = e.target.value;
    }
  });

  // Label Presets
  document.getElementById('presetDefault').addEventListener('click', () => {
    document.getElementById('vGap').value = '0.0';
    document.getElementById('hGap').value = '0.0';
    document.getElementById('topMargin').value = '0.5';
    document.getElementById('leftMargin').value = '0.1875';
  });
  document.getElementById('presetTight').addEventListener('click', () => {
    document.getElementById('vGap').value = '-0.05';
    document.getElementById('hGap').value = '-0.05';
    document.getElementById('topMargin').value = '0.45';
    document.getElementById('leftMargin').value = '0.15';
  });
  document.getElementById('presetSpaced').addEventListener('click', () => {
    document.getElementById('vGap').value = '0.05';
    document.getElementById('hGap').value = '0.05';
    document.getElementById('topMargin').value = '0.55';
    document.getElementById('leftMargin').value = '0.22';
  });

  // Filters
  document.getElementById('filterInput').addEventListener('input', renderTicketsTable);
  document.getElementById('labelsFilterInput').addEventListener('input', renderLabelsTable);

  // About
  document.getElementById('emailLink').addEventListener('click', (e) => {
    e.preventDefault();
    window.electronAPI.openExternal('mailto:him@mattgrilli.com');
  });
}

function switchTab(tabName) {
  document.querySelectorAll('.tab-button').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });

  document.querySelectorAll('.tab-pane').forEach(pane => {
    pane.classList.toggle('active', pane.id === tabName);
  });

  // Focus check-in input when switching to check-in tab
  if (tabName === 'checkin') {
    setTimeout(() => {
      document.getElementById('checkinInput').focus();
    }, 100);
  }
}

function updateUI() {
  applySettings();
  renderTicketsTable();
  renderLabelsTable();
}

// Handlers
async function handleRegister(e) {
  e.preventDefault();

  const firstName = document.getElementById('firstName').value.trim();
  const lastName = document.getElementById('lastName').value.trim();
  const quantity = parseInt(document.getElementById('quantity').value, 10);
  const classroom = document.getElementById('classroom').value.trim();
  const teacher = document.getElementById('teacher').value.trim();

  if (!firstName && !lastName) {
    await window.electronAPI.showMessage({
      type: 'error',
      title: 'Error',
      message: 'Please enter at least one name.'
    });
    return;
  }

  const customFields = { classroom, teacher };

  const result = await window.electronAPI.createAttendee({
    firstName,
    lastName,
    quantity,
    customFields
  });

  await window.electronAPI.showMessage({
    type: 'info',
    title: 'Success',
    message: `Created ${quantity} ticket(s) for ${firstName} ${lastName}\nTicket codes: ${result.ticketCodes.join(', ')}`
  });

  // Reset form
  document.getElementById('registerForm').reset();
  document.getElementById('quantity').value = '1';

  await loadTickets();
}

async function handleImport() {
  const result = await window.electronAPI.importCSV();

  if (result.canceled) return;

  if (result.success) {
    let message = `Import complete!\n\nImported: ${result.imported}`;
    if (result.skipped > 0) {
      message += `\nSkipped: ${result.skipped}`;
    }
    if (result.errors.length > 0) {
      message += `\n\nErrors:\n${result.errors.join('\n')}`;
    }

    await window.electronAPI.showMessage({
      type: 'info',
      title: 'Import Complete',
      message
    });

    await loadTickets();
  }
}

async function handleExport() {
  const result = await window.electronAPI.exportTicketsCSV();

  if (!result.canceled && result.success) {
    await window.electronAPI.showMessage({
      type: 'info',
      title: 'Export Complete',
      message: `Tickets exported successfully to:\n${result.path}`
    });
  }
}

async function handleExportOrderSummary() {
  const result = await window.electronAPI.exportOrderSummaryCSV();

  if (!result.canceled && result.success) {
    await window.electronAPI.showMessage({
      type: 'info',
      title: 'Export Complete',
      message: `Order summary exported successfully to:\n${result.path}`
    });
  }
}

async function handleEdit() {
  if (selectedTickets.size !== 1) {
    await window.electronAPI.showMessage({
      type: 'warning',
      title: 'Select One Ticket',
      message: 'Please select exactly one ticket to edit.'
    });
    return;
  }

  const ticketNumber = [...selectedTickets][0];
  const ticket = await window.electronAPI.getTicket(ticketNumber);

  // Create a simple prompt dialog (in a real app, you'd create a modal)
  const newFirstName = prompt('First Name:', ticket.first_name) || ticket.first_name;
  const newLastName = prompt('Last Name:', ticket.last_name) || ticket.last_name;
  const newClassroom = prompt('Classroom:', ticket.classroom || '') || null;
  const newTeacher = currentSettings.mode === 'sales' ?
    (prompt('Teacher:', ticket.teacher || '') || null) : ticket.teacher;

  await window.electronAPI.updateTicket(ticketNumber, {
    first_name: newFirstName,
    last_name: newLastName,
    classroom: newClassroom,
    teacher: newTeacher
  });

  await loadTickets();
}

async function handleDelete() {
  if (selectedTickets.size === 0) {
    await window.electronAPI.showMessage({
      type: 'warning',
      title: 'No Selection',
      message: 'Please select tickets to delete.'
    });
    return;
  }

  const response = await window.electronAPI.showMessage({
    type: 'question',
    title: 'Confirm Delete',
    message: `Delete ${selectedTickets.size} ticket(s)?`,
    buttons: ['Cancel', 'Delete'],
    defaultId: 0,
    cancelId: 0
  });

  if (response.response === 1) {
    await window.electronAPI.deleteTickets([...selectedTickets]);
    selectedTickets.clear();
    await loadTickets();
  }
}

async function handlePrintTickets(printAll) {
  let ticketsToPrint;

  if (printAll) {
    ticketsToPrint = allTickets.filter(t => !t.printed);
    if (ticketsToPrint.length === 0) {
      await window.electronAPI.showMessage({
        type: 'info',
        title: 'No Unprinted Tickets',
        message: 'All tickets have already been printed.'
      });
      return;
    }
  } else {
    if (selectedTickets.size === 0) {
      await window.electronAPI.showMessage({
        type: 'warning',
        title: 'No Selection',
        message: 'Please select tickets to print.'
      });
      return;
    }
    ticketsToPrint = allTickets.filter(t => selectedTickets.has(t.ticket_number));
  }

  const result = await window.electronAPI.generateTicketsPDF(ticketsToPrint);

  if (!result.canceled && result.success) {
    await window.electronAPI.showMessage({
      type: 'info',
      title: 'PDF Created',
      message: `Tickets PDF saved successfully!\n\nPrinted ${ticketsToPrint.length} ticket(s).`
    });

    await loadTickets();
  }
}

async function handlePrintLabels(printAll) {
  let attendeesToPrint;

  if (printAll) {
    attendeesToPrint = allTickets;
  } else {
    if (selectedTickets.size === 0) {
      await window.electronAPI.showMessage({
        type: 'warning',
        title: 'No Selection',
        message: 'Please select participants for labels.'
      });
      return;
    }
    attendeesToPrint = allTickets.filter(t => selectedTickets.has(t.ticket_number));
  }

  const result = await window.electronAPI.generateLabelsPDF(attendeesToPrint);

  if (!result.canceled && result.success) {
    // Deduplicate count
    const uniqueCount = new Set(
      attendeesToPrint.map(a => `${a.first_name}|${a.last_name}|${a.classroom || ''}`)
    ).size;

    await window.electronAPI.showMessage({
      type: 'info',
      title: 'Labels PDF Created',
      message: `Labels PDF saved successfully!\n\nCreated ${uniqueCount} unique label(s).`
    });
  }
}

async function handleCheckInKeyPress(e) {
  if (e.key === 'Enter') {
    const input = document.getElementById('checkinInput');
    const identifier = input.value.trim();

    if (!identifier) return;

    const result = await window.electronAPI.checkIn(identifier);

    const log = document.getElementById('checkinLog');
    const entry = document.createElement('div');
    entry.className = 'checkin-log-entry';

    if (result.status === 'checked_in') {
      entry.classList.add('success');
      entry.textContent = `✓ Ticket ${identifier} checked in at ${new Date(result.timestamp * 1000).toLocaleTimeString()}`;
    } else if (result.status === 'already') {
      entry.classList.add('warning');
      entry.textContent = `• Ticket ${identifier} already checked in at ${new Date(result.timestamp * 1000).toLocaleTimeString()}`;
    } else {
      entry.classList.add('error');
      entry.textContent = `✗ Ticket ${identifier} not found`;
    }

    log.insertBefore(entry, log.firstChild);
    input.value = '';

    await loadTickets();
  }
}

async function handleExportCheckIns() {
  const result = await window.electronAPI.exportCheckInsCSV();

  if (!result.canceled && result.success) {
    await window.electronAPI.showMessage({
      type: 'info',
      title: 'Export Complete',
      message: `Check-ins exported successfully to:\n${result.path}`
    });
  }
}

async function handleSaveSettings(e) {
  e.preventDefault();

  const settings = {
    mode: document.querySelector('input[name="mode"]:checked').value,
    organization_name: document.getElementById('orgName').value,
    event_name: document.getElementById('eventName').value,
    event_code: document.getElementById('eventCode').value.toUpperCase(),
    ticket_color: document.getElementById('accentColorText').value,
    qr_enabled: document.getElementById('qrEnabled').checked ? 'true' : 'false',
    label_show_borders: document.getElementById('showBorders').checked ? 'true' : 'false',
    label_vertical_gap: document.getElementById('vGap').value,
    label_horizontal_gap: document.getElementById('hGap').value,
    label_top_margin: document.getElementById('topMargin').value,
    label_left_margin: document.getElementById('leftMargin').value
  };

  await window.electronAPI.saveSettings(settings);

  await window.electronAPI.showMessage({
    type: 'info',
    title: 'Settings Saved',
    message: 'Settings have been saved successfully!'
  });

  await loadSettings();
  await loadTickets();
}
