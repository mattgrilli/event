// Application State
let currentSettings = {};
let allTickets = [];
let selectedTickets = new Set();
let sortColumn = 'ticket_number';
let sortDirection = 'desc'; // Start with newest first
let selectedEventCode = ''; // Empty string means "All Events"
let originalSettingsState = null; // Track original settings for unsaved changes detection

// Available custom fields
const CUSTOM_FIELDS = [
  { id: 'classroom', label: 'Classroom/Room', type: 'text' },
  { id: 'teacher', label: 'Teacher', type: 'text' },
  { id: 'grade', label: 'Grade', type: 'text' },
  { id: 'address', label: 'Address', type: 'text' },
  { id: 'email', label: 'Email', type: 'email' },
  { id: 'phone', label: 'Phone', type: 'tel' },
  { id: 'notes', label: 'Notes', type: 'textarea' }
];

let enabledFields = [];
let labelFields = [];

// Initialize App
document.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();
  await loadEventCodes();
  await loadTickets();
  await loadTemplateLists();
  initializeEventListeners();
  initializeUpdateChecking();
  updateUI();
});

// Theme Management
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);

  // Update theme toggle buttons
  document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.theme === theme);
  });
}

function updateAccentColor(color) {
  document.documentElement.style.setProperty('--accent', color);

  // Calculate RGB values for accent color variations
  const hex = color.replace('#', '');
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  document.documentElement.style.setProperty('--accent-rgb', `${r}, ${g}, ${b}`);
}

// Load Settings
async function loadSettings() {
  currentSettings = await window.electronAPI.getSettings();

  // Ensure current event exists in events table
  const eventCode = currentSettings.event_code || 'EVT';
  const eventName = currentSettings.event_name || 'Event';
  await window.electronAPI.ensureEvent(eventCode, eventName);

  applySettings();
  await updateEventBadge();
}

function applySettings() {
  const mode = currentSettings.mode || 'ticketing';

  // Load enabled and label fields
  enabledFields = JSON.parse(currentSettings.enabled_fields || '["classroom"]');
  labelFields = JSON.parse(currentSettings.label_fields || '["classroom"]');

  // Update mode badge
  document.getElementById('modeBadge').textContent =
    mode === 'ticketing' ? 'Ticketing Mode' : 'Sales Mode';

  // Apply theme
  const theme = currentSettings.theme || 'light';
  applyTheme(theme);

  // Update accent color
  const accentColor = currentSettings.ticket_color || '#ff7a00';
  updateAccentColor(accentColor);

  // Show/hide check-in tab
  const checkinTab = document.getElementById('checkinTab');
  checkinTab.style.display = mode === 'ticketing' ? 'block' : 'none';

  // Show/hide export order summary button
  const exportOrderBtn = document.getElementById('exportOrderBtn');
  exportOrderBtn.classList.toggle('hidden', mode !== 'sales');

  // Build custom forms
  buildCustomFieldsForms();

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
  document.getElementById('eventEmoji').value = currentSettings.event_emoji || '';

  // Custom fields checkboxes
  CUSTOM_FIELDS.forEach(field => {
    const fieldCheckbox = document.getElementById(`field${field.id.charAt(0).toUpperCase() + field.id.slice(1)}`);
    const labelCheckbox = document.getElementById(`label${field.id.charAt(0).toUpperCase() + field.id.slice(1)}`);
    if (fieldCheckbox) {
      fieldCheckbox.checked = enabledFields.includes(field.id);
    }
    if (labelCheckbox) {
      labelCheckbox.checked = labelFields.includes(field.id);
    }
  });

  // Label settings
  document.getElementById('showBorders').checked = currentSettings.label_show_borders === 'true';
  document.getElementById('vGap').value = currentSettings.label_vertical_gap || '0.0';
  document.getElementById('hGap').value = currentSettings.label_horizontal_gap || '0.0';
  document.getElementById('topMargin').value = currentSettings.label_top_margin || '0.5';
  document.getElementById('leftMargin').value = currentSettings.label_left_margin || '0.1875';
}

// Event Lock Management
async function updateEventBadge() {
  const eventCode = currentSettings.event_code || 'EVT';
  const isLocked = await window.electronAPI.isEventLocked(eventCode);

  const badge = document.getElementById('eventBadge');
  const codeDisplay = document.getElementById('eventCodeDisplay');
  const lockIcon = document.getElementById('eventLockIcon');

  codeDisplay.textContent = eventCode;

  if (isLocked) {
    lockIcon.textContent = '🔒';
    badge.classList.add('locked');
    badge.title = 'Event locked - Click to unlock';
  } else {
    lockIcon.textContent = '🔓';
    badge.classList.remove('locked');
    badge.title = 'Event unlocked - Accepting registrations';
  }

  // Update Settings UI
  updateSettingsLockUI(isLocked);
}

function updateSettingsLockUI(isLocked) {
  const icon = document.getElementById('lockStatusIcon');
  const text = document.getElementById('lockStatusText');
  const btn = document.getElementById('toggleLockBtn');

  if (!icon || !text || !btn) return; // Elements not loaded yet

  if (isLocked) {
    icon.textContent = '🔒';
    text.textContent = 'Locked - Not accepting new registrations';
    btn.textContent = 'Unlock Event';
    btn.classList.remove('btn-secondary');
    btn.classList.add('btn-danger');
  } else {
    icon.textContent = '🔓';
    text.textContent = 'Unlocked - Accepting new registrations';
    btn.textContent = 'Lock Event';
    btn.classList.remove('btn-danger');
    btn.classList.add('btn-secondary');
  }
}

