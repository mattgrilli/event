// Template Designer Module
// Handles drag-and-drop visual designer for tickets and labels

let currentTemplate = {
  type: 'ticket', // 'ticket' or 'label'
  name: 'default',
  elements: []
};

let selectedElement = null;
let elementIdCounter = 0;
let isDraggingElement = false;
let isResizingElement = false;
let dragOffset = { x: 0, y: 0 };
let resizeStart = { x: 0, y: 0, width: 0, height: 0 };

const TEMPLATE_DIMENSIONS = {
  ticket: { width: 504, height: 360, widthIn: 3.5, heightIn: 2.5, scale: 2 },
  label: { width: 378, height: 144, widthIn: 2.625, heightIn: 1.0, scale: 2 }
};

const SAMPLE_DATA = {
  event_name: 'Pretzel Sale 2024',
  organization_name: 'Lincoln Elementary PTA',
  participant_name: 'John Smith',
  first_name: 'John',
  last_name: 'Smith',
  ticket_code: 'EVT-ABC123',
  ticket_number: '42',
  classroom: '101',
  teacher: 'Ms. Johnson',
  grade: '3rd',
  address: '123 Main St',
  email: 'john@example.com',
  phone: '555-1234'
};

function initializeDesigner() {
  const canvas = document.getElementById('designerCanvas');
  const templateTypeSelect = document.getElementById('templateType');

  // Set initial canvas dimensions
  updateCanvasDimensions();

  // Template type change
  templateTypeSelect.addEventListener('change', (e) => {
    currentTemplate.type = e.target.value;
    currentTemplate.elements = [];
    updateCanvasDimensions();
    renderCanvas();
    updateDimensionsDisplay();
  });

  // Toolbox drag start
  document.querySelectorAll('.toolbox-item').forEach(item => {
    item.addEventListener('dragstart', handleToolboxDragStart);
  });

  // Canvas drop zone
  canvas.addEventListener('dragover', handleCanvasDragOver);
  canvas.addEventListener('drop', handleCanvasDrop);

  // Canvas click (deselect)
  canvas.addEventListener('click', (e) => {
    if (e.target === canvas) {
      deselectElement();
    }
  });

  // Properties panel inputs
  setupPropertiesListeners();

  // Template actions
  document.getElementById('newTemplateBtn').addEventListener('click', handleNewTemplate);
  document.getElementById('saveTemplateBtn').addEventListener('click', handleSaveTemplate);
  document.getElementById('saveAsTemplateBtn').addEventListener('click', handleSaveAsTemplate);
  document.getElementById('deleteTemplateBtn').addEventListener('click', handleDeleteTemplate);
  document.getElementById('previewTemplateBtn').addEventListener('click', handlePreviewTemplate);

  // Template select dropdown
  const templateSelect = document.getElementById('templateSelect');
  templateSelect.addEventListener('change', handleTemplateSelect);

  // Template type change should also reload template list
  templateTypeSelect.addEventListener('change', async () => {
    await loadTemplateList();
  });

  updateDimensionsDisplay();
  loadTemplateList(); // Load templates on init
}

function updateCanvasDimensions() {
  const canvas = document.getElementById('designerCanvas');
  const dims = TEMPLATE_DIMENSIONS[currentTemplate.type];

  canvas.className = `designer-canvas ${currentTemplate.type}`;
  canvas.style.width = `${dims.width}px`;
  canvas.style.height = `${dims.height}px`;
}

function updateDimensionsDisplay() {
  const dims = TEMPLATE_DIMENSIONS[currentTemplate.type];
  const display = document.getElementById('templateDimensions');
  display.textContent = `${dims.widthIn}" × ${dims.heightIn}" (shown at ${dims.scale}× scale)`;
}

function handleToolboxDragStart(e) {
  const fieldType = e.target.dataset.field;
  const fieldLabel = e.target.textContent.trim();

  e.dataTransfer.effectAllowed = 'copy';
  e.dataTransfer.setData('application/json', JSON.stringify({
    field: fieldType,
    label: fieldLabel,
    type: e.target.dataset.type || 'text'
  }));
}

function handleCanvasDragOver(e) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'copy';
}

