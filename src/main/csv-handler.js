const fs = require('fs');
const csv = require('csv-parser');
const { stringify } = require('csv-stringify/sync');
const XLSX = require('xlsx');

class CSVHandler {
  async importFile(filePath, database) {
    const ext = filePath.toLowerCase();
    let rows = [];

    if (ext.endsWith('.csv')) {
      rows = await this._readCSV(filePath);
    } else if (ext.endsWith('.xlsx') || ext.endsWith('.xls')) {
      rows = this._readExcel(filePath);
    } else {
      throw new Error('Unsupported file format. Use CSV or Excel files.');
    }

    return this._processImportRows(rows, database);
  }

  _readCSV(filePath) {
    return new Promise((resolve, reject) => {
      const rows = [];
      fs.createReadStream(filePath)
        .pipe(csv())
        .on('data', (row) => rows.push(row))
        .on('end', () => resolve(rows))
        .on('error', reject);
    });
  }

  _readExcel(filePath) {
    const workbook = XLSX.readFile(filePath);
    const sheetName = workbook.SheetNames[0];
    const sheet = workbook.Sheets[sheetName];
    return XLSX.utils.sheet_to_json(sheet);
  }

  _processImportRows(rows, database) {
    if (rows.length === 0) {
      throw new Error('No data found in file');
    }

    const results = {
      imported: 0,
      skipped: 0,
      errors: []
    };

    // Normalize column names (case-insensitive)
    const normalizedRows = rows.map(row => {
      const normalized = {};
      for (const [key, value] of Object.entries(row)) {
        normalized[key.toLowerCase().trim()] = value;
      }
      return normalized;
    });

    // Detect columns
    const firstRow = normalizedRows[0];
    const hasQuantity = this._hasColumn(firstRow, ['quantity', 'qty']);
    const hasStudentName = this._hasColumn(firstRow, ['student name', 'name', 'full name']);
    const hasFirstName = this._hasColumn(firstRow, ['first', 'first name', 'firstname']);
    const hasLastName = this._hasColumn(firstRow, ['last', 'last name', 'lastname']);
    const hasClassroom = this._hasColumn(firstRow, ['classroom', 'room', 'class']);
    const hasTeacher = this._hasColumn(firstRow, ['teacher']);
    const hasAddress = this._hasColumn(firstRow, ['address']);
    const hasEmail = this._hasColumn(firstRow, ['email']);
    const hasPhone = this._hasColumn(firstRow, ['phone']);
    const hasGrade = this._hasColumn(firstRow, ['grade']);

    for (const row of normalizedRows) {
      try {
        // Get quantity
        let quantity = 1;
        if (hasQuantity) {
          const qtyCol = this._findColumn(row, ['quantity', 'qty']);
          quantity = parseInt(qtyCol, 10) || 1;
        }

        // Get name
        let firstName = '';
        let lastName = '';

        if (hasStudentName) {
          const fullName = this._findColumn(row, ['student name', 'name', 'full name']);
          [firstName, lastName] = this._splitName(fullName);
        } else if (hasFirstName && hasLastName) {
          firstName = this._findColumn(row, ['first', 'first name', 'firstname']);
          lastName = this._findColumn(row, ['last', 'last name', 'lastname']);
        } else {
          results.skipped++;
          continue;
        }

        if (!firstName && !lastName) {
          results.skipped++;
          continue;
        }

        // Get custom fields
        const customFields = {};
        if (hasClassroom) {
          customFields.classroom = this._findColumn(row, ['classroom', 'room', 'class']);
        }
        if (hasTeacher) {
          customFields.teacher = this._findColumn(row, ['teacher']);
        }
        if (hasAddress) {
          customFields.address = this._findColumn(row, ['address']);
        }
        if (hasEmail) {
          customFields.email = this._findColumn(row, ['email']);
        }
        if (hasPhone) {
          customFields.phone = this._findColumn(row, ['phone']);
        }
        if (hasGrade) {
          customFields.grade = this._findColumn(row, ['grade']);
        }

        // Create attendee with tickets
        database.createAttendeeWithTickets(firstName, lastName, quantity, customFields);
        results.imported++;
      } catch (error) {
        results.errors.push(`Row error: ${error.message}`);
      }
    }

    return results;
  }

  _hasColumn(row, names) {
    return names.some(name => row.hasOwnProperty(name));
  }

  _findColumn(row, names) {
    for (const name of names) {
      if (row.hasOwnProperty(name)) {
        return row[name];
      }
    }
    return '';
  }

  _splitName(fullName) {
    const parts = fullName.trim().split(/\s+/);
    if (parts.length === 0) return ['', ''];
    if (parts.length === 1) return ['', parts[0]];

    const firstName = parts[0];
    const lastName = parts.slice(1).join(' ');
    return [firstName, lastName];
  }

  exportTickets(tickets, outputPath) {
    const csvData = tickets.map(t => ({
      'Ticket Number': t.ticket_number,
      'Ticket Code': t.ticket_code,
      'First Name': t.first_name,
      'Last Name': t.last_name,
      'Classroom': t.classroom || '',
      'Teacher': t.teacher || '',
      'Address': t.address || '',
      'Email': t.email || '',
      'Phone': t.phone || '',
      'Grade': t.grade || '',
      'Notes': t.notes || '',
      'Printed': t.printed ? 'Yes' : 'No',
      'Checked In': t.checked_in ? 'Yes' : 'No',
      'Checked In At': t.checked_in_at ? new Date(t.checked_in_at * 1000).toLocaleString() : ''
    }));

    const csv = stringify(csvData, { header: true });
    fs.writeFileSync(outputPath, csv);
    return outputPath;
  }

  exportCheckedIn(tickets, outputPath) {
    const csvData = tickets.map(t => ({
      'Ticket Number': t.ticket_number,
      'Ticket Code': t.ticket_code,
      'First Name': t.first_name,
      'Last Name': t.last_name,
      'Classroom': t.classroom || '',
      'Teacher': t.teacher || '',
      'Checked In At': new Date(t.checked_in_at * 1000).toLocaleString()
    }));

    const csv = stringify(csvData, { header: true });
    fs.writeFileSync(outputPath, csv);
    return outputPath;
  }

  exportOrderSummary(summary, outputPath) {
    const csvData = summary.map(s => ({
      'Teacher': s.teacher || '',
      'Classroom': s.classroom || '',
      'Order Count': s.order_count,
      'Total Quantity': s.total_quantity
    }));

    const csv = stringify(csvData, { header: true });
    fs.writeFileSync(outputPath, csv);
    return outputPath;
  }
}

module.exports = CSVHandler;
