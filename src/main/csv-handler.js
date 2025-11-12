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

    // Normalize column names (case-insensitive, remove punctuation and extra spaces)
    const normalizedRows = rows.map(row => {
      const normalized = {};
      for (const [key, value] of Object.entries(row)) {
        // Remove apostrophes, quotes, and other punctuation, convert to lowercase, trim
        const cleanKey = key.toLowerCase().replace(/['"'`]/g, '').replace(/[^\w\s]/g, ' ').replace(/\s+/g, ' ').trim();
        normalized[cleanKey] = value;
      }
      return normalized;
    });

    // Detect columns (with flexible matching)
    const firstRow = normalizedRows[0];
    const hasQuantity = this._hasColumn(firstRow, ['quantity', 'qty', 'count', 'amount', 'number', 'num']);
    const hasStudentName = this._hasColumn(firstRow, ['students name', 'student name', 'student s name', 'name', 'full name', 'fullname', 'attendee', 'attendee name']);
    const hasFirstName = this._hasColumn(firstRow, ['first', 'first name', 'firstname', 'fname', 'given name']);
    const hasLastName = this._hasColumn(firstRow, ['last', 'last name', 'lastname', 'lname', 'surname', 'family name']);
    const hasClassroom = this._hasColumn(firstRow, ['classroom', 'room', 'class', 'homeroom']);
    const hasTeacher = this._hasColumn(firstRow, ['teacher', 'instructor', 'teacher name']);
    const hasAddress = this._hasColumn(firstRow, ['address', 'street', 'home address']);
    const hasEmail = this._hasColumn(firstRow, ['email', 'e mail', 'email address']);
    const hasPhone = this._hasColumn(firstRow, ['phone', 'telephone', 'phone number', 'contact', 'mobile']);
    const hasGrade = this._hasColumn(firstRow, ['grade', 'grade level', 'year']);

    for (const row of normalizedRows) {
      try {
        // Get quantity
        let quantity = 1;
        if (hasQuantity) {
          const qtyCol = this._findColumn(row, ['quantity', 'qty', 'count', 'amount', 'number', 'num']);
          quantity = parseInt(qtyCol, 10) || 1;
        }

        // Get name
        let firstName = '';
        let lastName = '';

        if (hasStudentName) {
          const fullName = this._findColumn(row, ['students name', 'student name', 'student s name', 'name', 'full name', 'fullname', 'attendee', 'attendee name']);
          [firstName, lastName] = this._splitName(fullName);
        } else if (hasFirstName && hasLastName) {
          firstName = this._findColumn(row, ['first', 'first name', 'firstname', 'fname', 'given name']);
          lastName = this._findColumn(row, ['last', 'last name', 'lastname', 'lname', 'surname', 'family name']);
        } else {
          results.skipped++;
          results.errors.push(`Row skipped: No name columns found. Available columns: ${Object.keys(row).join(', ')}`);
          continue;
        }

        if (!firstName && !lastName) {
          results.skipped++;
          results.errors.push(`Row skipped: Name fields are empty. Row data: ${JSON.stringify(row)}`);
          continue;
        }

        // Get custom fields
        const customFields = {};
        if (hasClassroom) {
          customFields.classroom = this._findColumn(row, ['classroom', 'room', 'class', 'homeroom']);
        }
        if (hasTeacher) {
          const teacherValue = this._findColumn(row, ['teacher', 'instructor', 'teacher name']);
          customFields.teacher = teacherValue;

          // Try to extract grade and room from teacher field if it contains them
          // Handles formats like "K 101", "1st 205", "4th-Dodd 132", "K-Ehmann 101", etc.
          if (teacherValue && !hasGrade) {
            // Try format: "K-TeacherName 101" or "4th-TeacherName 132"
            let gradeMatch = teacherValue.match(/^(K|[0-9]{1,2}(?:st|nd|rd|th)?)\s*-?\s*[A-Za-z]+\s+(\d+)/i);
            if (!gradeMatch) {
              // Try simpler format: "K 101" or "1st 205"
              gradeMatch = teacherValue.match(/^(K|[0-9]{1,2}(?:st|nd|rd|th)?)\s+(\d+)/i);
            }
            if (gradeMatch) {
              customFields.grade = gradeMatch[1]; // Grade (K, 1st, 2nd, etc.)
              if (!hasClassroom) {
                customFields.classroom = gradeMatch[2]; // Room number
              }
            }
          }
        }
        if (hasAddress) {
          customFields.address = this._findColumn(row, ['address', 'street', 'home address']);
        }
        if (hasEmail) {
          customFields.email = this._findColumn(row, ['email', 'e mail', 'email address']);
        }
        if (hasPhone) {
          customFields.phone = this._findColumn(row, ['phone', 'telephone', 'phone number', 'contact', 'mobile']);
        }
        if (hasGrade) {
          customFields.grade = this._findColumn(row, ['grade', 'grade level', 'year']);
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
