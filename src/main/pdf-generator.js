const PDFDocument = require('pdfkit');
const QRCode = require('qrcode');
const fs = require('fs');
const path = require('path');

class PDFGenerator {
  constructor(settings) {
    this.settings = settings;
  }

  async generateTicketsPDF(tickets, outputPath, template = null) {
    // If custom template provided, use it
    if (template && template.elements && template.elements.length > 0) {
      return this.generateCustomTicketsPDF(tickets, outputPath, template);
    }

    // Otherwise use default layout
    return this.generateDefaultTicketsPDF(tickets, outputPath);
  }

  async generateDefaultTicketsPDF(tickets, outputPath) {
    const doc = new PDFDocument({
      size: 'LETTER',
      margins: { top: 36, bottom: 36, left: 36, right: 36 }
    });

    const stream = fs.createWriteStream(outputPath);
    doc.pipe(stream);

    const mode = this.settings.mode || 'ticketing';
    const orgName = this.settings.organization_name || 'Organization';
    const eventName = this.settings.event_name || 'Event';
    const eventEmoji = this.settings.event_emoji || '';
    const eventCode = this.settings.event_code || 'EVT';
    const accentColor = this.settings.ticket_color || '#ff7a00';
    const qrEnabled = this.settings.qr_enabled === 'true';

    // Ticket dimensions (3.5" x 2.5" like the original Python version)
    const ticketWidth = 3.5 * 72;  // 252 points
    const ticketHeight = 2.5 * 72; // 180 points
    const margin = 0.5 * 72;        // 36 points
    const padding = 0.2 * 72;       // 14.4 points

    const pageWidth = 612;  // Letter size
    const pageHeight = 792;

    // Calculate how many tickets fit per row
    const ticketsPerRow = Math.max(1, Math.floor((pageWidth - 2 * margin) / (ticketWidth + padding)));

    let col = 0;
    let yPos = margin;  // Start at top margin, not bottom

    for (let i = 0; i < tickets.length; i++) {
      const ticket = tickets[i];
      const fullName = `${ticket.first_name} ${ticket.last_name}`;

      const x = margin + col * (ticketWidth + padding);

      // Draw border with accent color
      doc.lineWidth(3)
        .roundedRect(x, yPos, ticketWidth, ticketHeight, 10)
        .stroke(accentColor);

      // EVENT NAME at top (what is this ticket for?)
      const displayEventName = eventEmoji ? `${eventEmoji}  ${eventName}  ${eventEmoji}` : eventName;
      doc.fillColor('#000000')
        .fontSize(14)
        .font('Helvetica-Bold')
        .text(displayEventName, x, yPos + 12, {
          width: ticketWidth,
          align: 'center'
        });

      // Organization name below event
      doc.fontSize(9)
        .font('Helvetica')
        .fillColor('#666666')
        .text(orgName, x, yPos + 32, {
          width: ticketWidth,
          align: 'center'
        });

      // PARTICIPANT NAME - LARGE in middle (who is it for?)
      doc.fillColor('#000000')
        .fontSize(20)
        .font('Helvetica-Bold')
        .text(fullName, x, yPos + 75, {
          width: ticketWidth,
          align: 'center'
        });

      // "ACCESS TICKET" label below name
      doc.fontSize(8)
        .font('Helvetica')
        .fillColor('#999999')
        .text('ACCESS TICKET', x, yPos + 105, {
          width: ticketWidth,
          align: 'center'
        });

      // Ticket code at bottom (small - just for reference)
      doc.fontSize(10)
        .font('Helvetica')
        .fillColor('#999999')
        .text(ticket.ticket_code || `${eventCode}-??????`, x, yPos + 158, {
          width: ticketWidth,
          align: 'center'
        });

      // QR Code (if enabled and in ticketing mode) - top-right corner
      if (qrEnabled && mode === 'ticketing' && ticket.ticket_code) {
        try {
          const qrDataUrl = await QRCode.toDataURL(ticket.ticket_code, {
            width: 130,
            margin: 0
          });
          const qrBuffer = Buffer.from(qrDataUrl.split(',')[1], 'base64');
          // Position in top-right corner
          const qrSize = 0.9 * 72; // ~65 points
          doc.image(qrBuffer, x + ticketWidth - qrSize - 10, yPos + 10, {
            width: qrSize,
            height: qrSize
          });
        } catch (error) {
          console.error('QR Code generation error:', error);
        }
      }

      // Move to next position
      col++;
      if (col >= ticketsPerRow) {
        col = 0;
        yPos += ticketHeight + padding;  // Move DOWN the page

        // Check if we need a new page (if next row would go past bottom margin)
        if (yPos + ticketHeight > pageHeight - margin && i < tickets.length - 1) {
          doc.addPage();
          yPos = margin;  // Reset to top of new page
        }
      }
    }

    doc.end();

    return new Promise((resolve, reject) => {
      stream.on('finish', () => resolve(outputPath));
      stream.on('error', reject);
    });
  }