function buildCustomFieldsForms() {
  // Build registration form custom fields
  const regContainer = document.getElementById('customFieldsContainer');
  regContainer.innerHTML = '';

  enabledFields.forEach(fieldId => {
    const field = CUSTOM_FIELDS.find(f => f.id === fieldId);
    if (!field) return;

    const formGroup = document.createElement('div');
    formGroup.className = 'form-group';

    const label = document.createElement('label');
    label.textContent = field.label;
    label.setAttribute('for', fieldId);

    let input;
    if (field.type === 'textarea') {
      input = document.createElement('textarea');
      input.rows = 2;
    } else {
      input = document.createElement('input');
      input.type = field.type;
    }
    input.id = fieldId;

    formGroup.appendChild(label);
    formGroup.appendChild(input);
    regContainer.appendChild(formGroup);
  });

  // Build edit modal custom fields
  const editContainer = document.getElementById('editCustomFieldsContainer');
  editContainer.innerHTML = '';

  enabledFields.forEach(fieldId => {
    const field = CUSTOM_FIELDS.find(f => f.id === fieldId);
    if (!field) return;

    const formGroup = document.createElement('div');
    formGroup.className = 'form-group';

    const label = document.createElement('label');
    label.textContent = field.label;
    label.setAttribute('for', `edit${fieldId.charAt(0).toUpperCase() + fieldId.slice(1)}`);

    let input;
    if (field.type === 'textarea') {
      input = document.createElement('textarea');
      input.rows = 2;
    } else {
      input = document.createElement('input');
      input.type = field.type;
    }
    input.id = `edit${fieldId.charAt(0).toUpperCase() + fieldId.slice(1)}`;

    formGroup.appendChild(label);
    formGroup.appendChild(input);
    editContainer.appendChild(formGroup);
  });
}

function updateTableHeaders() {
  const mode = currentSettings.mode || 'ticketing';
  const isTicketing = mode === 'ticketing';

  // Build headers with sort attributes
  const headers = [
    { label: '<input type="checkbox" id="selectAllTickets">', sort: null, class: 'checkbox-col' },
    { label: 'Ticket #', sort: 'ticket_number' },
    { label: 'Code', sort: 'ticket_code' },
    { label: 'First', sort: 'first_name' },
    { label: 'Last', sort: 'last_name' },
    { label: 'Room', sort: 'classroom' }
  ];

  if (mode === 'sales') {
    headers.push({ label: 'Teacher', sort: 'teacher' });
    headers.push({ label: 'Qty', sort: null });  // Quantity column for sales mode
  }

  headers.push({ label: 'Printed', sort: 'printed' });

  if (isTicketing) {
    headers.push({ label: 'Checked In', sort: 'checked_in' });
  }

  document.getElementById('tableHeader').innerHTML = headers.map(h => {
    if (h.sort) {
      const sortClass = sortColumn === h.sort ? sortDirection : '';
      return `<th class="sortable ${sortClass}" data-sort="${h.sort}">${h.label} <span class="sort-arrow">↕</span></th>`;
    } else {
      return `<th class="${h.class || ''}">${h.label}</th>`;
    }
  }).join('');

  // Labels table
  const labelsHeaders = [
    { label: '<input type="checkbox" id="selectAllLabels">', class: 'checkbox-col' },
    { label: 'First' },
    { label: 'Last' },
    { label: 'Room' }
  ];
  if (mode === 'sales') {
    labelsHeaders.push({ label: 'Teacher' });
    labelsHeaders.push({ label: 'Qty' });
  }

  document.getElementById('labelsTableHeader').innerHTML = labelsHeaders.map(h => {
    return `<th class="${h.class || ''}">${h.label}</th>`;
  }).join('');
}

// Load Event Codes
async function loadEventCodes() {
  const eventCodes = await window.electronAPI.getEventCodes();

  // Populate both event filter dropdowns
  const eventFilter = document.getElementById('eventFilter');
  const labelsEventFilter = document.getElementById('labelsEventFilter');

  [eventFilter, labelsEventFilter].forEach(select => {
    select.innerHTML = '<option value="">All Events</option>';
    eventCodes.forEach(code => {
      const option = document.createElement('option');
      option.value = code;
      option.textContent = code;
      select.appendChild(option);
    });
  });
}

// Load Tickets
async function loadTickets() {
  const eventCode = selectedEventCode || null;
  allTickets = await window.electronAPI.listTickets(eventCode);
  renderTicketsTable();
  renderLabelsTable();
  await updateStats();
}

