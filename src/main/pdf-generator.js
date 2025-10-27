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
    const accentColor = this.settings.ticket_color || '#ff7a00';
    const qrEnabled = this.settings.qr_enabled === 'true';

    for (let i = 0; i < tickets.length; i++) {
      if (i > 0) doc.addPage();

      const ticket = tickets[i];
      const fullName = `${ticket.first_name} ${ticket.last_name}`;

      // Header with accent color
      doc.rect(0, 0, 612, 80).fill(accentColor);

      // Organization name
      doc.fillColor('#ffffff')
        .fontSize(24)
        .font('Helvetica-Bold')
        .text(orgName, 50, 20, { width: 512, align: 'center' });

      // Event name
      doc.fontSize(16)
        .font('Helvetica')
        .text(eventName, 50, 50, { width: 512, align: 'center' });

      // Ticket info
      doc.fillColor('#000000')
        .fontSize(20)
        .font('Helvetica-Bold')
        .text(fullName, 50, 120, { width: 512, align: 'center' });

      // Ticket code
      doc.fontSize(14)
        .font('Helvetica')
        .text(`Ticket: ${ticket.ticket_code}`, 50, 160, { width: 512, align: 'center' });

      // QR Code (if enabled and in ticketing mode)
      if (qrEnabled && mode === 'ticketing') {
        try {
          const qrDataUrl = await QRCode.toDataURL(ticket.ticket_code, {
            width: 200,
            margin: 1
          });
          const qrBuffer = Buffer.from(qrDataUrl.split(',')[1], 'base64');
          doc.image(qrBuffer, 206, 200, { width: 200, height: 200 });
        } catch (error) {
          console.error('QR Code generation error:', error);
        }
      }

      // Additional info
      let yPos = qrEnabled && mode === 'ticketing' ? 420 : 220;

      if (ticket.classroom) {
        doc.fontSize(12)
          .text(`Room: ${ticket.classroom}`, 50, yPos, { width: 512, align: 'center' });
        yPos += 20;
      }

      // Footer
      doc.fontSize(10)
        .fillColor('#666666')
        .text(`Ticket #${ticket.ticket_number}`, 50, 700, { width: 512, align: 'center' });
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

      // Name
      doc.fontSize(11)
        .font('Helvetica-Bold')
        .fillColor('#000000')
        .text(fullName, x + 10, y + 15, {
          width: labelWidth - 20,
          align: 'center'
        });

      let yPos = y + 32;

      // Mode-specific content
      if (mode === 'sales') {
        // Sales mode: show room + teacher
        if (attendee.classroom) {
          doc.fontSize(9)
            .font('Helvetica')
            .text(`Room ${attendee.classroom}`, x + 10, yPos, {
              width: labelWidth - 20,
              align: 'center'
            });
          yPos += 12;
        }
        if (attendee.teacher) {
          doc.fontSize(9)
            .text(attendee.teacher, x + 10, yPos, {
              width: labelWidth - 20,
              align: 'center'
            });
          yPos += 12;
        }
        // Quantity (always 1 for labels)
        doc.fontSize(9)
          .text('Qty: 1', x + 10, yPos, {
            width: labelWidth - 20,
            align: 'center'
          });
      } else {
        // Ticketing mode: show event name and optional classroom
        if (attendee.classroom) {
          doc.fontSize(9)
            .font('Helvetica')
            .text(`Room ${attendee.classroom}`, x + 10, yPos, {
              width: labelWidth - 20,
              align: 'center'
            });
          yPos += 12;
        }
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