  async generateLabelsPDF(attendees, outputPath, template = null) {
    // If custom template provided, use it
    if (template && template.elements && template.elements.length > 0) {
      return this.generateCustomLabelsPDF(attendees, outputPath, template);
    }

    // Otherwise use default layout
    return this.generateDefaultLabelsPDF(attendees, outputPath);
  }

  async generateTestPatternPDF(outputPath) {
    const doc = new PDFDocument({
      size: 'LETTER',
      margins: { top: 0, bottom: 0, left: 0, right: 0 }
    });

    const stream = fs.createWriteStream(outputPath);
    doc.pipe(stream);

    // Avery 5160 official specifications
    const labelWidth = 2.625 * 72;   // 2.625" label width
    const labelHeight = 1.0 * 72;    // 1.0" label height
    const leftMargin = parseFloat(this.settings.label_left_margin || '0.19') * 72;  // 0.19" left margin (official spec)
    const topMargin = parseFloat(this.settings.label_top_margin || '0.5') * 72;     // 0.5" top margin (official spec)
    const hGap = parseFloat(this.settings.label_horizontal_gap || '0.125') * 72;    // 0.125" horizontal gap (pitch 2.75" - width 2.625")
    const vGap = parseFloat(this.settings.label_vertical_gap || '0') * 72;          // 0" vertical gap (pitch 1.0" - height 1.0")

    const cols = 3;
    const rows = 10;
    const labelsPerPage = cols * rows;

    // Generate test pattern for all 30 labels
    for (let labelIndex = 0; labelIndex < labelsPerPage; labelIndex++) {
      const row = Math.floor(labelIndex / cols);
      const col = labelIndex % cols;

      const x = leftMargin + col * (labelWidth + hGap);
      const y = topMargin + row * (labelHeight + vGap);

      // Draw border with rounded corners (matching Avery template)
      doc.roundedRect(x, y, labelWidth, labelHeight, 6).stroke('#000000');

      // Draw corner markers (small crosses at each corner)
      const markerSize = 5;
      // Top-left
      doc.moveTo(x, y + markerSize).lineTo(x, y - markerSize).stroke();
      doc.moveTo(x - markerSize, y).lineTo(x + markerSize, y).stroke();
      // Top-right
      doc.moveTo(x + labelWidth, y + markerSize).lineTo(x + labelWidth, y - markerSize).stroke();
      doc.moveTo(x + labelWidth - markerSize, y).lineTo(x + labelWidth + markerSize, y).stroke();
      // Bottom-left
      doc.moveTo(x, y + labelHeight + markerSize).lineTo(x, y + labelHeight - markerSize).stroke();
      doc.moveTo(x - markerSize, y + labelHeight).lineTo(x + markerSize, y + labelHeight).stroke();
      // Bottom-right
      doc.moveTo(x + labelWidth, y + labelHeight + markerSize).lineTo(x + labelWidth, y + labelHeight - markerSize).stroke();
      doc.moveTo(x + labelWidth - markerSize, y + labelHeight).lineTo(x + labelWidth + markerSize, y + labelHeight).stroke();

      // Label position number in center
      doc.fontSize(24)
        .font('Helvetica-Bold')
        .fillColor('#000000')
        .text(`#${labelIndex + 1}`, x, y + labelHeight / 2 - 15, {
          width: labelWidth,
          align: 'center'
        });

      // Row and column info
      doc.fontSize(10)
        .font('Helvetica')
        .text(`Row ${row + 1}, Col ${col + 1}`, x, y + labelHeight / 2 + 10, {
          width: labelWidth,
          align: 'center'
        });

      // Dimensions in small text at bottom
      doc.fontSize(8)
        .fillColor('#666666')
        .text('Avery 5160 Test', x, y + labelHeight - 15, {
          width: labelWidth,
          align: 'center'
        });
    }

    doc.end();

    return new Promise((resolve, reject) => {
      stream.on('finish', () => resolve(outputPath));
      stream.on('error', reject);
    });
  }