// Load Template Lists
async function loadTemplateLists() {
  // Load ticket templates
  const ticketTemplates = await window.electronAPI.getTemplatesByType('ticket');
  const ticketSelect = document.getElementById('ticketTemplateSelect');
  ticketSelect.innerHTML = '<option value="">Default Layout</option>';
  ticketTemplates.forEach(template => {
    const option = document.createElement('option');
    option.value = template.template_id;
    option.textContent = template.name;
    ticketSelect.appendChild(option);
  });

  // Load label templates
  const labelTemplates = await window.electronAPI.getTemplatesByType('label');
  const labelSelect = document.getElementById('labelTemplateSelect');
  labelSelect.innerHTML = '<option value="">Default Layout</option>';
  labelTemplates.forEach(template => {
    const option = document.createElement('option');
    option.value = template.template_id;
    option.textContent = template.name;
    labelSelect.appendChild(option);
  });
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

  // Sort tickets
  const sorted = filtered.sort((a, b) => {
    let aVal = a[sortColumn];
    let bVal = b[sortColumn];

    // Handle null values
    if (aVal === null || aVal === undefined) aVal = '';
    if (bVal === null || bVal === undefined) bVal = '';

    // Compare
    if (typeof aVal === 'string') {
      aVal = aVal.toLowerCase();
      bVal = bVal.toLowerCase();
    }

    if (sortDirection === 'asc') {
      return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
    } else {
      return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
    }
  });

  sorted.forEach(ticket => {
    const row = document.createElement('tr');
    row.dataset.ticketNumber = ticket.ticket_number;
    row.className = selectedTickets.has(ticket.ticket_number) ? 'selected' : '';

    // Add checkbox cell
    const checkboxCell = document.createElement('td');
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = selectedTickets.has(ticket.ticket_number);
    checkbox.addEventListener('change', (e) => {
      e.stopPropagation();
      handleCheckboxChange(ticket.ticket_number, e.target.checked);
    });
    checkboxCell.appendChild(checkbox);
    row.appendChild(checkboxCell);

    // Add data cells
    const cells = [
      ticket.ticket_number,
      ticket.ticket_code,
      ticket.first_name,
      ticket.last_name,
      ticket.classroom || ''
    ];

    if (mode === 'sales') {
      cells.push(ticket.teacher || '');

      // Calculate quantity (count of tickets for this student)
      const studentKey = `${ticket.first_name}|${ticket.last_name}|${ticket.classroom || ''}`;
      const studentTickets = allTickets.filter(t =>
        `${t.first_name}|${t.last_name}|${t.classroom || ''}` === studentKey
      );
      cells.push(studentTickets.length);
    }

    cells.push(ticket.printed ? 'Yes' : 'No');

    if (isTicketing) {
      cells.push(ticket.checked_in ? 'Yes' : 'No');
    }

    cells.forEach(c => {
      const td = document.createElement('td');
      td.textContent = c;
      row.appendChild(td);
    });

    // Handle row click (not on checkbox)
    row.addEventListener('click', (e) => {
      if (e.target.type !== 'checkbox') {
        handleRowClick(e, ticket.ticket_number);
      }
    });

    // Handle double-click to edit
    row.addEventListener('dblclick', (e) => {
      e.preventDefault();
      handleEditTicket(ticket.ticket_number);
    });

    // Handle right-click
    row.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      showContextMenu(e, ticket.ticket_number);
    });

    tbody.appendChild(row);
  });

  // Update select all checkbox
  updateSelectAllCheckbox();
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

    // Add checkbox cell
    const checkboxCell = document.createElement('td');
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = selectedTickets.has(ticket.ticket_number);
    checkbox.addEventListener('change', (e) => {
      e.stopPropagation();
      handleCheckboxChange(ticket.ticket_number, e.target.checked);
    });
    checkboxCell.appendChild(checkbox);
    row.appendChild(checkboxCell);

    // Add data cells (no ticket number for labels table)
    const cells = [
      ticket.first_name,
      ticket.last_name,
      ticket.classroom || ''
    ];

    if (mode === 'sales') {
      cells.push(ticket.teacher || '');

      // Calculate quantity (count of tickets for this student)
      const studentKey = `${ticket.first_name}|${ticket.last_name}|${ticket.classroom || ''}`;
      const studentTickets = allTickets.filter(t =>
        `${t.first_name}|${t.last_name}|${t.classroom || ''}` === studentKey
      );
      cells.push(studentTickets.length);
    }

    cells.forEach(c => {
      const td = document.createElement('td');
      td.textContent = c;
      row.appendChild(td);
    });

    // Handle row click (not on checkbox)
    row.addEventListener('click', (e) => {
      if (e.target.type !== 'checkbox') {
        handleRowClick(e, ticket.ticket_number);
      }
    });

    // Handle double-click to edit
    row.addEventListener('dblclick', (e) => {
      e.preventDefault();
      handleEditTicket(ticket.ticket_number);
    });

    // Handle right-click
    row.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      showContextMenu(e, ticket.ticket_number);
    });

    tbody.appendChild(row);
  });

  // Update select all checkbox for labels
  updateSelectAllLabelsCheckbox();
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

// New Helper Functions
function handleCheckboxChange(ticketNumber, checked) {
  if (checked) {
    selectedTickets.add(ticketNumber);
  } else {
    selectedTickets.delete(ticketNumber);
  }
  renderTicketsTable();
  renderLabelsTable();
}