function handleCanvasDrop(e) {
  e.preventDefault();

  const data = JSON.parse(e.dataTransfer.getData('application/json'));
  const canvas = document.getElementById('designerCanvas');
  const rect = canvas.getBoundingClientRect();

  // Calculate drop position relative to canvas
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;

  // Default sizes (2x scale for editor)
  const defaultWidth = data.type === 'qrcode' ? 120 : 200;
  const defaultHeight = data.type === 'qrcode' ? 120 : 40;

  // Create new element
  const element = {
    id: `element-${elementIdCounter++}`,
    field: data.field,
    label: data.label,
    type: data.type,
    x: Math.max(0, Math.min(x - defaultWidth / 2, rect.width - defaultWidth)),
    y: Math.max(0, Math.min(y - defaultHeight / 2, rect.height - defaultHeight)),
    width: defaultWidth,
    height: defaultHeight,
    fontSize: 24,  // 2x scale
    fontWeight: 'normal',
    textAlign: 'left',
    color: '#000000',
    staticText: data.type === 'static' ? 'Text' : ''
  };

  currentTemplate.elements.push(element);
  renderCanvas();
  selectElement(element.id);
}

function renderCanvas() {
  const canvas = document.getElementById('designerCanvas');

  // Clear canvas
  const elements = canvas.querySelectorAll('.canvas-element');
  elements.forEach(el => el.remove());

  // Render each element
  currentTemplate.elements.forEach(element => {
    const div = document.createElement('div');
    div.className = 'canvas-element';
    if (selectedElement && selectedElement.id === element.id) {
      div.classList.add('selected');
    }
    div.dataset.elementId = element.id;

    // Position and size
    div.style.left = `${element.x}px`;
    div.style.top = `${element.y}px`;
    div.style.width = `${element.width}px`;
    div.style.height = `${element.height}px`;

    // Content
    if (element.type === 'qrcode') {
      div.style.backgroundColor = '#f0f0f0';
      div.style.border = '2px solid #ccc';
      div.style.display = 'flex';
      div.style.alignItems = 'center';
      div.style.justifyContent = 'center';
      div.innerHTML = '<span style="font-size: 10px; color: #999;">QR</span>';
    } else if (element.type === 'static') {
      div.style.fontSize = `${element.fontSize}px`;
      div.style.fontWeight = element.fontWeight;
      div.style.textAlign = element.textAlign;
      div.style.color = element.color;
      div.textContent = element.staticText || 'Text';
    } else {
      // Data field
      div.style.fontSize = `${element.fontSize}px`;
      div.style.fontWeight = element.fontWeight;
      div.style.textAlign = element.textAlign;
      div.style.color = element.color;
      div.textContent = SAMPLE_DATA[element.field] || element.label;
    }

    // Label tag
    const label = document.createElement('div');
    label.className = 'element-label';
    label.textContent = element.label;
    div.appendChild(label);

    // Resize handle (if selected)
    if (selectedElement && selectedElement.id === element.id) {
      const handle = document.createElement('div');
      handle.className = 'element-handle';
      div.appendChild(handle);
    }

    // Event listeners
    div.addEventListener('click', (e) => {
      e.stopPropagation();
      selectElement(element.id);
    });

    div.addEventListener('mousedown', (e) => {
      if (e.target.classList.contains('element-handle')) {
        // Start resize
        startResizeElement(e, element.id);
      } else {
        // Start drag
        startDragElement(e, element.id);
      }
    });

    canvas.appendChild(div);
  });
}

function selectElement(elementId) {
  const element = currentTemplate.elements.find(e => e.id === elementId);
  if (!element) return;

  selectedElement = element;
  renderCanvas();
  updatePropertiesPanel(element);
}

function deselectElement() {
  selectedElement = null;
  renderCanvas();
  showPropertiesPlaceholder();
}