  async generateDefaultLabelsPDF(attendees, outputPath) {
    const doc = new PDFDocument({
      size: 'LETTER',
      margins: { top: 0, bottom: 0, left: 0, right: 0 }
    });

    const stream = fs.createWriteStream(outputPath);
    doc.pipe(stream);

    const mode = this.settings.mode || 'ticketing';
    const eventName = this.settings.event_name || 'Event';
    const eventEmoji = this.settings.event_emoji || '';
    const qrEnabled = this.settings.qr_enabled === 'true';
    const showBorders = this.settings.label_show_borders === 'true';

    // Avery 5160 official specifications
    // Official Avery 5160: 2.625" × 1", 3 cols × 10 rows
    const labelWidth = 2.625 * 72;   // 2.625" label width
    const labelHeight = 1.0 * 72;    // 1.0" label height
    const leftMargin = parseFloat(this.settings.label_left_margin || '0.19') * 72;  // 0.19" left margin (official spec)
    const topMargin = parseFloat(this.settings.label_top_margin || '0.5') * 72;     // 0.5" top margin (official spec)
    const hGap = parseFloat(this.settings.label_horizontal_gap || '0.125') * 72;    // 0.125" horizontal gap (pitch 2.75" - width 2.625")
    const vGap = parseFloat(this.settings.label_vertical_gap || '0') * 72;          // 0" vertical gap (pitch 1.0" - height 1.0")

    const cols = 3;
    const rows = 10;
    const labelsPerPage = cols * rows;

    // Deduplicate attendees by (name, classroom) and count quantities
    const attendeeMap = new Map();
    attendees.forEach(a => {
      const key = `${a.first_name}|${a.last_name}|${a.classroom || ''}`;
      if (attendeeMap.has(key)) {
        attendeeMap.get(key).quantity++;
      } else {
        attendeeMap.set(key, { ...a, quantity: 1 });
      }
    });

    const uniqueAttendees = Array.from(attendeeMap.values());

    let labelIndex = 0;

    for (const attendee of uniqueAttendees) {
      if (labelIndex > 0 && labelIndex % labelsPerPage === 0) {
        doc.addPage();
      }

      const row = Math.floor((labelIndex % labelsPerPage) / cols);
      const col = labelIndex % cols;

      const x = leftMargin + col * (labelWidth + hGap);
      const y = topMargin + row * (labelHeight + vGap);

      // Border (for testing alignment)
      if (showBorders) {
        doc.rect(x, y, labelWidth, labelHeight).stroke('#cccccc');
      }

      const fullName = `${attendee.first_name} ${attendee.last_name}`;

      // Load layout configuration
      const layoutConfig = JSON.parse(this.settings.label_layout_config || '{}');
      const nameConfig = layoutConfig.name || { size: 11, order: 0, bold: true, italic: false };
      const qtyConfig = layoutConfig.qty || { size: 9, order: 9, bold: false, italic: false };
      const fieldsConfig = layoutConfig.fields || {};

      // Build array of all elements with their order
      const elements = [];

      // Add name
      elements.push({
        type: 'name',
        order: nameConfig.order,
        size: nameConfig.size,
        bold: nameConfig.bold,
        italic: nameConfig.italic,
        text: fullName
      });

      // Add data fields
      const labelFields = JSON.parse(this.settings.label_fields || '["classroom"]');
      const fieldLabels = {
        classroom: (val) => `Room ${val}`,
        teacher: (val) => val,
        grade: (val) => `Grade ${val}`,
        address: (val) => val,
        email: (val) => val,
        phone: (val) => val,
        notes: (val) => val
      };

      labelFields.forEach((fieldId, index) => {
        const value = attendee[fieldId];
        if (value) {
          const fieldConfig = fieldsConfig[fieldId] || { size: 9, order: 1 + index, bold: false, italic: false };
          const displayText = fieldLabels[fieldId] ? fieldLabels[fieldId](value) : value;
          elements.push({
            type: 'field',
            order: fieldConfig.order,
            size: fieldConfig.size,
            bold: fieldConfig.bold,
            italic: fieldConfig.italic,
            text: displayText
          });
        }
      });

      // Add event name or quantity
      const qtyText = mode === 'sales' ? `Qty: ${attendee.quantity || 1}` : eventName;
      elements.push({
        type: 'qty',
        order: qtyConfig.order,
        size: qtyConfig.size,
        bold: qtyConfig.bold,
        italic: qtyConfig.italic,
        text: qtyText
      });

      // Sort by order
      elements.sort((a, b) => a.order - b.order);

      // Calculate total height of all content to center it vertically
      let totalHeight = 0;
      elements.forEach(element => {
        const fontName = element.bold && element.italic ? 'Helvetica-BoldOblique' :
                        element.bold ? 'Helvetica-Bold' :
                        element.italic ? 'Helvetica-Oblique' :
                        'Helvetica';

        doc.fontSize(element.size).font(fontName);
        const textHeight = doc.heightOfString(element.text, {
          width: labelWidth - 20,
          align: 'center'
        });
        totalHeight += textHeight + 3; // 3pt spacing between elements
      });
      totalHeight -= 3; // Remove spacing after last element

      // Start position - center content vertically in label
      let yPos = y + (labelHeight - totalHeight) / 2;

      // Render elements in order
      elements.forEach(element => {
        const fontName = element.bold && element.italic ? 'Helvetica-BoldOblique' :
                        element.bold ? 'Helvetica-Bold' :
                        element.italic ? 'Helvetica-Oblique' :
                        'Helvetica';

        doc.fontSize(element.size)
          .font(fontName)
          .fillColor('#000000')
          .text(element.text, x + 10, yPos, {
            width: labelWidth - 20,
            align: 'center'
          });

        const textHeight = doc.heightOfString(element.text, {
          width: labelWidth - 20,
          align: 'center'
        });
        yPos += textHeight + 3;
      });

      labelIndex++;
    }

    doc.end();

    return new Promise((resolve, reject) => {
      stream.on('finish', () => resolve(outputPath));
      stream.on('error', reject);
    });
  }
  async generateCustomTicketsPDF(tickets, outputPath, template) {
    const doc = new PDFDocument({
      size: 'LETTER',
      margins: { top: 36, bottom: 36, left: 36, right: 36 }
    });

    const stream = fs.createWriteStream(outputPath);
    doc.pipe(stream);

    const mode = this.settings.mode || 'ticketing';
    const eventCode = this.settings.event_code || 'EVT';

    // Ticket dimensions (3.5" x 2.5")
    const ticketWidth = 3.5 * 72;  // 252 points
    const ticketHeight = 2.5 * 72; // 180 points
    const margin = 0.5 * 72;
    const padding = 0.2 * 72;

    const pageWidth = 612;
    const pageHeight = 792;

    const ticketsPerRow = Math.max(1, Math.floor((pageWidth - 2 * margin) / (ticketWidth + padding)));

    let col = 0;
    let yPos = margin;

    for (let i = 0; i < tickets.length; i++) {
      const ticket = tickets[i];
      const x = margin + col * (ticketWidth + padding);

      // Draw border
      doc.lineWidth(2)
        .roundedRect(x, yPos, ticketWidth, ticketHeight, 10)
        .stroke('#cccccc');

      // Render each element from template
      for (const element of template.elements) {
        await this.renderTemplateElement(doc, element, ticket, x, yPos, 0.5); // 0.5 = scale from 2x to 1x
      }

      // Move to next position
      col++;
      if (col >= ticketsPerRow) {
        col = 0;
        yPos += ticketHeight + padding;

        if (yPos + ticketHeight > pageHeight - margin && i < tickets.length - 1) {
          doc.addPage();
          yPos = margin;
        }
      }
    }

    doc.end();

    return new Promise((resolve, reject) => {
      stream.on('finish', () => resolve(outputPath));
      stream.on('error', reject);
    });
  }