function updateSelectAllCheckbox() {
  const selectAllCheckbox = document.getElementById('selectAllTickets');
  if (!selectAllCheckbox) return;

  const visibleTickets = Array.from(document.querySelectorAll('#ticketsBody tr')).map(
    row => parseInt(row.dataset.ticketNumber)
  );

  if (visibleTickets.length === 0) {
    selectAllCheckbox.checked = false;
    selectAllCheckbox.indeterminate = false;
  } else if (visibleTickets.every(num => selectedTickets.has(num))) {
    selectAllCheckbox.checked = true;
    selectAllCheckbox.indeterminate = false;
  } else if (visibleTickets.some(num => selectedTickets.has(num))) {
    selectAllCheckbox.checked = false;
    selectAllCheckbox.indeterminate = true;
  } else {
    selectAllCheckbox.checked = false;
    selectAllCheckbox.indeterminate = false;
  }
}

function updateSelectAllLabelsCheckbox() {
  const selectAllCheckbox = document.getElementById('selectAllLabels');
  if (!selectAllCheckbox) return;

  const visibleTickets = Array.from(document.querySelectorAll('#labelsBody tr')).map(
    row => parseInt(row.dataset.ticketNumber)
  );

  if (visibleTickets.length === 0) {
    selectAllCheckbox.checked = false;
    selectAllCheckbox.indeterminate = false;
  } else if (visibleTickets.every(num => selectedTickets.has(num))) {
    selectAllCheckbox.checked = true;
    selectAllCheckbox.indeterminate = false;
  } else if (visibleTickets.some(num => selectedTickets.has(num))) {
    selectAllCheckbox.checked = false;
    selectAllCheckbox.indeterminate = true;
  } else {
    selectAllCheckbox.checked = false;
    selectAllCheckbox.indeterminate = false;
  }
}

function handleSelectAll(checked) {
  const visibleTickets = Array.from(document.querySelectorAll('#ticketsBody tr')).map(
    row => parseInt(row.dataset.ticketNumber)
  );

  if (checked) {
    visibleTickets.forEach(num => selectedTickets.add(num));
  } else {
    visibleTickets.forEach(num => selectedTickets.delete(num));
  }

  renderTicketsTable();
  renderLabelsTable();
}

function handleSelectAllLabels(checked) {
  const visibleTickets = Array.from(document.querySelectorAll('#labelsBody tr')).map(
    row => parseInt(row.dataset.ticketNumber)
  );

  if (checked) {
    visibleTickets.forEach(num => selectedTickets.add(num));
  } else {
    visibleTickets.forEach(num => selectedTickets.delete(num));
  }

  renderTicketsTable();
  renderLabelsTable();
}

function handleSort(column) {
  if (sortColumn === column) {
    // Toggle direction
    sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
  } else {
    // New column, default to ascending
    sortColumn = column;
    sortDirection = 'asc';
  }

  renderTicketsTable();
}

function showContextMenu(e, ticketNumber) {
  // Ensure the ticket is selected
  if (!selectedTickets.has(ticketNumber)) {
    selectedTickets.clear();
    selectedTickets.add(ticketNumber);
    renderTicketsTable();
  }

  const contextMenu = document.getElementById('contextMenu');
  contextMenu.style.left = `${e.pageX}px`;
  contextMenu.style.top = `${e.pageY}px`;
  contextMenu.classList.remove('hidden');

  // Store the ticket number for context menu actions
  contextMenu.dataset.ticketNumber = ticketNumber;
}

function hideContextMenu() {
  document.getElementById('contextMenu').classList.add('hidden');
}

async function handleContextMarkPrinted() {
  await window.electronAPI.markPrinted([...selectedTickets], true);
  await loadTickets();
  hideContextMenu();
}

async function handleContextResetPrinted() {
  await window.electronAPI.markPrinted([...selectedTickets], false);
  await loadTickets();
  hideContextMenu();
}

// Modal Functions
let currentEditingTicketNumber = null;

function showEditModal(ticketNumber) {
  currentEditingTicketNumber = ticketNumber;
  const ticket = allTickets.find(t => t.ticket_number === ticketNumber);

  if (!ticket) return;

  // Populate form
  document.getElementById('editFirstName').value = ticket.first_name || '';
  document.getElementById('editLastName').value = ticket.last_name || '';

  // Populate all enabled custom fields dynamically
  enabledFields.forEach(fieldId => {
    const element = document.getElementById(`edit${fieldId.charAt(0).toUpperCase() + fieldId.slice(1)}`);
    if (element) {
      element.value = ticket[fieldId] || '';
    }
  });

  // Show modal
  document.getElementById('editModal').classList.remove('hidden');
  document.getElementById('editFirstName').focus();
}

function hideEditModal() {
  document.getElementById('editModal').classList.add('hidden');
  currentEditingTicketNumber = null;
}

async function saveEdit() {
  if (!currentEditingTicketNumber) return;

  const fields = {
    first_name: document.getElementById('editFirstName').value.trim(),
    last_name: document.getElementById('editLastName').value.trim()
  };

  // Collect all enabled custom fields dynamically
  enabledFields.forEach(fieldId => {
    const element = document.getElementById(`edit${fieldId.charAt(0).toUpperCase() + fieldId.slice(1)}`);
    if (element) {
      fields[fieldId] = element.value.trim() || null;
    }
  });

  await window.electronAPI.updateTicket(currentEditingTicketNumber, fields);
  await loadTickets();
  hideEditModal();
}