function startDragElement(e, elementId) {
  e.preventDefault();
  e.stopPropagation();

  const element = currentTemplate.elements.find(el => el.id === elementId);
  if (!element) return;

  const canvas = document.getElementById('designerCanvas');
  const rect = canvas.getBoundingClientRect();

  // Calculate mouse position relative to canvas
  const mouseX = e.clientX - rect.left;
  const mouseY = e.clientY - rect.top;

  // Calculate offset from mouse to element's top-left corner
  dragOffset.x = mouseX - element.x;
  dragOffset.y = mouseY - element.y;

  isDraggingElement = true;

  function onMouseMove(moveEvent) {
    if (!isDraggingElement) return;

    // Get current mouse position relative to canvas
    const currentMouseX = moveEvent.clientX - rect.left;
    const currentMouseY = moveEvent.clientY - rect.top;

    // Calculate new element position (mouse position minus offset)
    const newX = currentMouseX - dragOffset.x;
    const newY = currentMouseY - dragOffset.y;

    // Constrain to canvas bounds
    element.x = Math.max(0, Math.min(newX, rect.width - element.width));
    element.y = Math.max(0, Math.min(newY, rect.height - element.height));

    renderCanvas();
    if (selectedElement && selectedElement.id === element.id) {
      updatePropertiesPanel(element);
    }
  }

  function onMouseUp() {
    isDraggingElement = false;
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  }

  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

function startResizeElement(e, elementId) {
  e.preventDefault();
  e.stopPropagation();

  const element = currentTemplate.elements.find(el => el.id === elementId);
  if (!element) return;

  const canvas = document.getElementById('designerCanvas');
  const rect = canvas.getBoundingClientRect();

  // Store starting values
  resizeStart.x = e.clientX;
  resizeStart.y = e.clientY;
  resizeStart.width = element.width;
  resizeStart.height = element.height;

  isResizingElement = true;

  function onMouseMove(moveEvent) {
    if (!isResizingElement) return;

    // Calculate how much the mouse has moved
    const deltaX = moveEvent.clientX - resizeStart.x;
    const deltaY = moveEvent.clientY - resizeStart.y;

    // Update element size (minimum 20px)
    element.width = Math.max(20, resizeStart.width + deltaX);
    element.height = Math.max(20, resizeStart.height + deltaY);

    // Constrain to canvas bounds
    const maxWidth = rect.width - element.x;
    const maxHeight = rect.height - element.y;
    element.width = Math.min(element.width, maxWidth);
    element.height = Math.min(element.height, maxHeight);

    renderCanvas();
    if (selectedElement && selectedElement.id === element.id) {
      updatePropertiesPanel(element);
    }
  }

  function onMouseUp() {
    isResizingElement = false;
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  }

  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

function updatePropertiesPanel(element) {
  const content = document.getElementById('propertiesContent');

  content.innerHTML = `
    <div class="property-group">
      <label>Field</label>
      <input type="text" value="${element.label}" readonly style="background-color: var(--bg-main);">
    </div>

    <div class="property-group">
      <label>Position</label>
      <div class="property-row">
        <div>
          <label style="font-size: 0.75rem; color: var(--fg-muted);">X</label>
          <input type="number" id="propX" value="${Math.round(element.x)}" min="0">
        </div>
        <div>
          <label style="font-size: 0.75rem; color: var(--fg-muted);">Y</label>
          <input type="number" id="propY" value="${Math.round(element.y)}" min="0">
        </div>
      </div>
    </div>

    <div class="property-group">
      <label>Size</label>
      <div class="property-row">
        <div>
          <label style="font-size: 0.75rem; color: var(--fg-muted);">Width</label>
          <input type="number" id="propWidth" value="${element.width}" min="10">
        </div>
        <div>
          <label style="font-size: 0.75rem; color: var(--fg-muted);">Height</label>
          <input type="number" id="propHeight" value="${element.height}" min="10">
        </div>
      </div>
    </div>

    ${element.type !== 'qrcode' ? `
      <div class="property-group">
        <label>Font Size</label>
        <input type="number" id="propFontSize" value="${element.fontSize}" min="6" max="72">
      </div>

      <div class="property-group">
        <label>Font Weight</label>
        <select id="propFontWeight">
          <option value="normal" ${element.fontWeight === 'normal' ? 'selected' : ''}>Normal</option>
          <option value="bold" ${element.fontWeight === 'bold' ? 'selected' : ''}>Bold</option>
        </select>
      </div>

      <div class="property-group">
        <label>Text Align</label>
        <select id="propTextAlign">
          <option value="left" ${element.textAlign === 'left' ? 'selected' : ''}>Left</option>
          <option value="center" ${element.textAlign === 'center' ? 'selected' : ''}>Center</option>
          <option value="right" ${element.textAlign === 'right' ? 'selected' : ''}>Right</option>
        </select>
      </div>

      <div class="property-group">
        <label>Color</label>
        <input type="color" id="propColor" value="${element.color}">
      </div>

      ${element.type === 'static' ? `
        <div class="property-group">
          <label>Text Content</label>
          <input type="text" id="propStaticText" value="${element.staticText}" placeholder="Enter text">
        </div>
      ` : ''}
    ` : ''}

    <div class="property-actions">
      <button class="btn btn-danger btn-sm" id="deleteElementBtn">Delete</button>
    </div>
  `;

  // Re-attach listeners
  setupPropertiesListeners();
}

function showPropertiesPlaceholder() {
  const content = document.getElementById('propertiesContent');
  content.innerHTML = '<p class="properties-placeholder">Select an element to edit its properties</p>';
}

function setupPropertiesListeners() {
  const propX = document.getElementById('propX');
  const propY = document.getElementById('propY');
  const propWidth = document.getElementById('propWidth');
  const propHeight = document.getElementById('propHeight');
  const propFontSize = document.getElementById('propFontSize');
  const propFontWeight = document.getElementById('propFontWeight');
  const propTextAlign = document.getElementById('propTextAlign');
  const propColor = document.getElementById('propColor');
  const propStaticText = document.getElementById('propStaticText');
  const deleteBtn = document.getElementById('deleteElementBtn');

  if (propX && selectedElement) {
    propX.addEventListener('input', (e) => {
      selectedElement.x = parseInt(e.target.value) || 0;
      renderCanvas();
    });
  }

  if (propY && selectedElement) {
    propY.addEventListener('input', (e) => {
      selectedElement.y = parseInt(e.target.value) || 0;
      renderCanvas();
    });
  }

  if (propWidth && selectedElement) {
    propWidth.addEventListener('input', (e) => {
      selectedElement.width = parseInt(e.target.value) || 10;
      renderCanvas();
    });
  }

  if (propHeight && selectedElement) {
    propHeight.addEventListener('input', (e) => {
      selectedElement.height = parseInt(e.target.value) || 10;
      renderCanvas();
    });
  }

  if (propFontSize && selectedElement) {
    propFontSize.addEventListener('input', (e) => {
      selectedElement.fontSize = parseInt(e.target.value) || 12;
      renderCanvas();
    });
  }

  if (propFontWeight && selectedElement) {
    propFontWeight.addEventListener('change', (e) => {
      selectedElement.fontWeight = e.target.value;
      renderCanvas();
    });
  }

  if (propTextAlign && selectedElement) {
    propTextAlign.addEventListener('change', (e) => {
      selectedElement.textAlign = e.target.value;
      renderCanvas();
    });
  }

  if (propColor && selectedElement) {
    propColor.addEventListener('input', (e) => {
      selectedElement.color = e.target.value;
      renderCanvas();
    });
  }

  if (propStaticText && selectedElement) {
    propStaticText.addEventListener('input', (e) => {
      selectedElement.staticText = e.target.value;
      renderCanvas();
    });
  }

  if (deleteBtn && selectedElement) {
    deleteBtn.addEventListener('click', () => {
      currentTemplate.elements = currentTemplate.elements.filter(e => e.id !== selectedElement.id);
      deselectElement();
      renderCanvas();
    });
  }
}

function handleNewTemplate() {
  if (currentTemplate.elements.length > 0) {
    if (!confirm('Create new template? This will clear the current canvas.')) {
      return;
    }
  }

  currentTemplate.elements = [];
  deselectElement();
  renderCanvas();
}

async function loadTemplateList() {
  const templateSelect = document.getElementById('templateSelect');
  const templates = await window.electronAPI.getTemplatesByType(currentTemplate.type);

  // Clear dropdown
  templateSelect.innerHTML = '<option value="">New Template</option>';

  // Add templates
  templates.forEach(template => {
    const option = document.createElement('option');
    option.value = template.template_id;
    option.textContent = template.name;
    templateSelect.appendChild(option);
  });
}

async function handleTemplateSelect(e) {
  const templateId = e.target.value;

  if (!templateId) {
    // New template selected
    handleNewTemplate();
    return;
  }

  const template = await window.electronAPI.getTemplate(parseInt(templateId));
  if (template) {
    currentTemplate.name = template.name;
    currentTemplate.type = template.type;
    currentTemplate.elements = template.elements;

    // Update type dropdown
    document.getElementById('templateType').value = template.type;

    updateCanvasDimensions();
    renderCanvas();
    updateDimensionsDisplay();
  }
}

async function handleSaveTemplate() {
  if (currentTemplate.elements.length === 0) {
    await window.electronAPI.showMessage({
      type: 'warning',
      title: 'Empty Template',
      message: 'Cannot save an empty template. Add some elements first.'
    });
    return;
  }

  // If current template has a name, save it
  if (currentTemplate.name && currentTemplate.name !== 'default') {
    try {
      await window.electronAPI.saveTemplate(currentTemplate.name, currentTemplate.type, currentTemplate.elements);
      await window.electronAPI.showMessage({
        type: 'info',
        title: 'Template Saved',
        message: `Template "${currentTemplate.name}" has been saved successfully.`
      });
      await loadTemplateList();
    } catch (error) {
      await window.electronAPI.showMessage({
        type: 'error',
        title: 'Save Failed',
        message: `Failed to save template: ${error.message}`
      });
    }
  } else {
    // No name yet, prompt for "Save As"
    handleSaveAsTemplate();
  }
}

async function handleSaveAsTemplate() {
  if (currentTemplate.elements.length === 0) {
    await window.electronAPI.showMessage({
      type: 'warning',
      title: 'Empty Template',
      message: 'Cannot save an empty template. Add some elements first.'
    });
    return;
  }

  const name = prompt('Enter a name for this template:', currentTemplate.name || '');

  if (!name || name.trim() === '') {
    return; // User canceled
  }

  const trimmedName = name.trim();

  // Check if template with this name already exists
  const existing = await window.electronAPI.getTemplateByName(trimmedName, currentTemplate.type);
  if (existing) {
    const response = await window.electronAPI.showMessage({
      type: 'question',
      title: 'Template Exists',
      message: `A template named "${trimmedName}" already exists. Do you want to overwrite it?`,
      buttons: ['Cancel', 'Overwrite']
    });

    if (response.response !== 1) {
      return; // User canceled
    }
  }

  try {
    await window.electronAPI.saveTemplate(trimmedName, currentTemplate.type, currentTemplate.elements);
    currentTemplate.name = trimmedName;

    await window.electronAPI.showMessage({
      type: 'info',
      title: 'Template Saved',
      message: `Template "${trimmedName}" has been saved successfully.`
    });

    await loadTemplateList();

    // Select the newly saved template in dropdown
    const templateSelect = document.getElementById('templateSelect');
    const saved = await window.electronAPI.getTemplateByName(trimmedName, currentTemplate.type);
    if (saved) {
      templateSelect.value = saved.template_id;
    }
  } catch (error) {
    await window.electronAPI.showMessage({
      type: 'error',
      title: 'Save Failed',
      message: `Failed to save template: ${error.message}`
    });
  }
}

async function handleDeleteTemplate() {
  const templateSelect = document.getElementById('templateSelect');
  const templateId = parseInt(templateSelect.value);

  if (!templateId) {
    await window.electronAPI.showMessage({
      type: 'warning',
      title: 'No Template Selected',
      message: 'Please select a template to delete.'
    });
    return;
  }

  const template = await window.electronAPI.getTemplate(templateId);
  if (!template) return;

  const response = await window.electronAPI.showMessage({
    type: 'question',
    title: 'Delete Template',
    message: `Are you sure you want to delete the template "${template.name}"? This cannot be undone.`,
    buttons: ['Cancel', 'Delete']
  });

  if (response.response !== 1) {
    return; // User canceled
  }

  try {
    await window.electronAPI.deleteTemplate(templateId);

    await window.electronAPI.showMessage({
      type: 'info',
      title: 'Template Deleted',
      message: `Template "${template.name}" has been deleted.`
    });

    // Reset to new template
    handleNewTemplate();
    templateSelect.value = '';
    await loadTemplateList();
  } catch (error) {
    await window.electronAPI.showMessage({
      type: 'error',
      title: 'Delete Failed',
      message: `Failed to delete template: ${error.message}`
    });
  }
}

async function handlePreviewTemplate() {
  if (currentTemplate.elements.length === 0) {
    await window.electronAPI.showMessage({
      type: 'warning',
      title: 'Empty Template',
      message: 'Add some elements to the template before previewing.'
    });
    return;
  }

  // Create sample data based on template type
  const sampleTicket = {
    ticket_number: 42,
    ticket_code: 'EVT-ABC123',
    first_name: 'John',
    last_name: 'Smith',
    classroom: '101',
    teacher: 'Ms. Johnson',
    grade: '3rd',
    address: '123 Main St',
    email: 'john@example.com',
    phone: '555-1234'
  };

  // Create template object with elements
  const templateData = {
    name: currentTemplate.name || 'Preview',
    type: currentTemplate.type,
    elements: currentTemplate.elements
  };

  try {
    if (currentTemplate.type === 'ticket') {
      await window.electronAPI.previewTicketsPDF([sampleTicket], templateData);
    } else {
      await window.electronAPI.previewLabelsPDF([sampleTicket], templateData);
    }
  } catch (error) {
    await window.electronAPI.showMessage({
      type: 'error',
      title: 'Preview Failed',
      message: `Failed to generate preview: ${error.message}`
    });
  }
}

// Export for use in main app
window.DesignerModule = {
  initialize: initializeDesigner,
  getCurrentTemplate: () => currentTemplate,
  setTemplate: (template) => {
    currentTemplate = template;
    renderCanvas();
  }
};