  async generateCustomLabelsPDF(attendees, outputPath, template) {
    const doc = new PDFDocument({
      size: 'LETTER',
      margins: { top: 0, bottom: 0, left: 0, right: 0 }
    });

    const stream = fs.createWriteStream(outputPath);
    doc.pipe(stream);

    // Avery 5160 official specifications
    // Official Avery 5160: 2.625" × 1", 3 cols × 10 rows
    const labelWidth = 2.625 * 72;   // 2.625" label width
    const labelHeight = 1.0 * 72;    // 1.0" label height
    const leftMargin = parseFloat(this.settings.label_left_margin || '0.19') * 72;  // 0.19" left margin (official spec)
    const topMargin = parseFloat(this.settings.label_top_margin || '0.5') * 72;     // 0.5" top margin (official spec)
    const hGap = parseFloat(this.settings.label_horizontal_gap || '0.125') * 72;    // 0.125" horizontal gap (pitch 2.75" - width 2.625")
    const vGap = parseFloat(this.settings.label_vertical_gap || '0') * 72;          // 0" vertical gap (pitch 1.0" - height 1.0")
    const showBorders = this.settings.label_show_borders === 'true';

    const cols = 3;
    const rows = 10;
    const labelsPerPage = cols * rows;

    // Deduplicate attendees
    const seen = new Set();
    const uniqueAttendees = attendees.filter(a => {
      const key = `${a.first_name}|${a.last_name}|${a.classroom || ''}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    let labelIndex = 0;

    for (const attendee of uniqueAttendees) {
      if (labelIndex > 0 && labelIndex % labelsPerPage === 0) {
        doc.addPage();
      }

      const row = Math.floor((labelIndex % labelsPerPage) / cols);
      const col = labelIndex % cols;

      const x = leftMargin + col * (labelWidth + hGap);
      const y = topMargin + row * (labelHeight + vGap);

      // Border (for testing alignment)
      if (showBorders) {
        doc.rect(x, y, labelWidth, labelHeight).stroke('#cccccc');
      }

      // Render each element from template
      for (const element of template.elements) {
        await this.renderTemplateElement(doc, element, attendee, x, y, 0.5); // 0.5 = scale from 2x to 1x
      }

      labelIndex++;
    }

    doc.end();

    return new Promise((resolve, reject) => {
      stream.on('finish', () => resolve(outputPath));
      stream.on('error', reject);
    });
  }

  async renderTemplateElement(doc, element, data, offsetX, offsetY, scale) {
    // Scale coordinates and sizes from designer (2x) to print (1x)
    const x = offsetX + (element.x * scale);
    const y = offsetY + (element.y * scale);
    const width = element.width * scale;
    const height = element.height * scale;
    const fontSize = element.fontSize * scale;

    if (element.type === 'qrcode') {
      // Render QR code
      const qrData = data.ticket_code || data.ticket_number || 'N/A';
      try {
        const qrDataUrl = await QRCode.toDataURL(qrData, {
          width: Math.round(width * 2),
          margin: 0
        });
        const qrBuffer = Buffer.from(qrDataUrl.split(',')[1], 'base64');
        doc.image(qrBuffer, x, y, {
          width: width,
          height: height
        });
      } catch (error) {
        console.error('QR Code generation error:', error);
      }
    } else if (element.type === 'static') {
      // Render static text
      const text = element.staticText || '';
      doc.fontSize(fontSize)
        .font(element.fontWeight === 'bold' ? 'Helvetica-Bold' : 'Helvetica')
        .fillColor(element.color || '#000000')
        .text(text, x, y, {
          width: width,
          height: height,
          align: element.textAlign || 'left'
        });
    } else {
      // Render data field
      let text = '';

      // Map field names to data
      if (element.field === 'event_name') {
        text = this.settings.event_name || 'Event';
      } else if (element.field === 'organization_name') {
        text = this.settings.organization_name || 'Organization';
      } else if (element.field === 'participant_name') {
        text = `${data.first_name || ''} ${data.last_name || ''}`.trim();
      } else if (element.field === 'first_name') {
        text = data.first_name || '';
      } else if (element.field === 'last_name') {
        text = data.last_name || '';
      } else if (element.field === 'ticket_code') {
        text = data.ticket_code || '';
      } else if (element.field === 'ticket_number') {
        text = data.ticket_number ? String(data.ticket_number) : '';
      } else if (element.field === 'classroom') {
        text = data.classroom || '';
      } else if (element.field === 'teacher') {
        text = data.teacher || '';
      } else if (element.field === 'grade') {
        text = data.grade || '';
      } else if (element.field === 'address') {
        text = data.address || '';
      } else if (element.field === 'email') {
        text = data.email || '';
      } else if (element.field === 'phone') {
        text = data.phone || '';
      }

      if (text) {
        doc.fontSize(fontSize)
          .font(element.fontWeight === 'bold' ? 'Helvetica-Bold' : 'Helvetica')
          .fillColor(element.color || '#000000')
          .text(text, x, y, {
            width: width,
            height: height,
            align: element.textAlign || 'left'
          });
      }
    }
  }
}

module.exports = PDFGenerator;