function handleEditTicket(ticketNumber) {
  showEditModal(ticketNumber);
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
  document.getElementById('previewSelectedBtn').addEventListener('click', () => handlePreviewTickets(false));
  document.getElementById('printSelectedBtn').addEventListener('click', () => handlePrintTickets(false));
  document.getElementById('previewAllBtn').addEventListener('click', () => handlePreviewTickets(true));
  document.getElementById('printAllBtn').addEventListener('click', () => handlePrintTickets(true));

  // Label Actions
  document.getElementById('previewLabelsSelectedBtn').addEventListener('click', () => handlePreviewLabels(false));
  document.getElementById('printLabelsSelectedBtn').addEventListener('click', () => handlePrintLabels(false));
  document.getElementById('previewLabelsAllBtn').addEventListener('click', () => handlePreviewLabels(true));
  document.getElementById('printLabelsAllBtn').addEventListener('click', () => handlePrintLabels(true));
  document.getElementById('editLabelBtn').addEventListener('click', handleEdit);

  // Check-In
  document.getElementById('checkinInput').addEventListener('keypress', handleCheckInKeyPress);
  document.getElementById('exportCheckinsBtn').addEventListener('click', handleExportCheckIns);

  // Settings
  document.getElementById('settingsForm').addEventListener('submit', handleSaveSettings);

  // Theme Toggle
  document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const theme = btn.dataset.theme;
      applyTheme(theme);
    });
  });

  // Accent Color - live preview
  document.getElementById('accentColor').addEventListener('input', (e) => {
    const color = e.target.value;
    document.getElementById('accentColorText').value = color;
    updateAccentColor(color);
  });
  document.getElementById('accentColorText').addEventListener('input', (e) => {
    const color = e.target.value;
    if (/^#[0-9A-Fa-f]{6}$/.test(color)) {
      document.getElementById('accentColor').value = color;
      updateAccentColor(color);
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

  // Event Filters (sync both dropdowns)
  document.getElementById('eventFilter').addEventListener('change', async (e) => {
    selectedEventCode = e.target.value;
    document.getElementById('labelsEventFilter').value = selectedEventCode;
    await loadTickets();
  });
  document.getElementById('labelsEventFilter').addEventListener('change', async (e) => {
    selectedEventCode = e.target.value;
    document.getElementById('eventFilter').value = selectedEventCode;
    await loadTickets();
  });

  // Event Lock Management
  document.getElementById('eventBadge').addEventListener('click', async () => {
    const eventCode = currentSettings.event_code || 'EVT';
    const isLocked = await window.electronAPI.isEventLocked(eventCode);

    if (isLocked) {
      const result = await window.electronAPI.showMessage({
        type: 'question',
        title: 'Unlock Event?',
        message: `Unlock "${eventCode}" to accept new registrations?`,
        buttons: ['Cancel', 'Unlock'],
        defaultId: 1
      });

      if (result.response === 1) {
        await window.electronAPI.unlockEvent(eventCode);
        await updateEventBadge();
      }
    }
  });

  document.getElementById('toggleLockBtn').addEventListener('click', async () => {
    const eventCode = currentSettings.event_code || 'EVT';
    const isLocked = await window.electronAPI.isEventLocked(eventCode);

    if (isLocked) {
      await window.electronAPI.unlockEvent(eventCode);
    } else {
      await window.electronAPI.lockEvent(eventCode);
    }

    await updateEventBadge();
  });

  // About
  document.getElementById('emailLink').addEventListener('click', (e) => {
    e.preventDefault();
    window.electronAPI.openExternal('mailto:him@mattgrilli.com');
  });

  // Table Enhancements - using event delegation for dynamically created elements
  document.addEventListener('click', (e) => {
    // Handle sortable headers
    if (e.target.closest('.sortable')) {
      const header = e.target.closest('.sortable');
      const column = header.dataset.sort;
      if (column) {
        handleSort(column);
      }
    }

    // Handle select all checkboxes (using delegation since they're dynamically created)
    if (e.target.id === 'selectAllTickets') {
      handleSelectAll(e.target.checked);
    }
    if (e.target.id === 'selectAllLabels') {
      handleSelectAllLabels(e.target.checked);
    }

    // Hide context menu on any click
    if (!e.target.closest('.context-menu')) {
      hideContextMenu();
    }

    // Hide modal on background click
    if (e.target.id === 'editModal') {
      hideEditModal();
    }
  });

  // Context Menu Actions
  document.getElementById('contextMarkPrinted').addEventListener('click', handleContextMarkPrinted);
  document.getElementById('contextResetPrinted').addEventListener('click', handleContextResetPrinted);
  document.getElementById('contextEdit').addEventListener('click', () => {
    hideContextMenu();
    handleEdit();
  });
  document.getElementById('contextDelete').addEventListener('click', () => {
    hideContextMenu();
    handleDelete();
  });

  // Hide context menu on scroll
  document.addEventListener('scroll', hideContextMenu, true);

  // Modal Actions
  document.getElementById('closeEditModal').addEventListener('click', hideEditModal);
  document.getElementById('cancelEdit').addEventListener('click', hideEditModal);
  document.getElementById('editForm').addEventListener('submit', (e) => {
    e.preventDefault();
    saveEdit();
  });

  // Escape key to close modal
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      hideEditModal();
      hideContextMenu();
    }
  });
}

