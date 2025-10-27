const Database = require('better-sqlite3');
const path = require('path');
const { app } = require('electron');
const crypto = require('crypto');

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';

class EventDatabase {
  constructor() {
    const userDataPath = app.getPath('userData');
    const dbPath = path.join(userDataPath, 'pta_tickets.db');
    this.db = new Database(dbPath);
    this.db.pragma('journal_mode = WAL');
    this.db.pragma('foreign_keys = ON');
    this._migrate();
    this._backfillTicketCodes();
  }

  _migrate() {
    // Create settings table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
      )
    `);

    // Create attendees table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS attendees (
        attendee_id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        created_at REAL NOT NULL,
        classroom TEXT,
        teacher TEXT,
        address TEXT,
        email TEXT,
        phone TEXT,
        grade TEXT,
        notes TEXT
      )
    `);

    // Create tickets table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS tickets (
        ticket_number INTEGER PRIMARY KEY AUTOINCREMENT,
        attendee_id INTEGER NOT NULL,
        ticket_code TEXT UNIQUE,
        printed INTEGER DEFAULT 0,
        checked_in INTEGER DEFAULT 0,
        checked_in_at REAL,
        created_at REAL NOT NULL,
        FOREIGN KEY (attendee_id) REFERENCES attendees(attendee_id) ON DELETE CASCADE
      )
    `);

    // Create indexes
    this.db.exec(`
      CREATE INDEX IF NOT EXISTS idx_tickets_printed ON tickets(printed);
      CREATE INDEX IF NOT EXISTS idx_tickets_attendee ON tickets(attendee_id);
      CREATE INDEX IF NOT EXISTS idx_tickets_code ON tickets(ticket_code);
      CREATE INDEX IF NOT EXISTS idx_tickets_checked ON tickets(checked_in);
    `);

    // Initialize default settings
    this._initDefaultSettings();
  }

  _initDefaultSettings() {
    const defaults = {
      organization_name: 'My Organization',
      event_name: 'Event',
      event_code: 'EVT',
      ticket_color: '#ff7a00',
      qr_enabled: 'true',
      mode: 'ticketing',
      enabled_fields: JSON.stringify(['classroom']),
      label_fields: JSON.stringify(['classroom']),
      label_vertical_gap: '0.0',
      label_horizontal_gap: '0.0',
      label_top_margin: '0.5',
      label_left_margin: '0.1875',
      label_show_borders: 'false'
    };

    for (const [key, value] of Object.entries(defaults)) {
      const exists = this.db.prepare('SELECT 1 FROM settings WHERE key = ?').get(key);
      if (!exists) {
        this.db.prepare('INSERT INTO settings (key, value) VALUES (?, ?)').run(key, value);
      }
    }
  }

  _backfillTicketCodes() {
    const eventCode = this.getSetting('event_code') || 'EVT';
    const tickets = this.db.prepare('SELECT ticket_number FROM tickets WHERE ticket_code IS NULL').all();

    const update = this.db.prepare('UPDATE tickets SET ticket_code = ? WHERE ticket_number = ?');
    for (const ticket of tickets) {
      const code = this._generateTicketCode(eventCode);
      update.run(code, ticket.ticket_number);
    }
  }

  _generateTicketCode(eventCode = 'EVT', length = 6) {
    const prefix = eventCode.toUpperCase();
    const randomChars = Array.from({ length }, () =>
      ALPHABET[crypto.randomInt(ALPHABET.length)]
    ).join('');
    return `${prefix}-${randomChars}`;
  }

  _generateUniqueTicketCode(eventCode) {
    const maxRetries = 100;
    for (let i = 0; i < maxRetries; i++) {
      const code = this._generateTicketCode(eventCode);
      const exists = this.db.prepare('SELECT 1 FROM tickets WHERE ticket_code = ?').get(code);
      if (!exists) {
        return code;
      }
    }
    throw new Error('Failed to generate unique ticket code');
  }

  // Settings
  getSetting(key) {
    const row = this.db.prepare('SELECT value FROM settings WHERE key = ?').get(key);
    return row ? row.value : null;
  }

  setSetting(key, value) {
    this.db.prepare('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)').run(key, value);
  }

  getAllSettings() {
    const rows = this.db.prepare('SELECT key, value FROM settings').all();
    const settings = {};
    for (const row of rows) {
      settings[row.key] = row.value;
    }
    return settings;
  }

  // Attendees & Tickets
  createAttendeeWithTickets(firstName, lastName, quantity, customFields = {}) {
    const now = Date.now() / 1000;
    const eventCode = this.getSetting('event_code') || 'EVT';

    const attendeeId = this.db.prepare(`
      INSERT INTO attendees (first_name, last_name, created_at, classroom, teacher, address, email, phone, grade, notes)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      firstName,
      lastName,
      now,
      customFields.classroom || null,
      customFields.teacher || null,
      customFields.address || null,
      customFields.email || null,
      customFields.phone || null,
      customFields.grade || null,
      customFields.notes || null
    ).lastInsertRowid;

    const insertTicket = this.db.prepare(`
      INSERT INTO tickets (attendee_id, ticket_code, created_at)
      VALUES (?, ?, ?)
    `);

    const ticketCodes = [];
    for (let i = 0; i < quantity; i++) {
      const code = this._generateUniqueTicketCode(eventCode);
      insertTicket.run(attendeeId, code, now);
      ticketCodes.push(code);
    }

    return { attendeeId, ticketCodes };
  }

  listTickets() {
    return this.db.prepare(`
      SELECT
        t.ticket_number,
        t.ticket_code,
        a.first_name,
        a.last_name,
        t.printed,
        t.checked_in,
        t.checked_in_at,
        t.created_at,
        a.classroom,
        a.teacher,
        a.address,
        a.email,
        a.phone,
        a.grade,
        a.notes
      FROM tickets t
      JOIN attendees a ON t.attendee_id = a.attendee_id
      ORDER BY t.ticket_number DESC
    `).all();
  }

  getTicket(ticketNumber) {
    return this.db.prepare(`
      SELECT
        t.ticket_number,
        t.ticket_code,
        t.attendee_id,
        a.first_name,
        a.last_name,
        t.printed,
        t.checked_in,
        t.checked_in_at,
        t.created_at,
        a.classroom,
        a.teacher,
        a.address,
        a.email,
        a.phone,
        a.grade,
        a.notes
      FROM tickets t
      JOIN attendees a ON t.attendee_id = a.attendee_id
      WHERE t.ticket_number = ?
    `).get(ticketNumber);
  }

  updateTicket(ticketNumber, fields) {
    const ticket = this.getTicket(ticketNumber);
    if (!ticket) return false;

    this.db.prepare(`
      UPDATE attendees SET
        first_name = ?,
        last_name = ?,
        classroom = ?,
        teacher = ?,
        address = ?,
        email = ?,
        phone = ?,
        grade = ?,
        notes = ?
      WHERE attendee_id = ?
    `).run(
      fields.first_name || ticket.first_name,
      fields.last_name || ticket.last_name,
      fields.classroom !== undefined ? fields.classroom : ticket.classroom,
      fields.teacher !== undefined ? fields.teacher : ticket.teacher,
      fields.address !== undefined ? fields.address : ticket.address,
      fields.email !== undefined ? fields.email : ticket.email,
      fields.phone !== undefined ? fields.phone : ticket.phone,
      fields.grade !== undefined ? fields.grade : ticket.grade,
      fields.notes !== undefined ? fields.notes : ticket.notes,
      ticket.attendee_id
    );

    return true;
  }

  deleteTickets(ticketNumbers) {
    const deleteTicket = this.db.prepare('DELETE FROM tickets WHERE ticket_number = ?');
    const deleteOrphanAttendees = this.db.prepare(`
      DELETE FROM attendees
      WHERE attendee_id NOT IN (SELECT DISTINCT attendee_id FROM tickets)
    `);

    const transaction = this.db.transaction((numbers) => {
      for (const num of numbers) {
        deleteTicket.run(num);
      }
      deleteOrphanAttendees.run();
    });

    transaction(ticketNumbers);
  }

  markPrinted(ticketNumbers, printed = true) {
    const update = this.db.prepare('UPDATE tickets SET printed = ? WHERE ticket_number = ?');
    const value = printed ? 1 : 0;

    const transaction = this.db.transaction((numbers) => {
      for (const num of numbers) {
        update.run(value, num);
      }
    });

    transaction(ticketNumbers);
  }

  checkIn(identifier) {
    // Try as ticket_code first
    let ticket = this.db.prepare('SELECT * FROM tickets WHERE ticket_code = ?').get(identifier);

    // Try as ticket_number
    if (!ticket) {
      const num = parseInt(identifier, 10);
      if (!isNaN(num)) {
        ticket = this.db.prepare('SELECT * FROM tickets WHERE ticket_number = ?').get(num);
      }
    }

    if (!ticket) {
      return { status: 'not_found' };
    }

    if (ticket.checked_in) {
      return { status: 'already', timestamp: ticket.checked_in_at };
    }

    const now = Date.now() / 1000;
    this.db.prepare('UPDATE tickets SET checked_in = 1, checked_in_at = ? WHERE ticket_number = ?')
      .run(now, ticket.ticket_number);

    return { status: 'checked_in', timestamp: now };
  }

  getStats() {
    const total = this.db.prepare('SELECT COUNT(*) as count FROM tickets').get().count;
    const printed = this.db.prepare('SELECT COUNT(*) as count FROM tickets WHERE printed = 1').get().count;
    const checkedIn = this.db.prepare('SELECT COUNT(*) as count FROM tickets WHERE checked_in = 1').get().count;

    return {
      total,
      printed,
      unprinted: total - printed,
      checkedIn
    };
  }

  getOrderSummary() {
    const rows = this.db.prepare(`
      SELECT
        a.teacher,
        a.classroom,
        COUNT(*) as order_count,
        SUM(1) as total_quantity
      FROM tickets t
      JOIN attendees a ON t.attendee_id = a.attendee_id
      GROUP BY a.teacher, a.classroom
      ORDER BY a.teacher, a.classroom
    `).all();

    return rows;
  }

  getCheckedInTickets() {
    return this.db.prepare(`
      SELECT
        t.ticket_number,
        t.ticket_code,
        a.first_name,
        a.last_name,
        t.checked_in_at,
        a.classroom,
        a.teacher
      FROM tickets t
      JOIN attendees a ON t.attendee_id = a.attendee_id
      WHERE t.checked_in = 1
      ORDER BY t.checked_in_at DESC
    `).all();
  }

  close() {
    this.db.close();
  }
}

module.exports = EventDatabase;
