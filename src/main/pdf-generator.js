const PDFDocument = require('pdfkit');
const QRCode = require('qrcode');
const fs = require('fs');
const path = require('path');

class PDFGenerator {
  constructor(settings) {
    this.settings = settings;
  }

  async generateTicketsPDF(tickets, outputPath) {
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

  async generateLabelsPDF(attendees, outputPath) {
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

    // Avery 5160 dimensions (in points: 1 inch = 72 points)
    const labelWidth = 2.625 * 72;
    const labelHeight = 1.0 * 72;
    const leftMargin = parseFloat(this.settings.label_left_margin || '0.1875') * 72;
    const topMargin = parseFloat(this.settings.label_top_margin || '0.5') * 72;
    const hGap = parseFloat(this.settings.label_horizontal_gap || '0.0') * 72;
    const vGap = parseFloat(this.settings.label_vertical_gap || '0.0') * 72;

    const cols = 3;
    const rows = 10;
    const labelsPerPage = cols * rows;

    // Deduplicate attendees by (name, classroom)
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

      const fullName = `${attendee.first_name} ${attendee.last_name}`;

      // Emoji decoration (if set)
      let yPos = y + 10;
      if (eventEmoji) {
        doc.fontSize(16)
          .font('Helvetica')
          .fillColor('#000000')
          .text(eventEmoji, x + 10, yPos, {
            width: labelWidth - 20,
            align: 'center'
          });
        yPos += 18;
      }

      // Name
      doc.fontSize(11)
        .font('Helvetica-Bold')
        .fillColor('#000000')
        .text(fullName, x + 10, yPos, {
          width: labelWidth - 20,
          align: 'center'
        });

      yPos += eventEmoji ? 17 : 22;

      // Dynamic label fields based on configuration
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

      // Show configured fields on label
      labelFields.forEach(fieldId => {
        const value = attendee[fieldId];
        if (value) {
          const displayText = fieldLabels[fieldId] ? fieldLabels[fieldId](value) : value;
          doc.fontSize(9)
            .font('Helvetica')
            .text(displayText, x + 10, yPos, {
              width: labelWidth - 20,
              align: 'center'
            });
          yPos += 12;
        }
      });

      // Show event name (ticketing) or quantity (sales) at the end
      if (mode === 'sales') {
        doc.fontSize(9)
          .text('Qty: 1', x + 10, yPos, {
            width: labelWidth - 20,
            align: 'center'
          });
      } else {
        doc.fontSize(9)
          .text(eventName, x + 10, yPos, {
            width: labelWidth - 20,
            align: 'center'
          });
      }

      labelIndex++;
    }

    doc.end();

    return new Promise((resolve, reject) => {
      stream.on('finish', () => resolve(outputPath));
      stream.on('error', reject);
    });
  }
}

module.exports = PDFGenerator;