async function switchTab(tabName) {
  // Check for unsaved settings changes when leaving settings tab
  const currentTab = document.querySelector('.tab-button.active')?.dataset.tab;
  if (currentTab === 'settings' && tabName !== 'settings') {
    const hasChanges = checkSettingsChanges();
    if (hasChanges) {
      const result = await window.electronAPI.showMessage({
        type: 'question',
        title: 'Unsaved Changes',
        message: 'You have unsaved changes in Settings. Do you want to save them?',
        buttons: ['Discard Changes', 'Cancel', 'Save'],
        defaultId: 2,
        cancelId: 1
      });

      if (result.response === 2) {
        // Save settings
        await handleSaveSettings(new Event('submit'));
        // Continue with tab switch
      } else if (result.response === 1) {
        // Cancel - don't switch tabs
        return;
      } else if (result.response === 0) {
        // Discard changes - reload original settings
        applySettings();
        originalSettingsState = null;
      }
    }
  }

  document.querySelectorAll('.tab-button').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });

  document.querySelectorAll('.tab-pane').forEach(pane => {
    pane.classList.toggle('active', pane.id === tabName);
  });

  // Capture original settings state when entering settings tab
  if (tabName === 'settings') {
    captureSettingsState();
  }

  // Focus check-in input when switching to check-in tab
  if (tabName === 'checkin') {
    setTimeout(() => {
      document.getElementById('checkinInput').focus();
    }, 100);
  }

  // Initialize designer when switching to design tab
  if (tabName === 'design' && window.DesignerModule && !window.designerInitialized) {
    setTimeout(() => {
      window.DesignerModule.initialize();
      window.designerInitialized = true;
    }, 100);
  }
}

function captureSettingsState() {
  // Capture current form values
  const activeThemeBtn = document.querySelector('.theme-toggle-btn.active');
  const state = {
    theme: activeThemeBtn?.dataset.theme || 'light',
    mode: document.querySelector('input[name="mode"]:checked')?.value,
    orgName: document.getElementById('orgName')?.value,
    eventName: document.getElementById('eventName')?.value,
    eventCode: document.getElementById('eventCode')?.value,
    accentColor: document.getElementById('accentColorText')?.value,
    qrEnabled: document.getElementById('qrEnabled')?.checked,
    eventEmoji: document.getElementById('eventEmoji')?.value,
    showBorders: document.getElementById('showBorders')?.checked,
    vGap: document.getElementById('vGap')?.value,
    hGap: document.getElementById('hGap')?.value,
    topMargin: document.getElementById('topMargin')?.value,
    leftMargin: document.getElementById('leftMargin')?.value,
    enabledFields: [],
    labelFields: []
  };

  // Capture custom field states
  CUSTOM_FIELDS.forEach(field => {
    const fieldCheckbox = document.getElementById(`field${field.id.charAt(0).toUpperCase() + field.id.slice(1)}`);
    const labelCheckbox = document.getElementById(`label${field.id.charAt(0).toUpperCase() + field.id.slice(1)}`);
    if (fieldCheckbox?.checked) state.enabledFields.push(field.id);
    if (labelCheckbox?.checked) state.labelFields.push(field.id);
  });

  originalSettingsState = state;
}

function checkSettingsChanges() {
  if (!originalSettingsState) return false;

  const activeThemeBtn = document.querySelector('.theme-toggle-btn.active');
  const currentState = {
    theme: activeThemeBtn?.dataset.theme || 'light',
    mode: document.querySelector('input[name="mode"]:checked')?.value,
    orgName: document.getElementById('orgName')?.value,
    eventName: document.getElementById('eventName')?.value,
    eventCode: document.getElementById('eventCode')?.value,
    accentColor: document.getElementById('accentColorText')?.value,
    qrEnabled: document.getElementById('qrEnabled')?.checked,
    eventEmoji: document.getElementById('eventEmoji')?.value,
    showBorders: document.getElementById('showBorders')?.checked,
    vGap: document.getElementById('vGap')?.value,
    hGap: document.getElementById('hGap')?.value,
    topMargin: document.getElementById('topMargin')?.value,
    leftMargin: document.getElementById('leftMargin')?.value,
    enabledFields: [],
    labelFields: []
  };

  // Capture current custom field states
  CUSTOM_FIELDS.forEach(field => {
    const fieldCheckbox = document.getElementById(`field${field.id.charAt(0).toUpperCase() + field.id.slice(1)}`);
    const labelCheckbox = document.getElementById(`label${field.id.charAt(0).toUpperCase() + field.id.slice(1)}`);
    if (fieldCheckbox?.checked) currentState.enabledFields.push(field.id);
    if (labelCheckbox?.checked) currentState.labelFields.push(field.id);
  });

  // Deep comparison
  return JSON.stringify(originalSettingsState) !== JSON.stringify(currentState);
}

function updateUI() {
  applySettings();
  renderTicketsTable();
  renderLabelsTable();
}

// Handlers
async function handleRegister(e) {
  e.preventDefault();

  // Check if event is locked
  const eventCode = currentSettings.event_code || 'EVT';
  const isLocked = await window.electronAPI.isEventLocked(eventCode);

  if (isLocked) {
    const result = await window.electronAPI.showMessage({
      type: 'warning',
      title: 'Event Locked',
      message: `"${eventCode}" is locked for new registrations.\n\nWhat would you like to do?`,
      buttons: ['Cancel', 'Unlock Event', 'Go to Settings'],
      defaultId: 2,
      cancelId: 0
    });

    if (result.response === 1) {
      // Unlock event
      await window.electronAPI.unlockEvent(eventCode);
      await updateEventBadge();
      // Let them continue with registration - re-submit form
      setTimeout(() => document.getElementById('registerForm').dispatchEvent(new Event('submit')), 100);
    } else if (result.response === 2) {
      // Go to Settings
      switchTab('settings');
      document.getElementById('eventCode').focus();
    }
    return;
  }

  const firstName = document.getElementById('firstName').value.trim();
  const lastName = document.getElementById('lastName').value.trim();
  const quantity = parseInt(document.getElementById('quantity').value, 10);

  if (!firstName && !lastName) {
    await window.electronAPI.showMessage({
      type: 'error',
      title: 'Error',
      message: 'Please enter at least one name.'
    });
    return;
  }

  // Collect all enabled custom fields dynamically
  const customFields = {};
  enabledFields.forEach(fieldId => {
    const element = document.getElementById(fieldId);
    if (element) {
      customFields[fieldId] = element.value.trim() || null;
    }
  });

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

  await loadEventCodes(); // Reload event codes in case new event code was created
  await loadTickets();
}

async function handleImport() {
  // Check if event is locked
  const eventCode = currentSettings.event_code || 'EVT';
  const isLocked = await window.electronAPI.isEventLocked(eventCode);

  if (isLocked) {
    const result = await window.electronAPI.showMessage({
      type: 'warning',
      title: 'Event Locked',
      message: `"${eventCode}" is locked for new registrations.\n\nUnlock to import to this event, or create a new event code first in Settings.`,
      buttons: ['Cancel', 'Unlock Event'],
      defaultId: 0,
      cancelId: 0
    });

    if (result.response === 1) {
      // Unlock event
      await window.electronAPI.unlockEvent(eventCode);
      await updateEventBadge();
      // Continue with import
    } else {
      return;
    }
  }

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

    await loadEventCodes(); // Reload event codes in case new event codes were imported
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
  showEditModal(ticketNumber);
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

  // Get selected template
  const templateSelect = document.getElementById('ticketTemplateSelect');
  const templateId = templateSelect.value ? parseInt(templateSelect.value) : null;
  let template = null;
  if (templateId) {
    template = await window.electronAPI.getTemplate(templateId);
  }

  const result = await window.electronAPI.generateTicketsPDF(ticketsToPrint, template);

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

  // Get selected template
  const templateSelect = document.getElementById('labelTemplateSelect');
  const templateId = templateSelect.value ? parseInt(templateSelect.value) : null;
  let template = null;
  if (templateId) {
    template = await window.electronAPI.getTemplate(templateId);
  }

  const result = await window.electronAPI.generateLabelsPDF(attendeesToPrint, template);

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

// Preview functions - generate temp PDFs and open with default viewer
async function handlePreviewTickets(printAll) {
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
        message: 'Please select tickets to preview.'
      });
      return;
    }
    ticketsToPrint = allTickets.filter(t => selectedTickets.has(t.ticket_number));
  }

  // Get selected template
  const templateSelect = document.getElementById('ticketTemplateSelect');
  const templateId = templateSelect.value ? parseInt(templateSelect.value) : null;
  let template = null;
  if (templateId) {
    template = await window.electronAPI.getTemplate(templateId);
  }

  await window.electronAPI.previewTicketsPDF(ticketsToPrint, template);
}

async function handlePreviewLabels(printAll) {
  let attendeesToPrint;

  if (printAll) {
    attendeesToPrint = allTickets;
  } else {
    if (selectedTickets.size === 0) {
      await window.electronAPI.showMessage({
        type: 'warning',
        title: 'No Selection',
        message: 'Please select participants to preview labels.'
      });
      return;
    }
    attendeesToPrint = allTickets.filter(t => selectedTickets.has(t.ticket_number));
  }

  // Get selected template
  const templateSelect = document.getElementById('labelTemplateSelect');
  const templateId = templateSelect.value ? parseInt(templateSelect.value) : null;
  let template = null;
  if (templateId) {
    template = await window.electronAPI.getTemplate(templateId);
  }

  await window.electronAPI.previewLabelsPDF(attendeesToPrint, template);
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

  // Collect enabled fields
  const newEnabledFields = [];
  const newLabelFields = [];

  CUSTOM_FIELDS.forEach(field => {
    const fieldCheckbox = document.getElementById(`field${field.id.charAt(0).toUpperCase() + field.id.slice(1)}`);
    const labelCheckbox = document.getElementById(`label${field.id.charAt(0).toUpperCase() + field.id.slice(1)}`);

    if (fieldCheckbox && fieldCheckbox.checked) {
      newEnabledFields.push(field.id);
    }
    if (labelCheckbox && labelCheckbox.checked) {
      newLabelFields.push(field.id);
    }
  });

  // Get selected theme
  const activeThemeBtn = document.querySelector('.theme-toggle-btn.active');
  const theme = activeThemeBtn ? activeThemeBtn.dataset.theme : 'light';

  const settings = {
    theme: theme,
    mode: document.querySelector('input[name="mode"]:checked').value,
    organization_name: document.getElementById('orgName').value,
    event_name: document.getElementById('eventName').value,
    event_code: document.getElementById('eventCode').value.toUpperCase(),
    ticket_color: document.getElementById('accentColorText').value,
    qr_enabled: document.getElementById('qrEnabled').checked ? 'true' : 'false',
    event_emoji: document.getElementById('eventEmoji').value.trim(),
    enabled_fields: JSON.stringify(newEnabledFields),
    label_fields: JSON.stringify(newLabelFields),
    label_show_borders: document.getElementById('showBorders').checked ? 'true' : 'false',
    label_vertical_gap: document.getElementById('vGap').value,
    label_horizontal_gap: document.getElementById('hGap').value,
    label_top_margin: document.getElementById('topMargin').value,
    label_left_margin: document.getElementById('leftMargin').value
  };

  await window.electronAPI.saveSettings(settings);

  // Clear unsaved changes state
  originalSettingsState = null;

  await window.electronAPI.showMessage({
    type: 'info',
    title: 'Settings Saved',
    message: 'Settings have been saved successfully!'
  });

  await loadSettings();
  await loadTickets();
}

// Auto-Updater
function initializeUpdateChecking() {
  // Listen for update available
  window.electronAPI.onUpdateAvailable((updateInfo) => {
    showUpdateNotification(updateInfo);
  });

  // Listen for update not available
  window.electronAPI.onUpdateNotAvailable(() => {
    document.getElementById('updateStatusText').textContent = '✓ You have the latest version';
    setTimeout(() => {
      document.getElementById('updateStatusText').textContent = '';
    }, 3000);
  });

  // Listen for download progress
  window.electronAPI.onUpdateDownloadProgress((progress) => {
    const progressContainer = document.getElementById('updateProgressContainer');
    const progressFill = document.getElementById('updateProgressFill');
    const progressText = document.getElementById('updateProgressText');

    progressContainer.classList.remove('hidden');
    progressFill.style.width = `${progress.percent}%`;

    const mbTransferred = (progress.transferred / 1024 / 1024).toFixed(1);
    const mbTotal = (progress.total / 1024 / 1024).toFixed(1);
    const speedMB = (progress.bytesPerSecond / 1024 / 1024).toFixed(1);

    progressText.textContent = `Downloading... ${mbTransferred} MB / ${mbTotal} MB (${speedMB} MB/s)`;
  });

  // Listen for update downloaded
  window.electronAPI.onUpdateDownloaded((info) => {
    const notification = document.getElementById('updateNotification');
    const headerText = document.getElementById('updateHeaderText');
    const message = document.getElementById('updateMessage');
    const progressContainer = document.getElementById('updateProgressContainer');
    const downloadBtn = document.getElementById('downloadUpdateBtn');
    const installBtn = document.getElementById('installUpdateBtn');

    headerText.textContent = 'Update Ready!';
    message.textContent = `Version ${info.version} has been downloaded and is ready to install.`;
    progressContainer.classList.add('hidden');
    downloadBtn.classList.add('hidden');
    installBtn.classList.remove('hidden');
    notification.classList.remove('hidden');
  });

  // Listen for update error
  window.electronAPI.onUpdateError((error) => {
    console.error('Update error:', error);
    document.getElementById('updateStatusText').textContent = `✗ Update failed: ${error.message}`;
    setTimeout(() => {
      document.getElementById('updateStatusText').textContent = '';
    }, 5000);
  });

  // Check for updates button
  const checkUpdatesBtn = document.getElementById('checkUpdatesBtn');
  if (checkUpdatesBtn) {
    checkUpdatesBtn.addEventListener('click', async () => {
      checkUpdatesBtn.disabled = true;
      document.getElementById('updateStatusText').textContent = 'Checking...';

      await window.electronAPI.checkForUpdates();
      checkUpdatesBtn.disabled = false;
    });
  }

  // Download update button
  const downloadUpdateBtn = document.getElementById('downloadUpdateBtn');
  if (downloadUpdateBtn) {
    downloadUpdateBtn.addEventListener('click', async () => {
      downloadUpdateBtn.disabled = true;
      downloadUpdateBtn.textContent = 'Downloading...';
      await window.electronAPI.downloadUpdate();
    });
  }

  // Install update button
  const installUpdateBtn = document.getElementById('installUpdateBtn');
  if (installUpdateBtn) {
    installUpdateBtn.addEventListener('click', async () => {
      await window.electronAPI.installUpdate();
    });
  }
}

function showUpdateNotification(updateInfo) {
  const notification = document.getElementById('updateNotification');
  const message = document.getElementById('updateMessage');

  if (notification && message) {
    message.textContent = `Version ${updateInfo.version} is now available. Click below to download.`;
    if (updateInfo.releaseNotes) {
      message.textContent += `\n\nWhat's new:\n${updateInfo.releaseNotes}`;
    }
    notification.classList.remove('hidden');
  }
}
