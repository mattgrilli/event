#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Event & Sales Manager — Dark-Mode-First, High-Contrast (Full Build + Sales Mode)
---------------------------------------------------------------------------------

A professional event management system for ticketing and product sales.
Perfect for schools, PTAs, clubs, fundraisers, and community organizations.

Key features:
- Event Ticketing Mode: Generate tickets with QR codes, check-in system, attendance tracking
- Product Sales Mode: Manage orders, print distribution labels, export order summaries
- Professional label printing (Avery 5160 compatible)
- CSV/Excel import and export
- Dark mode interface with customizable accent colors
- Backward compatible with existing databases

Technical improvements:
- DB: backfills missing ticket_code on legacy rows; adds index on checked_in
- Ticket codes: unbiased secure generation; same short format (EVT-XXXXXX)
- Scanner: accepts only numeric or PREFIX-BASE36 forms; less false positives
- Exports: include Classroom and Teacher columns
- Labels: de-duplicate by (name, classroom), not just name
- Check-in: distinct feedback for "checked now" vs "already checked", with time

Drop-in: replace your current file. Uses your existing SQLite DB.
"""

from __future__ import annotations
import csv
import json
import platform
import re
import secrets
import sqlite3
import string
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Iterable, Optional, Dict

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser

# Platform-specific imports
if platform.system() == 'Windows':
    try:
        import winsound  # type: ignore
    except ImportError:
        winsound = None
else:
    winsound = None

# ---- Optional imports (guarded) ----
HAS_PANDAS = False
try:
    import pandas as pd  # type: ignore
    HAS_PANDAS = True
except (ImportError, ModuleNotFoundError):
    pass

HAS_RL = False
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas as rl_canvas
    HAS_RL = True
except (ImportError, ModuleNotFoundError):
    pass

HAS_QR = False
try:
    import qrcode  # type: ignore
    from PIL import Image
    HAS_QR = True
except (ImportError, ModuleNotFoundError):
    pass

APP_TITLE = "Event & Sales Manager"
DB_NAME = "pta_tickets.db"
MAX_CODE_RETRIES = 100  # Prevent infinite loops in ticket code generation

ALPHABET = string.ascii_uppercase + string.digits  # base36-like
# Accept either legacy numeric, or PREFIX-XXXX (2–6 letter prefix, 4–10 base36 payload)
SCAN_PATTERN = re.compile(r'(?:\d+|[A-Z]{2,6}-[A-Z0-9]{4,10})$')


def generate_ticket_code(event_code: str = 'EVT', length_rand: int = 6) -> str:
    """
    Return something like EVT-K7R4Z9
    event_code: human event short code (uppercase, 2-6 chars)
    length_rand: number of random chars appended (keeps code short)
    """
    prefix = event_code.upper()
    rand_chars = ''.join(secrets.choice(ALPHABET) for _ in range(length_rand))
    return f"{prefix}-{rand_chars}"


# ============ Data Layer ============
class Database:
    def __init__(self, path: Path):
        self.conn = sqlite3.connect(str(path))
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.execute("PRAGMA journal_mode = WAL;")
        self._migrate()

    def _get_table_columns(self, table_name: str) -> List[str]:
        """Get list of column names for a table."""
        cur = self.conn.cursor()
        cur.execute(f"PRAGMA table_info({table_name})")
        return [r[1] for r in cur.fetchall()]

    def _migrate(self) -> None:
        """
        Initialize database schema and perform migrations.
        Creates tables, indexes, and adds missing columns for backward compatibility.
        """
        c = self.conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS attendees (
                attendee_id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name  TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Include ticket_code in fresh schema; if table already exists without it, we'll ALTER below.
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_number INTEGER PRIMARY KEY AUTOINCREMENT,
                attendee_id INTEGER NOT NULL,
                ticket_code TEXT UNIQUE,
                printed INTEGER NOT NULL DEFAULT 0,
                checked_in INTEGER NOT NULL DEFAULT 0,
                checked_in_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(attendee_id) REFERENCES attendees(attendee_id) ON DELETE CASCADE
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_tickets_printed ON tickets(printed);")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tickets_attendee ON tickets(attendee_id);")
        self.conn.commit()

        # --- Ensure ticket_code column exists BEFORE creating its index (fixes OperationalError on old DBs) ---
        try:
            cols = self._get_table_columns('tickets')
            if 'ticket_code' not in cols:
                c.execute("ALTER TABLE tickets ADD COLUMN ticket_code TEXT")
                self.conn.commit()
        except sqlite3.OperationalError as e:
            print(f"Warning: Could not add ticket_code column: {e}")

        # Now it's safe to create the UNIQUE index on ticket_code
        try:
            self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tickets_code ON tickets(ticket_code)")
            self.conn.commit()
        except sqlite3.OperationalError as e:
            print(f"Warning: Could not create index on ticket_code: {e}")

        # --- Add classroom column to attendees if missing ---
        try:
            cols = self._get_table_columns('attendees')
            if 'classroom' not in cols:
                c.execute("ALTER TABLE attendees ADD COLUMN classroom TEXT")
                self.conn.commit()
        except sqlite3.OperationalError as e:
            print(f"Warning: Could not add classroom column: {e}")

        # --- Add teacher column to attendees if missing (NEW FOR SALES MODE) ---
        try:
            cols = self._get_table_columns('attendees')
            if 'teacher' not in cols:
                c.execute("ALTER TABLE attendees ADD COLUMN teacher TEXT")
                self.conn.commit()
        except sqlite3.OperationalError as e:
            print(f"Warning: Could not add teacher column: {e}")

        # --- Index for check-in filters/stats ---
        try:
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_checked ON tickets(checked_in)")
            self.conn.commit()
        except sqlite3.OperationalError as e:
            print(f"Warning: Could not create index on checked_in: {e}")

        # --- Backfill missing ticket_code values on legacy rows ---
        try:
            self._backfill_ticket_codes()
        except Exception as e:
            # Non-fatal; UI will still function
            print(f"Warning: Could not backfill ticket codes: {e}")

    def _backfill_ticket_codes(self) -> None:
        """
        Backfill ticket_code for legacy rows that don't have one.
        Uses the current event_code setting to generate codes.
        Max retries per ticket to prevent infinite loops.
        """
        cur = self.conn.cursor()
        evc = (self.get_setting('event_code', 'EVT') or 'EVT').strip().upper()
        cur.execute("SELECT ticket_number FROM tickets WHERE ticket_code IS NULL OR ticket_code=''")
        missing = [r[0] for r in cur.fetchall()]
        if not missing:
            return
        for tnum in missing:
            attempts = 0
            while attempts < MAX_CODE_RETRIES:
                try:
                    code = generate_ticket_code(evc)
                    cur.execute("UPDATE tickets SET ticket_code=? WHERE ticket_number=?", (code, tnum))
                    break
                except sqlite3.IntegrityError:
                    # Extremely unlikely collision; try again
                    attempts += 1
                    if attempts >= MAX_CODE_RETRIES:
                        # Log error but don't crash - this ticket will remain without a code
                        print(f"Warning: Could not generate unique code for ticket {tnum} after {MAX_CODE_RETRIES} attempts")
                        break
                    continue
        self.conn.commit()

    # Settings
    def get_setting(self, key: str, default: str = "") -> str:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))
        self.conn.commit()

    def get_label_settings(self) -> Dict[str, any]:
        """Get label printing settings with defaults matching Avery 5160 Word template."""
        return {
            'show_border': self.get_setting('label_show_border', '1') == '1',  # '1' for testing, '0' for production
            'vertical_gap': float(self.get_setting('label_vertical_gap', '0.0')),  # inches between rows
            'horizontal_gap': float(self.get_setting('label_horizontal_gap', '0.14')),  # inches between columns (updated from 0.125)
            'margin_top': float(self.get_setting('label_margin_top', '0.5')),  # top margin
            'margin_left': float(self.get_setting('label_margin_left', '0.15625')),  # left margin (updated from 0.1875 for 2.63" width)
        }
    
    def set_label_settings(self, settings: Dict[str, any]) -> None:
        """Save label printing settings."""
        self.set_setting('label_show_border', '1' if settings.get('show_border', True) else '0')
        self.set_setting('label_vertical_gap', str(settings.get('vertical_gap', 0.0)))
        self.set_setting('label_horizontal_gap', str(settings.get('horizontal_gap', 0.125)))
        self.set_setting('label_margin_top', str(settings.get('margin_top', 0.5)))
        self.set_setting('label_margin_left', str(settings.get('margin_left', 0.1875)))

    def get_enabled_fields(self) -> List[str]:
        """Get list of enabled custom fields from settings."""
        fields_json = self.get_setting('enabled_fields', '["classroom", "teacher"]')
        try:
            return json.loads(fields_json)
        except (json.JSONDecodeError, TypeError):
            return ["classroom", "teacher"]
    
    def set_enabled_fields(self, fields: List[str]) -> None:
        """Save list of enabled custom fields to settings."""
        self.set_setting('enabled_fields', json.dumps(fields))
    
    def get_label_fields(self) -> List[str]:
        """Get list of fields to show on labels."""
        fields_json = self.get_setting('label_fields', '["classroom", "teacher"]')
        try:
            return json.loads(fields_json)
        except (json.JSONDecodeError, TypeError):
            return ["classroom", "teacher"]
    
    def set_label_fields(self, fields: List[str]) -> None:
        """Save list of fields to show on labels."""
        self.set_setting('label_fields', json.dumps(fields))
    
    def ensure_field_columns(self, fields: List[str]) -> None:
        """Ensure all enabled custom field columns exist in attendees table."""
        # Validate field names to prevent SQL injection
        VALID_FIELD_PATTERN = re.compile(r'^[a-z_][a-z0-9_]*$', re.IGNORECASE)
        
        cur = self.conn.cursor()
        existing_cols = self._get_table_columns('attendees')
        
        for field in fields:
            # Validate field name is safe for SQL
            if not VALID_FIELD_PATTERN.match(field):
                print(f"Warning: Skipping invalid field name: {field}")
                continue
                
            if field not in existing_cols:
                try:
                    # Safe now after validation
                    cur.execute(f"ALTER TABLE attendees ADD COLUMN {field} TEXT")
                    self.conn.commit()
                except sqlite3.OperationalError as e:
                    print(f"Warning: Could not add column {field}: {e}")

    def get_unique_event_codes(self) -> List[str]:
        """Get list of unique event codes (ticket prefixes) from all tickets."""
        cur = self.conn.cursor()
        cur.execute("SELECT DISTINCT ticket_code FROM tickets WHERE ticket_code IS NOT NULL AND ticket_code != ''")
        codes = []
        for row in cur.fetchall():
            code = row[0]
            # Extract prefix (e.g., "EVT-K7R4Z9" -> "EVT")
            if '-' in code:
                prefix = code.split('-')[0]
                if prefix not in codes:
                    codes.append(prefix)
        return sorted(codes)

    # Attendees & Tickets
    def create_attendee_with_tickets(
        self, first: str, last: str, qty: int, event_code: Optional[str] = None, custom_fields: Optional[Dict[str, str]] = None
    ) -> List[str]:
        qty = max(1, int(qty))
        cur = self.conn.cursor()
        
        # Build dynamic INSERT with custom fields
        custom_fields = custom_fields or {}
        field_names = ['first_name', 'last_name'] + list(custom_fields.keys())
        field_values = [first, last] + list(custom_fields.values())
        placeholders = ','.join(['?'] * len(field_values))
        field_cols = ','.join(field_names)
        
        cur.execute(f"INSERT INTO attendees({field_cols}) VALUES({placeholders})", field_values)
        attendee_id = cur.lastrowid
        codes: List[str] = []
        event_code = (event_code or self.get_setting('event_code', '')).strip() or 'EVT'
        for _ in range(qty):
            code = generate_ticket_code(event_code)
            while True:
                try:
                    cur.execute("INSERT INTO tickets(attendee_id, ticket_code) VALUES(?,?)", (attendee_id, code))
                    codes.append(code)
                    break
                except sqlite3.IntegrityError:
                    code = generate_ticket_code(event_code)
        self.conn.commit()
        return codes

    def list_tickets(self, enabled_fields: Optional[List[str]] = None) -> List[Tuple]:
        """List all tickets with classroom and teacher fields (backward compatible)."""
        cur = self.conn.cursor()
        
        # Always return base columns + classroom + teacher for backward compatibility
        cur.execute("""
            SELECT t.ticket_number, t.ticket_code, a.first_name, a.last_name,
                   t.printed, t.checked_in, COALESCE(t.checked_in_at,''), t.created_at,
                   COALESCE(a.classroom, ''), COALESCE(a.teacher, '')
              FROM tickets t
              JOIN attendees a ON a.attendee_id = t.attendee_id
             ORDER BY t.ticket_number DESC
        """)
        return cur.fetchall()

    def delete_tickets(self, ticket_numbers: Iterable[int]) -> int:
        nums = list(ticket_numbers)
        if not nums:
            return 0
        q = ",".join(["?"] * len(nums))
        self.conn.execute(f"DELETE FROM tickets WHERE ticket_number IN ({q})", nums)
        self.conn.commit()
        return len(nums)

    def update_attendee_name_for_ticket(self, ticket_number: int, first: str, last: str, custom_fields: Optional[Dict[str, str]] = None) -> None:
        """Update attendee information for a given ticket."""
        cur = self.conn.cursor()
        cur.execute("SELECT attendee_id FROM tickets WHERE ticket_number=?", (ticket_number,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Ticket not found")
        
        attendee_id = row[0]
        custom_fields = custom_fields or {}
        
        # Build dynamic UPDATE
        updates = ['first_name=?', 'last_name=?']
        values = [first, last]
        
        for field, value in custom_fields.items():
            updates.append(f"{field}=?")
            values.append(value or '')
        
        values.append(attendee_id)
        update_sql = f"UPDATE attendees SET {', '.join(updates)} WHERE attendee_id=?"
        
        self.conn.execute(update_sql, values)
        self.conn.commit()

    def mark_printed(self, ticket_numbers: Iterable[int], value: int = 1) -> None:
        nums = list(ticket_numbers)
        if not nums:
            return
        q = ",".join(["?"] * len(nums))
        self.conn.execute(f"UPDATE tickets SET printed=? WHERE ticket_number IN ({q})", (value, *nums))
        self.conn.commit()

    def unprinted_ticket_numbers(self) -> List[int]:
        cur = self.conn.cursor()
        cur.execute("SELECT ticket_number FROM tickets WHERE printed=0 ORDER BY ticket_number")
        return [r[0] for r in cur.fetchall()]

    def stats(self) -> Tuple[int, int, int, int]:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*), SUM(printed), SUM(checked_in) FROM tickets")
        total, printed, checked_in = cur.fetchone()
        total = int(total or 0)
        printed = int(printed or 0)
        checked_in = int(checked_in or 0)
        return total, printed, total - printed, checked_in

    def check_in(self, ticket_identifier) -> Tuple[str, Optional[str]]:
        """
        Returns:
            ("checked_in", timestamp)  -> just checked in now
            ("already", timestamp)     -> was already checked in
            ("not_found", None)        -> no such ticket
        """
        cur = self.conn.cursor()
        # Accept int/string numeric or event-aware code
        if isinstance(ticket_identifier, int) or str(ticket_identifier).isdigit():
            cur.execute("SELECT checked_in, checked_in_at FROM tickets WHERE ticket_number=?", (int(ticket_identifier),))
            key = ("ticket_number", int(ticket_identifier))
        else:
            cur.execute("SELECT checked_in, checked_in_at FROM tickets WHERE ticket_code=?", (str(ticket_identifier),))
            key = ("ticket_code", str(ticket_identifier))
        row = cur.fetchone()
        if not row:
            return "not_found", None
        already = int(row[0]) == 1
        if already:
            return "already", row[1]
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cur.execute(f"UPDATE tickets SET checked_in=1, checked_in_at=? WHERE {key[0]}=?", (now, key[1]))
        self.conn.commit()
        return "checked_in", now

    def get_order_summary(self) -> List[Tuple[str, str, int]]:
        """
        For Product Sales mode: return [(teacher, classroom, total_qty), ...]
        Grouped by teacher and classroom.
        """
        cur = self.conn.cursor()
        
        # Check if teacher column exists
        cur.execute("PRAGMA table_info(attendees)")
        cols = [r[1] for r in cur.fetchall()]
        
        if 'teacher' not in cols:
            return []
        
        classroom_col = 'classroom' if 'classroom' in cols else "''"
        
        cur.execute(f"""
            SELECT a.teacher, a.{classroom_col}, COUNT(t.ticket_number) as qty
            FROM attendees a
            JOIN tickets t ON a.attendee_id = t.attendee_id
            WHERE a.teacher IS NOT NULL AND a.teacher != ''
            GROUP BY a.teacher, a.{classroom_col}
            ORDER BY a.teacher, a.{classroom_col}
        """)
        return cur.fetchall()


# ============ Ticket Rendering ============
class TicketRenderer:
    def __init__(self, db: Database):
        self.db = db
        self.org = db.get_setting('organization_name', 'Your Organization Name') or 'Your Organization Name'
        self.event = db.get_setting('event_name', 'TRUNK OR TREAT') or 'TRUNK OR TREAT'
        self.event_code = db.get_setting('event_code', 'EVT') or 'EVT'
        self.accent = db.get_setting('ticket_color', '#ff7a00') or '#ff7a00'
        self.qr_enabled = db.get_setting('qr_enabled', '1') == '1'
        self.mode = db.get_setting('mode', 'ticketing')  # NEW

    def generate_pdf(self, rows: List[Tuple], out_path: Path) -> None:
        if not HAS_RL:
            raise RuntimeError('reportlab not installed')
        from reportlab.lib.colors import HexColor
        from reportlab.lib.utils import ImageReader
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        c = rl_canvas.Canvas(str(out_path), pagesize=letter)
        page_w, page_h = letter
        tw, th = 3.5 * inch, 2.5 * inch
        margin, pad = 0.5 * inch, 0.2 * inch
        cols = max(1, int((page_w - 2 * margin) // (tw + pad)))
        x0, y = margin, page_h - margin - th
        col = 0
        qr_cache: Dict[str, Image.Image] = {}
        for tnum, tcode, first, last, printed, checked, checked_at, created, classroom, teacher in rows:
            x = x0 + col * (tw + pad)
            # border
            c.setLineWidth(3)
            c.setStrokeColor(HexColor(self.accent))
            c.roundRect(x, y, tw, th, 10, stroke=1, fill=0)
            # header & body
            c.setFont('Helvetica-Bold', 10); c.drawCentredString(x + tw / 2, y + th - 18, self.org)
            c.setFont('Helvetica-Bold', 12); c.drawCentredString(x + tw / 2, y + th - 36, self.event)
            c.setFont('Helvetica', 9); c.drawCentredString(x + tw / 2, y + th - 52, 'ACCESS TICKET')
            c.setFont('Helvetica-Bold', 22); c.drawCentredString(x + tw / 2, y + th / 2 + 2, tcode or f"{self.event_code}-??????")

            # QR (optional) — encodes the public ticket_code, positioned to not overlap name
            if self.qr_enabled and HAS_QR and (tcode or "") and self.mode == 'ticketing':
                if tcode not in qr_cache:
                    q = qrcode.QRCode(border=0, box_size=2)
                    q.add_data(tcode)
                    q.make(fit=True)
                    img = q.make_image(fill_color="black", back_color="white").convert("RGB")
                    qr_cache[tcode] = img
                import io
                target = 0.9 * inch
                bio = io.BytesIO()
                qr_cache[tcode].resize((int(target), int(target))).save(bio, format="PNG")
                bio.seek(0)
                ir = ImageReader(bio)
                # Position QR in top-right corner, well above the name at bottom
                c.drawImage(ir, x + tw - target - 10, y + th - target - 15, width=target, height=target, preserveAspectRatio=True, mask="auto")

            # Name at bottom, no overlap with QR
            c.setFont('Helvetica-Oblique', 9); c.drawCentredString(x + tw / 2, y + 15, f"Registered: {first} {last}")
            col += 1
            if col >= cols:
                col = 0
                y -= th + pad
                if y < margin:
                    c.showPage()
                    y = page_h - margin - th
        c.save()

    def generate_html(self, rows: List[Tuple], out_path: Path) -> None:
        a = self.accent
        html = ["<!DOCTYPE html>", "<html><head><meta charset='utf-8'>",
                f"<title>{self.event} Tickets</title>",
                "<style>@page{margin:0.5in}body{font-family:system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;margin:0;padding:20px;background:#111418;color:#eaeff4}"
                ".t{width:3.5in;height:2.5in;border:4px solid "+a+";border-radius:12px;padding:16px;margin:8px;display:inline-block;page-break-inside:avoid;position:relative;background:#0f1216}"
                ".h1{font-weight:700;text-align:center;font-size:12px;color:"+a+"}.h2{font-weight:700;text-align:center;font-size:14px;margin-top:2px}.nr{font-weight:800;text-align:center;font-size:22px;margin:10px 0}.nm{font-style:italic;text-align:center;font-size:11px;color:#c9d5df}.lbl{font-size:10px;text-align:center;color:#9fb0bf}</style>",
                "</head><body>"]
        for tnum, tcode, first, last, printed, checked, checked_at, created, classroom, teacher in rows:
            html += ["<div class='t'>",
                     f"<div class='h1'>{self.org}</div>",
                     f"<div class='h2'>{self.event}</div>",
                     "<div class='lbl'>ACCESS TICKET</div>",
                     f"<div class='nr'>{tcode}</div>",
                     f"<div class='nm'>Registered: {first} {last}</div>",
                     "</div>"]
        html += ["</body></html>"]
        out_path.write_text("\n".join(html), encoding='utf-8')

    def generate_labels_pdf(self, rows: List[Tuple], out_path: Path) -> None:
        """
        rows should be: [(ticket_number, ticket_code, first, last, classroom, teacher), ...]
        (caller must extract relevant fields from list_tickets() result)
        Avery 5160: 3 cols x 10 rows.
        Mode-aware: In sales mode, show Name, Room-Teacher, Qty (no QR).
        """
        if not HAS_RL:
            raise RuntimeError('ReportLab not installed. pip install reportlab')
        from reportlab.lib.colors import HexColor
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch

        c = rl_canvas.Canvas(str(out_path), pagesize=letter)
        w, h = letter

        # Get label settings
        label_settings = self.db.get_label_settings()
        show_border = label_settings['show_border']
        gap_y = label_settings['vertical_gap'] * inch
        gap_x = label_settings['horizontal_gap'] * inch
        margin_y = label_settings['margin_top'] * inch
        margin_x = label_settings['margin_left'] * inch

        # Avery 5160 official dimensions from Word template: 3 cols x 10 rows per page
        # Official specs: Width 2.63", Height 1" (not 2.625" - that was approximation)
        label_w, label_h = 2.63*inch, 1*inch
        cols_per_page, rows_per_page = 3, 10

        def draw_label(x_pos, y_pos, tnum, tcode, first, last, classroom, teacher):
            """Draw one label at (x_pos, y_pos)."""
            # Border - optional, for testing alignment
            if show_border:
                c.setStrokeColorRGB(0.8, 0.8, 0.8)  # light gray for testing
                c.setLineWidth(0.5)
                c.setDash(1, 2)  # dotted line
                c.rect(x_pos, y_pos, label_w, label_h)
                c.setDash()  # reset to solid

            # Name
            c.setFillColorRGB(0,0,0)
            c.setFont('Helvetica-Bold', 11)
            name = f"{first} {last}".strip()
            c.drawString(x_pos+0.15*inch, y_pos+label_h-0.25*inch, name)

            if self.mode == 'sales':
                # Product Sales Mode: Show Room-Teacher and Qty
                c.setFont('Helvetica', 9)
                room_teacher = ''
                if classroom and teacher:
                    room_teacher = f"Room {classroom} - {teacher}"
                elif classroom:
                    room_teacher = f"Room {classroom}"
                elif teacher:
                    room_teacher = teacher
                
                if room_teacher:
                    c.drawString(x_pos+0.15*inch, y_pos+label_h-0.45*inch, room_teacher)
                
                # Show quantity
                c.setFont('Helvetica', 8)
                c.drawString(x_pos+0.15*inch, y_pos+label_h-0.65*inch, "Qty: 1")
                
            else:
                # Event Ticketing Mode: Show Room and Event
                c.setFont('Helvetica', 9)
                if classroom:
                    c.drawString(x_pos+0.15*inch, y_pos+label_h-0.45*inch, f"Room {classroom}")

                c.setFont('Helvetica-Bold', 9)
                c.setFillColor(HexColor(self.accent))
                c.drawString(x_pos+0.15*inch, y_pos+0.15*inch, self.event)

                # QR code (ticketing only)
                if self.qr_enabled and HAS_QR and tcode:
                    try:
                        qr = qrcode.QRCode(box_size=10, border=1)
                        qr.add_data(tcode)
                        qr.make(fit=True)
                        img = qr.make_image(fill_color='black', back_color='white')
                        tmp = Path(f'/tmp/qr_{tnum}.png')
                        img.save(str(tmp))
                        qr_size = 0.6*inch
                        c.drawImage(str(tmp), x_pos+label_w-qr_size-0.1*inch,
                                   y_pos+0.15*inch, width=qr_size, height=qr_size)
                        tmp.unlink()
                    except (OSError, IOError) as e:
                        print(f"Warning: Could not generate QR code for ticket {tnum}: {e}")

        idx = 0
        for (tnum, tcode, first, last, classroom, teacher) in rows:
            page_idx = idx // (cols_per_page*rows_per_page)
            label_idx = idx % (cols_per_page*rows_per_page)
            row_n = label_idx // cols_per_page
            col_n = label_idx % cols_per_page

            x = margin_x + col_n*(label_w + gap_x)
            y = h - margin_y - (row_n+1)*label_h - row_n*gap_y

            draw_label(x, y, tnum, tcode, first, last, classroom, teacher)
            idx += 1

            if (idx % (cols_per_page*rows_per_page)) == 0 and idx < len(rows):
                c.showPage()

        c.save()


# ============ UI ============
class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1000x900")

        # Paths/DB/Renderer
        self.data_dir = Path.home() / 'Documents' / 'PTA_Tickets'
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database(self.data_dir / DB_NAME)
        self.renderer = TicketRenderer(self.db)

        # Get mode
        self.current_mode = self.db.get_setting('mode', 'ticketing')
        
        # Get enabled custom fields
        self.enabled_fields = self.db.get_enabled_fields()
        self.label_fields = self.db.get_label_fields()
        
        # Ensure all enabled field columns exist
        self.db.ensure_field_columns(self.enabled_fields)

        # Dark-mode-first palette & ttk theme
        self._init_theme()

        self._build_ui()
        self.refresh()

    def _init_theme(self):
        # Palette (dark-first, neutral colors except accent)
        self.bg_main = '#0f1216'     # app background
        self.bg_frame = '#151a21'    # frames/cards
        self.fg_text = '#eaeff4'     # primary text
        self.fg_muted = '#b6c2cf'    # secondary text
        self.accent = self.db.get_setting('ticket_color', '#ff7a00') or '#ff7a00'  # only bright color
        self.btn_secondary = '#27313d'
        self.btn_secondary_active = '#2f3b49'
        self.danger = '#d83a3a'
        self.danger_active = '#a62828'
        self.selection_bg = '#22303c'

        # Tk defaults for consistent colors
        self.root.configure(bg=self.bg_main)
        self.root.option_add('*Background', self.bg_main)
        self.root.option_add('*Foreground', self.fg_text)
        self.root.option_add('*Label.background', self.bg_main)
        self.root.option_add('*Label.foreground', self.fg_text)
        self.root.option_add('*Labelframe.background', self.bg_frame)
        self.root.option_add('*Labelframe.foreground', self.fg_text)
        self.root.option_add('*Entry.background', '#1c232d')
        self.root.option_add('*Entry.foreground', self.fg_text)
        self.root.option_add('*Entry.insertBackground', self.fg_text)
        self.root.option_add('*Button.background', self.btn_secondary)
        self.root.option_add('*Button.foreground', self.fg_text)
        self.root.option_add('*Button.activeBackground', self.btn_secondary_active)
        self.root.option_add('*Button.activeforeground', self.fg_text)
        self.root.option_add('*Button.highlightThickness', 0)
        self.root.option_add('*Button.borderWidth', 1)

        # TTK styling
        style = ttk.Style()

        # Use native theme on Windows, our custom theme elsewhere
        try:
            if platform.system() == 'Windows':
                try:
                    style.theme_use('vista')  # Modern Windows look
                except tk.TclError:
                    style.theme_use('winnative')  # Fallback
                style.configure('Treeview', rowheight=24)
                style.map('Treeview', background=[('selected', self.selection_bg)],
                          foreground=[('selected', '#ffffff')])
            else:
                try:
                    style.theme_use('clam')
                except tk.TclError:
                    pass
                style.configure('Treeview', background=self.bg_frame, fieldbackground=self.bg_frame,
                                foreground=self.fg_text, rowheight=24)
                style.map('Treeview', background=[('selected', self.selection_bg)], foreground=[('selected', '#ffffff')])
                try:
                    style.configure('Treeview.Heading', background='#1c232d', foreground=self.fg_text, relief='flat')
                    style.map('Treeview.Heading', background=[('active', self.selection_bg)])
                except tk.TclError:
                    pass
                style.configure('TNotebook', background=self.bg_main, borderwidth=0)
                style.configure('TNotebook.Tab', background='#1c232d', foreground=self.fg_text)
                style.map('TNotebook.Tab', background=[('selected', self.bg_frame)])
        except Exception as e:
            print(f"Warning: Could not configure theme: {e}")

    def _build_ui(self):
        # Header
        self.header_frame = tk.Frame(self.root, bg=self.accent, height=64)
        self.header_frame.pack(fill='x')
        
        # Header with title and mode indicator
        header_content = tk.Frame(self.header_frame, bg=self.accent)
        header_content.pack(pady=12)
        
        self.header_label = tk.Label(header_content, text='Event & Sales Manager', bg=self.accent, fg='#0f1216', font=('Arial', 20, 'bold'))
        self.header_label.pack(side='left', padx=(0, 15))
        
        # Mode indicator badge
        mode_text = "🎟️ Ticketing Mode" if self.current_mode == 'ticketing' else "📦 Sales Mode"
        self.mode_indicator = tk.Label(header_content, text=mode_text, bg='#0f1216', fg=self.fg_text, 
                                       font=('Arial', 11, 'bold'), padx=12, pady=4, relief='flat')
        self.mode_indicator.pack(side='left')

        # Tabs
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill='both', expand=True, padx=10, pady=10)
        self.tab_manage = tk.Frame(self.nb, bg=self.bg_main)
        self.tab_labels = tk.Frame(self.nb, bg=self.bg_main)
        self.tab_checkin = tk.Frame(self.nb, bg=self.bg_main)
        self.tab_settings = tk.Frame(self.nb, bg=self.bg_main)
        self.tab_help = tk.Frame(self.nb, bg=self.bg_main)
        self.tab_about = tk.Frame(self.nb, bg=self.bg_main)
        
        self.nb.add(self.tab_manage, text='Manage')
        self.nb.add(self.tab_labels, text='Labels')
        # Only add check-in tab in ticketing mode
        if self.current_mode == 'ticketing':
            self.nb.add(self.tab_checkin, text='Check-In')
        self.nb.add(self.tab_settings, text='Settings')
        self.nb.add(self.tab_help, text='Help')
        self.nb.add(self.tab_about, text='About')

        self._build_manage_tab()
        self._build_labels_tab()
        self._build_checkin_tab()
        self._build_settings_tab()
        self._build_help_tab()
        self._build_about_tab()

        # Footer stats
        self.stats_lbl = tk.Label(self.root, text='', bg=self.bg_main, fg=self.fg_text, font=('Arial', 11, 'bold'))
        self.stats_lbl.pack(pady=(0, 8))

    # ---- Manage Tab ----
    def _build_manage_tab(self):
        frm = self.tab_manage
        lf = tk.LabelFrame(frm, text='Register Participant', bg=self.bg_frame, fg=self.fg_text)
        lf.pack(fill='x', padx=8, pady=8)
        
        tk.Label(lf, text='First Name', bg=self.bg_frame, fg=self.fg_text).grid(row=0, column=0, padx=8, pady=6, sticky='w')
        tk.Label(lf, text='Last Name',  bg=self.bg_frame, fg=self.fg_text).grid(row=1, column=0, padx=8, pady=6, sticky='w')
        tk.Label(lf, text='Classroom (optional)',  bg=self.bg_frame, fg=self.fg_text).grid(row=2, column=0, padx=8, pady=6, sticky='w')
        
        self.ent_first = tk.Entry(lf, width=24)
        self.ent_last = tk.Entry(lf, width=24)
        self.ent_classroom = tk.Entry(lf, width=12)
        self.ent_first.grid(row=0, column=1, padx=8, pady=6)
        self.ent_last.grid(row=1, column=1, padx=8, pady=6)
        self.ent_classroom.grid(row=2, column=1, padx=8, pady=6, sticky='w')
        
        # Teacher field - only show in sales mode
        current_row = 3
        if self.current_mode == 'sales':
            self.teacher_label = tk.Label(lf, text='Teacher (optional)',  bg=self.bg_frame, fg=self.fg_text)
            self.teacher_label.grid(row=current_row, column=0, padx=8, pady=6, sticky='w')
            self.ent_teacher = tk.Entry(lf, width=24)
            self.ent_teacher.grid(row=current_row, column=1, padx=8, pady=6)
            current_row += 1
        else:
            self.ent_teacher = tk.Entry(lf, width=24)  # Create but don't grid
        
        tk.Label(lf, text='Ticket Qty',  bg=self.bg_frame, fg=self.fg_text).grid(row=current_row, column=0, padx=8, pady=6, sticky='w')
        self.ent_qty = tk.Spinbox(lf, from_=1, to=20, width=6)
        self.ent_qty.grid(row=current_row, column=1, padx=8, pady=6, sticky='w')
        current_row += 1

        btns = tk.Frame(lf, bg=self.bg_frame); btns.grid(row=current_row, column=0, columnspan=2, pady=8)
        # Primary (accent) - dark text for high contrast
        tk.Button(btns, text='Generate', command=self.on_generate,
                  bg=self.accent, fg='#0f1216', activebackground=self.selection_bg, activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(side='left', padx=4)
        # Secondary - light gray with black text
        tk.Button(btns, text='Import CSV/Excel', command=self.on_import,
                  bg='#c9d5df', fg='#0f1216', activebackground='#b0bec8', activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(side='left', padx=4)
        tk.Button(btns, text='Export CSV', command=self.on_export,
                  bg='#c9d5df', fg='#0f1216', activebackground='#b0bec8', activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(side='left', padx=4)
        
        # Add Export Order Summary button ONLY in sales mode
        if self.current_mode == 'sales':
            tk.Button(btns, text='Export Order Summary', command=self.on_export_order_summary,
                      bg='#c9d5df', fg='#0f1216', activebackground='#b0bec8', activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(side='left', padx=4)

        # Table with dynamic count in header
        self.manage_table_frame = tk.LabelFrame(frm, text='Tickets (0)', bg=self.bg_frame, fg=self.fg_text)
        self.manage_table_frame.pack(fill='both', expand=True, padx=8, pady=8)
        
        # Dynamic columns based on mode
        if self.current_mode == 'sales':
            cols = ('Ticket ID', 'First', 'Last', 'Room', 'Teacher', 'Printed', 'Created')
            widths = [120, 120, 120, 60, 120, 80, 140]
        else:
            cols = ('Ticket ID', 'First', 'Last', 'Room', 'Printed', 'Checked In', 'Checked At', 'Created')
            widths = [120, 120, 120, 60, 80, 90, 140, 140]
            
        self.tree = ttk.Treeview(self.manage_table_frame, columns=cols, show='headings', height=14)
        for c in cols:
            self.tree.heading(c, text=c)
        for c, w in zip(cols, widths):
            self.tree.column(c, width=w, anchor='center')
        vsb = ttk.Scrollbar(self.manage_table_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        fbar = tk.Frame(frm, bg=self.bg_main); fbar.pack(fill='x', padx=8, pady=(0, 8))
        
        # Event filter dropdown
        tk.Label(fbar, text='Event:', bg=self.bg_main, fg=self.fg_text).pack(side='left', padx=(0,4))
        self.event_filter_var = tk.StringVar(value='All Events')
        self.event_filter_dropdown = ttk.Combobox(fbar, textvariable=self.event_filter_var, width=15, state='readonly')
        self.event_filter_dropdown.pack(side='left', padx=4)
        self.event_filter_dropdown.bind('<<ComboboxSelected>>', lambda e: self.apply_filter())
        
        # Text search filter
        tk.Label(fbar, text='Search:', bg=self.bg_main, fg=self.fg_text).pack(side='left', padx=(10,4))
        self.filter_var = tk.StringVar(); tk.Entry(fbar, textvariable=self.filter_var, width=28).pack(side='left', padx=4)
        self.filter_var.trace_add('write', lambda *_: self.apply_filter())
        
        # Edit and Delete - light backgrounds with black text
        tk.Button(fbar, text='Edit', command=self.on_edit,
                  bg='#c9d5df', fg='#0f1216', activebackground='#b0bec8', activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(side='left', padx=4)
        tk.Button(fbar, text='Delete', command=self.on_delete,
                  bg='#ffb3b3', fg='#0f1216', activebackground='#ff9999', activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(side='left', padx=4)
        
        # Ticket printing buttons - only show in ticketing mode
        if self.current_mode == 'ticketing':
            tk.Button(fbar, text='Print Tickets: Selected', command=self.on_print_selected,
                      bg=self.accent, fg='#0f1216', activebackground=self.selection_bg, activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(side='right', padx=4)
            tk.Button(fbar, text='Print Tickets: All Unprinted', command=self.on_print_all_unprinted,
                      bg=self.accent, fg='#0f1216', activebackground=self.selection_bg, activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(side='right', padx=4)

        # Click-to-sort
        def sort_by(col, reverse=False):
            data = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
            data.sort(key=lambda t: t[0], reverse=reverse)
            for idx, (_, k) in enumerate(data):
                self.tree.move(k, '', idx)
            self.tree.heading(col, command=lambda: sort_by(col, not reverse))
        for c in cols:
            self.tree.heading(c, command=lambda _c=c: sort_by(_c, False))

        # Double-click to edit
        self.tree.bind('<Double-Button-1>', lambda e: self.on_edit())

        # Map tree item -> internal ticket_number
        self._tree_num_by_item: Dict[str, int] = {}

    # ---- Labels Tab ----
    def _build_labels_tab(self):
        frm = self.tab_labels
        
        # Header info
        info_frame = tk.LabelFrame(frm, text='Label Printing', bg=self.bg_frame, fg=self.fg_text)
        info_frame.pack(fill='x', padx=8, pady=8)
        
        mode_info = "🎟️ Event labels with QR codes" if self.current_mode == 'ticketing' else "📦 Distribution labels with order details"
        tk.Label(info_frame, text=mode_info, bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10)).pack(padx=15, pady=10)
        
        # Print options
        options_frame = tk.LabelFrame(frm, text='Print Options', bg=self.bg_frame, fg=self.fg_text)
        options_frame.pack(fill='x', padx=8, pady=8)
        
        tk.Label(options_frame, text='Choose which tickets to print labels for:', bg=self.bg_frame, fg=self.fg_muted, font=('Arial', 9)).pack(padx=15, pady=(10,5), anchor='w')
        
        btn_frame = tk.Frame(options_frame, bg=self.bg_frame)
        btn_frame.pack(padx=15, pady=10)
        
        tk.Button(btn_frame, text='Print Labels: Selected Tickets', command=self.on_print_labels_selected,
                  bg=self.accent, fg='#0f1216', activebackground=self.selection_bg, activeforeground='#0f1216', 
                  takefocus=0, relief='flat', bd=0, highlightthickness=0, font=('Arial', 10, 'bold'), padx=20, pady=8).pack(side='left', padx=5)
        
        tk.Button(btn_frame, text='Print Labels: All Tickets', command=self.on_print_labels_all,
                  bg='#c9d5df', fg='#0f1216', activebackground='#b0bec8', activeforeground='#0f1216', 
                  takefocus=0, relief='flat', bd=0, highlightthickness=0, font=('Arial', 10), padx=20, pady=8).pack(side='left', padx=5)
        
        tk.Label(options_frame, text='💡 Labels are automatically de-duplicated (one per unique name + room)', 
                bg=self.bg_frame, fg=self.fg_muted, font=('Arial', 9, 'italic')).pack(padx=15, pady=(0,10), anchor='w')
        
        # Label format info
        format_frame = tk.LabelFrame(frm, text='Label Format', bg=self.bg_frame, fg=self.fg_text)
        format_frame.pack(fill='x', padx=8, pady=8)
        
        tk.Label(format_frame, text='Template: Avery 5160 (or compatible)', bg=self.bg_frame, fg=self.fg_text, 
                font=('Arial', 10, 'bold')).pack(padx=15, pady=(10,5), anchor='w')
        
        specs = """• 30 labels per sheet (3 columns × 10 rows)
• Label size: 2.63" × 1" (official Avery 5160 dimensions)
• Compatible brands: Avery, Office Depot, Staples, Amazon Basics"""
        
        tk.Label(format_frame, text=specs, bg=self.bg_frame, fg=self.fg_text, font=('Arial', 9), justify='left').pack(padx=30, pady=5, anchor='w')
        
        # What gets printed
        content_frame = tk.LabelFrame(frm, text='Label Content', bg=self.bg_frame, fg=self.fg_text)
        content_frame.pack(fill='x', padx=8, pady=8)
        
        if self.current_mode == 'ticketing':
            content_text = """Event Ticketing Mode:
• Student/Attendee name (bold)
• Room number
• Event name
• QR code (optional, based on settings)"""
        else:
            content_text = """Product Sales Mode:
• Student/Attendee name (bold)
• Room + Teacher (if available)
• Quantity: 1
• No QR codes"""
        
        tk.Label(content_frame, text=content_text, bg=self.bg_frame, fg=self.fg_text, font=('Arial', 9), justify='left').pack(padx=15, pady=10, anchor='w')
        
        # Selection table with dynamic count
        self.labels_table_frame = tk.LabelFrame(frm, text='Select Tickets for Labels (0)', bg=self.bg_frame, fg=self.fg_text)
        self.labels_table_frame.pack(fill='both', expand=True, padx=8, pady=8)
        
        # Build column list dynamically
        if self.current_mode == 'sales':
            cols = ('Ticket ID', 'First', 'Last', 'Room', 'Teacher')
            widths = [120, 150, 150, 80, 120]
        else:
            cols = ('Ticket ID', 'First', 'Last', 'Room')
            widths = [120, 150, 150, 80]
        
        self.labels_tree = ttk.Treeview(self.labels_table_frame, columns=cols, show='headings', height=12)
        for c in cols:
            self.labels_tree.heading(c, text=c)
        for c, w in zip(cols, widths):
            self.labels_tree.column(c, width=w, anchor='center')
        
        vsb = ttk.Scrollbar(self.labels_table_frame, orient='vertical', command=self.labels_tree.yview)
        self.labels_tree.configure(yscrollcommand=vsb.set)
        self.labels_tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        vsb.pack(side='right', fill='y', pady=5)
        
        # Filter for labels table
        filter_frame = tk.Frame(frm, bg=self.bg_main)
        filter_frame.pack(fill='x', padx=8, pady=(0, 8))
        tk.Label(filter_frame, text='Filter:', bg=self.bg_main, fg=self.fg_text).pack(side='left', padx=5)
        self.labels_filter_var = tk.StringVar()
        tk.Entry(filter_frame, textvariable=self.labels_filter_var, width=32).pack(side='left', padx=5)
        self.labels_filter_var.trace_add('write', lambda *_: self.apply_labels_filter())
        
        # Event code filter toggle (shared with Manage tab)
        
        tk.Label(filter_frame, text='💡 Tip: Use Ctrl+Click or Shift+Click to select multiple tickets', 
                bg=self.bg_main, fg=self.fg_muted, font=('Arial', 9, 'italic')).pack(side='right', padx=5)
        
        # Double-click to edit (from labels tab)
        self.labels_tree.bind('<Double-Button-1>', lambda e: self.on_edit_from_labels())
        
        # Map for labels tree
        self._labels_tree_num_by_item: Dict[str, int] = {}

    # ---- Check-In Tab ----
    def _build_checkin_tab(self):
        frm = self.tab_checkin
        box = tk.LabelFrame(frm, text='Scan / Enter Ticket ID', bg=self.bg_frame, fg=self.fg_text)
        box.pack(padx=8, pady=12, fill='x')
        self.checkin_var = tk.StringVar()
        ent = tk.Entry(box, textvariable=self.checkin_var, font=('Arial', 16), width=18)
        ent.pack(padx=8, pady=10); ent.focus_set()
        ent.bind('<Return>', lambda ev: self.on_checkin())
        tk.Button(box, text='Check In', command=self.on_checkin,
                  bg=self.accent, fg='#0f1216', activebackground=self.selection_bg, activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(pady=6)
        tk.Label(box, text='Example: EVT-K7R4Z9  •  Legacy numeric still works (e.g., 42 or #00042).',
                 bg=self.bg_frame, fg=self.fg_muted).pack(pady=(2, 10))

        # Export button at bottom of check-in box
        tk.Button(box, text='Export Check-Ins to CSV', command=self.on_export_checkins,
                  bg=self.btn_secondary, fg=self.fg_text, activebackground=self.btn_secondary_active, activeforeground=self.fg_text, takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(pady=(0, 10))

        self.checkin_log = tk.Text(frm, height=10, bg=self.bg_frame, fg=self.fg_text, insertbackground=self.fg_text)
        self.checkin_log.pack(fill='both', expand=True, padx=8, pady=8)
        self.checkin_log.insert('end', 'Check-in log will appear here...\n')
        self.checkin_log.config(state='disabled')

    # ---- Settings Tab ----
    def _build_settings_tab(self):
        frm = self.tab_settings
        
        # Create scrollable canvas for settings
        canvas = tk.Canvas(frm, bg=self.bg_main, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frm, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.bg_main)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Make canvas expand with window
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Make scrollable_frame expand to fill canvas width
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(canvas.find_withtag("all")[0], width=e.width))
        
        # Now use scrollable_frame instead of frm for all content
        box = tk.LabelFrame(scrollable_frame, text='Event Settings', bg=self.bg_frame, fg=self.fg_text)
        box.pack(padx=8, pady=12, fill='both', expand=True)

        # Mode Selection (NEW)
        tk.Label(box, text='Mode:', bg=self.bg_frame, fg=self.fg_text).grid(row=0, column=0, padx=8, pady=6, sticky='w')
        self.var_mode = tk.StringVar(value=self.current_mode)
        mode_frame = tk.Frame(box, bg=self.bg_frame)
        mode_frame.grid(row=0, column=1, padx=8, pady=6, sticky='w')
        tk.Radiobutton(mode_frame, text='Event Ticketing', variable=self.var_mode, value='ticketing',
                       bg=self.bg_frame, fg=self.fg_text, selectcolor=self.bg_frame, activebackground=self.bg_frame).pack(side='left', padx=(0,10))
        tk.Radiobutton(mode_frame, text='Product Sales', variable=self.var_mode, value='sales',
                       bg=self.bg_frame, fg=self.fg_text, selectcolor=self.bg_frame, activebackground=self.bg_frame).pack(side='left')

        # Organization Name
        tk.Label(box, text='Organization Name:', bg=self.bg_frame, fg=self.fg_text).grid(row=1, column=0, padx=8, pady=6, sticky='w')
        self.var_org = tk.StringVar(value=self.db.get_setting('organization_name', 'Your Organization Name') or 'Your Organization Name')
        tk.Entry(box, textvariable=self.var_org, width=30).grid(row=1, column=1, padx=8, pady=6, sticky='w')

        tk.Label(box, text='Event Name:', bg=self.bg_frame, fg=self.fg_text).grid(row=2, column=0, padx=8, pady=6, sticky='w')
        self.var_event = tk.StringVar(value=self.db.get_setting('event_name', 'TRUNK OR TREAT') or 'TRUNK OR TREAT')
        tk.Entry(box, textvariable=self.var_event, width=30).grid(row=2, column=1, padx=8, pady=6, sticky='w')

        tk.Label(box, text='Event Code (prefix):', bg=self.bg_frame, fg=self.fg_text).grid(row=3, column=0, padx=8, pady=6, sticky='w')
        self.var_event_code = tk.StringVar(value=self.db.get_setting('event_code', 'EVT') or 'EVT')
        tk.Entry(box, textvariable=self.var_event_code, width=10).grid(row=3, column=1, padx=8, pady=6, sticky='w')

        # Accent Color with picker button
        tk.Label(box, text='Accent Color:', bg=self.bg_frame, fg=self.fg_text).grid(row=4, column=0, padx=8, pady=6, sticky='w')
        color_frame = tk.Frame(box, bg=self.bg_frame)
        color_frame.grid(row=4, column=1, padx=8, pady=6, sticky='w')
        self.var_color = tk.StringVar(value=self.db.get_setting('ticket_color', '#ff7a00') or '#ff7a00')
        self.color_entry = tk.Entry(color_frame, textvariable=self.var_color, width=10)
        self.color_entry.pack(side='left', padx=(0, 6))
        self.color_preview = tk.Label(color_frame, text='  ', bg=self.var_color.get(), width=3, relief='solid', borderwidth=1)
        self.color_preview.pack(side='left', padx=(0, 6))
        tk.Button(color_frame, text='Pick Color', command=self.on_pick_color,
                  bg='#c9d5df', fg='#0f1216', activebackground='#b0bec8', activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(side='left')

        # Update preview when hex entry changes
        self.var_color.trace_add('write', lambda *_: self._update_color_preview())

        # QR Code Toggle
        tk.Label(box, text='Include QR Codes:', bg=self.bg_frame, fg=self.fg_text).grid(row=5, column=0, padx=8, pady=6, sticky='w')
        self.var_qr_enabled = tk.BooleanVar(value=self.db.get_setting('qr_enabled', '1') == '1')
        chk = tk.Checkbutton(box, variable=self.var_qr_enabled, bg=self.bg_frame, fg=self.fg_text,
                             selectcolor=self.bg_frame, activebackground=self.bg_frame)
        chk.grid(row=5, column=1, padx=8, pady=6, sticky='w')

        tk.Button(box, text='Save', command=self.on_save_settings,
                  bg=self.accent, fg='#0f1216', activebackground=self.selection_bg, activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).grid(row=6, column=0, columnspan=2, pady=8)

        # Custom Fields Section
        fields_box = tk.LabelFrame(scrollable_frame, text='Custom Fields', bg=self.bg_frame, fg=self.fg_text)
        fields_box.pack(padx=8, pady=12, fill='both', expand=True)
        
        tk.Label(fields_box, text='Enable fields you need:', bg=self.bg_frame, fg=self.fg_muted, font=('Arial', 9)).grid(row=0, column=0, columnspan=2, padx=8, pady=(8,4), sticky='w')
        
        # Define available fields
        self.available_fields = {
            'classroom': 'Room/Classroom',
            'teacher': 'Teacher',
            'address': 'Address',
            'email': 'Email',
            'phone': 'Phone',
            'grade': 'Grade',
            'notes': 'Notes'
        }
        
        self.field_vars = {}
        row = 1
        for field_key, field_label in self.available_fields.items():
            var = tk.BooleanVar(value=(field_key in self.enabled_fields))
            self.field_vars[field_key] = var
            chk = tk.Checkbutton(fields_box, text=field_label, variable=var, 
                                bg=self.bg_frame, fg=self.fg_text, selectcolor=self.bg_frame, activebackground=self.bg_frame)
            chk.grid(row=row, column=0, padx=20, pady=2, sticky='w')
            row += 1
        
        tk.Label(fields_box, text='', bg=self.bg_frame).grid(row=row, column=0, pady=4)
        row += 1
        
        tk.Label(fields_box, text='Show on labels:', bg=self.bg_frame, fg=self.fg_muted, font=('Arial', 9)).grid(row=row, column=0, columnspan=2, padx=8, pady=(8,4), sticky='w')
        row += 1
        
        self.label_field_vars = {}
        for field_key, field_label in self.available_fields.items():
            var = tk.BooleanVar(value=(field_key in self.label_fields))
            self.label_field_vars[field_key] = var
            chk = tk.Checkbutton(fields_box, text=f"Include {field_label} on labels", variable=var,
                                bg=self.bg_frame, fg=self.fg_text, selectcolor=self.bg_frame, activebackground=self.bg_frame)
            chk.grid(row=row, column=0, padx=20, pady=2, sticky='w')
            row += 1
        
        tk.Label(fields_box, text='💡 Changes take effect immediately when you click Save.', bg=self.bg_frame, fg=self.fg_muted, 
                font=('Arial', 9, 'italic')).grid(row=row, column=0, columnspan=2, padx=8, pady=8, sticky='w')

        # Label Printing Settings Section
        label_settings_box = tk.LabelFrame(scrollable_frame, text='Label Printing Settings', bg=self.bg_frame, fg=self.fg_text)
        label_settings_box.pack(padx=8, pady=12, fill='both', expand=True)
        
        tk.Label(label_settings_box, text='Fine-tune label printing for your printer:', bg=self.bg_frame, fg=self.fg_muted, 
                font=('Arial', 9)).grid(row=0, column=0, columnspan=3, padx=8, pady=(8,4), sticky='w')
        
        # Get current label settings
        current_label_settings = self.db.get_label_settings()
        
        # Show Border checkbox
        label_row = 1
        tk.Label(label_settings_box, text='Show Borders:', bg=self.bg_frame, fg=self.fg_text).grid(row=label_row, column=0, padx=8, pady=6, sticky='w')
        self.var_label_show_border = tk.BooleanVar(value=current_label_settings['show_border'])
        chk_border = tk.Checkbutton(label_settings_box, variable=self.var_label_show_border, bg=self.bg_frame, fg=self.fg_text,
                             selectcolor=self.bg_frame, activebackground=self.bg_frame)
        chk_border.grid(row=label_row, column=1, padx=8, pady=6, sticky='w')
        tk.Label(label_settings_box, text='(helpful for testing alignment)', bg=self.bg_frame, fg=self.fg_muted, 
                font=('Arial', 8, 'italic')).grid(row=label_row, column=2, padx=(0,8), pady=6, sticky='w')
        label_row += 1
        
        # Vertical Gap
        tk.Label(label_settings_box, text='Vertical Gap:', bg=self.bg_frame, fg=self.fg_text).grid(row=label_row, column=0, padx=8, pady=6, sticky='w')
        gap_frame = tk.Frame(label_settings_box, bg=self.bg_frame)
        gap_frame.grid(row=label_row, column=1, columnspan=2, padx=8, pady=6, sticky='w')
        self.var_label_vgap = tk.StringVar(value=str(current_label_settings['vertical_gap']))
        tk.Entry(gap_frame, textvariable=self.var_label_vgap, width=6).pack(side='left')
        tk.Label(gap_frame, text='inches between rows', bg=self.bg_frame, fg=self.fg_muted, font=('Arial', 8)).pack(side='left', padx=5)
        label_row += 1
        
        # Horizontal Gap
        tk.Label(label_settings_box, text='Horizontal Gap:', bg=self.bg_frame, fg=self.fg_text).grid(row=label_row, column=0, padx=8, pady=6, sticky='w')
        hgap_frame = tk.Frame(label_settings_box, bg=self.bg_frame)
        hgap_frame.grid(row=label_row, column=1, columnspan=2, padx=8, pady=6, sticky='w')
        self.var_label_hgap = tk.StringVar(value=str(current_label_settings['horizontal_gap']))
        tk.Entry(hgap_frame, textvariable=self.var_label_hgap, width=6).pack(side='left')
        tk.Label(hgap_frame, text='inches between columns', bg=self.bg_frame, fg=self.fg_muted, font=('Arial', 8)).pack(side='left', padx=5)
        label_row += 1
        
        # Top Margin
        tk.Label(label_settings_box, text='Top Margin:', bg=self.bg_frame, fg=self.fg_text).grid(row=label_row, column=0, padx=8, pady=6, sticky='w')
        tmargin_frame = tk.Frame(label_settings_box, bg=self.bg_frame)
        tmargin_frame.grid(row=label_row, column=1, columnspan=2, padx=8, pady=6, sticky='w')
        self.var_label_margin_top = tk.StringVar(value=str(current_label_settings['margin_top']))
        tk.Entry(tmargin_frame, textvariable=self.var_label_margin_top, width=6).pack(side='left')
        tk.Label(tmargin_frame, text='inches from top of page', bg=self.bg_frame, fg=self.fg_muted, font=('Arial', 8)).pack(side='left', padx=5)
        label_row += 1
        
        # Left Margin
        tk.Label(label_settings_box, text='Left Margin:', bg=self.bg_frame, fg=self.fg_text).grid(row=label_row, column=0, padx=8, pady=6, sticky='w')
        lmargin_frame = tk.Frame(label_settings_box, bg=self.bg_frame)
        lmargin_frame.grid(row=label_row, column=1, columnspan=2, padx=8, pady=6, sticky='w')
        self.var_label_margin_left = tk.StringVar(value=str(current_label_settings['margin_left']))
        tk.Entry(lmargin_frame, textvariable=self.var_label_margin_left, width=6).pack(side='left')
        tk.Label(lmargin_frame, text='inches from left of page', bg=self.bg_frame, fg=self.fg_muted, font=('Arial', 8)).pack(side='left', padx=5)
        label_row += 1
        
        # Presets
        tk.Label(label_settings_box, text='Quick Presets:', bg=self.bg_frame, fg=self.fg_text).grid(row=label_row, column=0, padx=8, pady=6, sticky='w')
        preset_frame = tk.Frame(label_settings_box, bg=self.bg_frame)
        preset_frame.grid(row=label_row, column=1, columnspan=2, padx=8, pady=6, sticky='w')
        
        def apply_preset_default():
            self.var_label_vgap.set('0.0')
            self.var_label_hgap.set('0.14')
            self.var_label_margin_top.set('0.5')
            self.var_label_margin_left.set('0.15625')
        
        def apply_preset_tight():
            self.var_label_vgap.set('0.0')
            self.var_label_hgap.set('0.0')
            self.var_label_margin_top.set('0.5')
            self.var_label_margin_left.set('0.21875')  # Wider left margin to compensate for no gaps
        
        def apply_preset_spaced():
            self.var_label_vgap.set('0.1')
            self.var_label_hgap.set('0.2')
            self.var_label_margin_top.set('0.5')
            self.var_label_margin_left.set('0.09375')  # Smaller margin to fit with larger gaps
        
        tk.Button(preset_frame, text='Default', command=apply_preset_default,
                  bg='#c9d5df', fg='#0f1216', activebackground='#b0bec8', activeforeground='#0f1216', 
                  takefocus=0, relief='flat', bd=0, highlightthickness=0, padx=8).pack(side='left', padx=2)
        tk.Button(preset_frame, text='Tight', command=apply_preset_tight,
                  bg='#c9d5df', fg='#0f1216', activebackground='#b0bec8', activeforeground='#0f1216', 
                  takefocus=0, relief='flat', bd=0, highlightthickness=0, padx=8).pack(side='left', padx=2)
        tk.Button(preset_frame, text='Spaced', command=apply_preset_spaced,
                  bg='#c9d5df', fg='#0f1216', activebackground='#b0bec8', activeforeground='#0f1216', 
                  takefocus=0, relief='flat', bd=0, highlightthickness=0, padx=8).pack(side='left', padx=2)
        label_row += 1
        
        tk.Label(label_settings_box, text='💡 Tip: Turn on borders while testing, turn off for final printing.', bg=self.bg_frame, fg=self.fg_muted, 
                font=('Arial', 8, 'italic')).grid(row=label_row, column=0, columnspan=3, padx=8, pady=(0,8), sticky='w')

    # ---- Help Tab ----
    def _build_help_tab(self):
        frm = self.tab_help

        # Scrollable container
        canvas = tk.Canvas(frm, bg=self.bg_main, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frm, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.bg_main)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Content
        content = scrollable_frame

        # CSV Import Format
        csv_box = tk.LabelFrame(content, text='CSV/Excel Import Format', bg=self.bg_frame, fg=self.fg_text, font=('Arial', 12, 'bold'))
        csv_box.pack(padx=20, pady=20, fill='x')

        tk.Label(csv_box, text='Required Columns:', bg=self.bg_frame, fg=self.accent, font=('Arial', 11, 'bold')).pack(anchor='w', padx=15, pady=(10, 5))

        required_text = """• Quantity (or Qty) - Number of tickets per person
• Student Name (or Name, Full Name) - Full name of attendee
  OR
• First (or First Name) - First name
• Last (or Last Name) - Last name"""

        tk.Label(csv_box, text=required_text, bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10), justify='left').pack(anchor='w', padx=30, pady=5)

        tk.Label(csv_box, text='Optional Columns:', bg=self.bg_frame, fg=self.accent, font=('Arial', 11, 'bold')).pack(anchor='w', padx=15, pady=(15, 5))

        optional_text = """• Classroom (or Room, Class) - Room number for label printing
• Teacher (or Teacher Name) - Teacher name for sales mode"""

        tk.Label(csv_box, text=optional_text, bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10), justify='left').pack(anchor='w', padx=30, pady=5)

        tk.Label(csv_box, text='Example CSV Format:', bg=self.bg_frame, fg=self.accent, font=('Arial', 11, 'bold')).pack(anchor='w', padx=15, pady=(15, 5))

        example_frame = tk.Frame(csv_box, bg='#1c232d', relief='solid', borderwidth=1)
        example_frame.pack(padx=30, pady=(5, 15), fill='x')

        example_text = """Quantity,Student Name,Classroom,Teacher
2,Julia McSweeney,101,Smith
2,Haley DiPaolo,202,Johnson
4,Emmett Potts,101,Smith
1,Felix Dambach,204,Davis"""

        tk.Label(example_frame, text=example_text, bg='#1c232d', fg='#c9d5df', font=('Courier', 9), justify='left').pack(padx=10, pady=10, anchor='w')

        tk.Label(csv_box, text='Note: Column names are case-insensitive. Classroom and Teacher are optional.',
                 bg=self.bg_frame, fg=self.fg_muted, font=('Arial', 9, 'italic')).pack(anchor='w', padx=30, pady=(0, 15))

        # Label Printing
        label_box = tk.LabelFrame(content, text='Envelope Label Printing', bg=self.bg_frame, fg=self.fg_text, font=('Arial', 12, 'bold'))
        label_box.pack(padx=20, pady=20, fill='x')

        tk.Label(label_box, text='Label Template:', bg=self.bg_frame, fg=self.accent, font=('Arial', 11, 'bold')).pack(anchor='w', padx=15, pady=(10, 5))

        tk.Label(label_box, text='Avery 5160 (or compatible)', bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10, 'bold')).pack(anchor='w', padx=30, pady=5)

        specs_text = """• 30 labels per sheet (3 columns × 10 rows)
• Label size: 2.625" × 1"
• Margins: 0.22" left/right, 0.5" top
• Available at office supply stores or online"""

        tk.Label(label_box, text=specs_text, bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10), justify='left').pack(anchor='w', padx=30, pady=5)

        tk.Label(label_box, text='Compatible Brands:', bg=self.bg_frame, fg=self.accent, font=('Arial', 11, 'bold')).pack(anchor='w', padx=15, pady=(15, 5))

        brands_text = """• Avery 5160
• Office Depot/OfficeMax (same size)
• Staples (equivalent template)
• Amazon Basics address labels (compatible)"""

        tk.Label(label_box, text=brands_text, bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10), justify='left').pack(anchor='w', padx=30, pady=5)

        tk.Label(label_box, text='What Gets Printed:', bg=self.bg_frame, fg=self.accent, font=('Arial', 11, 'bold')).pack(anchor='w', padx=15, pady=(15, 5))

        printed_text = """• Student name (bold, centered)
• Room number (if provided in CSV)
• Event name (from Settings) OR Teacher + Qty (in Sales mode)

Labels are deduplicated - one label per (student, room), regardless of ticket quantity."""

        tk.Label(label_box, text=printed_text, bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10), justify='left').pack(anchor='w', padx=30, pady=(5, 15))

        # Quick Tips
        tips_box = tk.LabelFrame(content, text='Quick Tips', bg=self.bg_frame, fg=self.fg_text, font=('Arial', 12, 'bold'))
        tips_box.pack(padx=20, pady=20, fill='x')

        tips_text = """• Import your CSV first, then print tickets and labels
• Tickets show name only (privacy)
• Labels show name + room (for distribution)
• Three label printing options: Selected, All, or All Unprinted
• Use Filter box to search tickets by name or room
• Toggle "Show all events" to see tickets from previous events
• By default, only current event code tickets are shown
• Check-In accepts QR codes or ticket IDs (ticketing mode only)
• Export CSV anytime to get full reports
• Export Check-Ins CSV from Check-In tab (ticketing mode)
• Use Product Sales mode for pretzel/popcorn orders"""

        tk.Label(tips_box, text=tips_text, bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10), justify='left').pack(anchor='w', padx=30, pady=15)

    # ---- About Tab ----
    def _build_about_tab(self):
        frm = self.tab_about

        # Center container
        container = tk.Frame(frm, bg=self.bg_main)
        container.pack(expand=True)

        # App info
        tk.Label(container, text='Event & Sales Manager', bg=self.bg_main, fg=self.accent,
                 font=('Arial', 24, 'bold')).pack(pady=(20, 10))

        tk.Label(container, text='Version 1.2 (with Sales Mode)', bg=self.bg_main, fg=self.fg_muted,
                 font=('Arial', 12)).pack(pady=5)

        tk.Label(container, text='A professional system for events, ticketing & product sales', bg=self.bg_main, fg=self.fg_text,
                 font=('Arial', 11)).pack(pady=(10, 30))

        # Features
        features_frame = tk.Frame(container, bg=self.bg_frame, relief='solid', borderwidth=1)
        features_frame.pack(pady=20, padx=40, fill='x')

        tk.Label(features_frame, text='Features', bg=self.bg_frame, fg=self.accent,
                 font=('Arial', 14, 'bold')).pack(pady=(15, 10))

        features = [
            '✓ Generate custom tickets with QR codes',
            '✓ Print professional envelope labels',
            '✓ Real-time check-in with scanner support',
            '✓ Import from CSV/Excel',
            '✓ Export attendance reports',
            '✓ Customizable branding and colors',
            '✓ Product Sales mode for fundraisers',
            '✓ Order summary exports for vendors'
        ]

        for feature in features:
            tk.Label(features_frame, text=feature, bg=self.bg_frame, fg=self.fg_text,
                     font=('Arial', 11), anchor='w').pack(pady=3, padx=20)

        tk.Label(features_frame, text='', bg=self.bg_frame).pack(pady=5)

        # Credits
        tk.Label(container, text='Created by Matthew Grilli', bg=self.bg_main, fg=self.fg_text,
                 font=('Arial', 12, 'bold')).pack(pady=(30, 5))

        # Email as clickable link
        email_label = tk.Label(container, text='him@mattgrilli.com', bg=self.bg_main, fg=self.accent,
                               font=('Arial', 11, 'underline'), cursor='hand2')
        email_label.pack(pady=5)
        email_label.bind('<Button-1>', lambda e: self._open_email())

        tk.Label(container, text='Built with ❤️ for organizers everywhere', bg=self.bg_main, fg=self.fg_muted,
                 font=('Arial', 10, 'italic')).pack(pady=(20, 40))

    def _open_email(self):
        """Open default email client."""
        webbrowser.open('mailto:him@mattgrilli.com')

    # ============ Actions ============
    def refresh(self):
        # Update event filter dropdown with available event codes
        event_codes = self.db.get_unique_event_codes()
        dropdown_values = ['All Events'] + event_codes
        self.event_filter_dropdown['values'] = dropdown_values
        # Keep current selection if still valid, otherwise reset to 'All Events'
        if self.event_filter_var.get() not in dropdown_values:
            self.event_filter_var.set('All Events')
        
        # Get selected event filter
        selected_event = self.event_filter_var.get()
        
        # Reload main table
        self._tree_num_by_item.clear()
        for it in self.tree.get_children():
            self.tree.delete(it)
        for r in self.db.list_tickets():
            tnum, tcode, f, l, pr, ch, cha, cr, classroom, teacher = r
            
            # Filter by selected event code
            if selected_event != 'All Events':
                ticket_prefix = tcode.split('-')[0] if tcode and '-' in tcode else ''
                if ticket_prefix != selected_event:
                    continue  # Skip tickets from other events
            
            # Show different columns based on mode
            if self.current_mode == 'sales':
                values = (tcode or '', f, l, classroom or '', teacher or '', 'Yes' if pr else 'No', cr)
            else:
                values = (tcode or '', f, l, classroom or '', 'Yes' if pr else 'No', 'Yes' if ch else 'No', cha, cr)
            iid = self.tree.insert('', 'end', values=values)
            self._tree_num_by_item[iid] = tnum
        
        # Reload labels tree
        self._labels_tree_num_by_item.clear()
        for it in self.labels_tree.get_children():
            self.labels_tree.delete(it)
        for r in self.db.list_tickets():
            tnum, tcode, f, l, pr, ch, cha, cr, classroom, teacher = r
            
            # Filter by selected event code
            if selected_event != 'All Events':
                ticket_prefix = tcode.split('-')[0] if tcode and '-' in tcode else ''
                if ticket_prefix != selected_event:
                    continue  # Skip tickets from other events
            
            if self.current_mode == 'sales':
                values = (tcode or '', f, l, classroom or '', teacher or '')
            else:
                values = (tcode or '', f, l, classroom or '')
            iid = self.labels_tree.insert('', 'end', values=values)
            self._labels_tree_num_by_item[iid] = tnum
        
        # Update table header counts
        manage_count = len(self._tree_num_by_item)
        labels_count = len(self._labels_tree_num_by_item)
        mode_label = "Orders" if self.current_mode == 'sales' else "Tickets"
        
        # Update Manage tab table header
        if hasattr(self, 'manage_table_frame'):
            self.manage_table_frame.config(text=f'{mode_label} ({manage_count})')
        
        # Update Labels tab table header
        if hasattr(self, 'labels_table_frame'):
            self.labels_table_frame.config(text=f'Select {mode_label} for Labels ({labels_count})')
        
        total, printed, unprinted, checked = self.db.stats()
        
        # Show filtered count if filtering by event
        if selected_event != 'All Events':
            visible_count = len(self._tree_num_by_item)
            self.stats_lbl.config(text=f"Showing {visible_count} of {total} {mode_label} (Event: {selected_event})  |  Printed: {printed}  |  Unprinted: {unprinted}  |  Checked-In: {checked}")
        else:
            self.stats_lbl.config(text=f"Total {mode_label}: {total}  |  Printed: {printed}  |  Unprinted: {unprinted}  |  Checked-In: {checked}")
        
        self.apply_filter()
        self.apply_labels_filter()

    def apply_filter(self):
        q = (getattr(self, 'filter_var', tk.StringVar()).get() or '').lower().strip()
        # Get ALL items including detached ones
        all_items = list(self._tree_num_by_item.keys())
        for item in all_items:
            try:
                vals = [str(v).lower() for v in self.tree.item(item)['values']]
                show = (not q) or any(q in v for v in vals)
                if show:
                    self.tree.reattach(item, '', 'end')
                else:
                    self.tree.detach(item)
            except tk.TclError:
                # Item might have been deleted
                pass

    def apply_labels_filter(self):
        """Filter the labels tree table."""
        q = (getattr(self, 'labels_filter_var', tk.StringVar()).get() or '').lower().strip()
        all_items = list(self._labels_tree_num_by_item.keys())
        for item in all_items:
            try:
                vals = [str(v).lower() for v in self.labels_tree.item(item)['values']]
                show = (not q) or any(q in v for v in vals)
                if show:
                    self.labels_tree.reattach(item, '', 'end')
                else:
                    self.labels_tree.detach(item)  # FIXED: was incorrectly using self.tree
            except tk.TclError:
                # Item might have been deleted
                pass

    def on_generate(self):
        first = self.ent_first.get().strip(); last = self.ent_last.get().strip()
        classroom = self.ent_classroom.get().strip()
        teacher = self.ent_teacher.get().strip()
        try:
            qty = int(self.ent_qty.get())
        except Exception:
            qty = 1
        if not first or not last:
            messagebox.showwarning('Missing Info', 'Please provide first and last name.')
            return
        
        # Build custom fields dict
        custom_fields = {}
        if classroom:
            custom_fields['classroom'] = classroom
        if teacher:
            custom_fields['teacher'] = teacher
        
        codes = self.db.create_attendee_with_tickets(first, last, qty, custom_fields=custom_fields)
        if len(codes) == 1:
            message = f"Created ticket ID {codes[0]} for {first} {last}."
        else:
            message = f"Created {len(codes)} tickets ({codes[0]} … {codes[-1]}) for {first} {last}."
        messagebox.showinfo('Success', message)
        self.ent_first.delete(0, 'end'); self.ent_last.delete(0, 'end'); self.ent_classroom.delete(0, 'end'); self.ent_teacher.delete(0, 'end'); self.ent_qty.delete(0, 'end'); self.ent_qty.insert(0, '1')
        self.refresh()

    def _selected_nums(self) -> List[int]:
        nums: List[int] = []
        for iid in self.tree.selection():
            num = self._tree_num_by_item.get(iid)
            if num is not None:
                nums.append(num)
        return nums

    def on_edit_from_labels(self):
        """Edit a ticket from the Labels tab - similar to on_edit but uses labels_tree selection."""
        sels = self.labels_tree.selection()
        if len(sels) != 1:
            messagebox.showwarning('Select One', 'Select exactly one ticket to edit.')
            return
        iid = sels[0]
        v = self.labels_tree.item(iid)['values']
        tnum = self._labels_tree_num_by_item.get(iid)
        if tnum is None:
            messagebox.showerror('Error', 'Could not find selected ticket.')
            return
        
        # Get full ticket data from database to access all fields
        rows = self.db.list_tickets()
        ticket_data = None
        for r in rows:
            if r[0] == tnum:  # r[0] is ticket_number
                ticket_data = r
                break
        
        if not ticket_data:
            messagebox.showerror('Error', 'Could not load ticket data.')
            return
        
        # Parse values based on current display mode
        if self.current_mode == 'sales':
            tcode, first, last, classroom, teacher = v[0], v[1], v[2], v[3], v[4]
        else:
            tcode, first, last, classroom = v[0], v[1], v[2], v[3]
            teacher = ''
        
        # Call the standard edit dialog with this ticket number
        self._show_edit_dialog(tnum, tcode, first, last, classroom, teacher)

    def on_edit(self):
        """Edit a ticket - dynamically shows all enabled fields."""
        sels = self.tree.selection()
        if len(sels) != 1:
            messagebox.showwarning('Select One', 'Select exactly one ticket to edit.')
            return
        iid = sels[0]
        v = self.tree.item(iid)['values']
        tnum = self._tree_num_by_item.get(iid)
        if tnum is None:
            messagebox.showerror('Error', 'Could not find selected ticket.')
            return
        
        # Get full ticket data from database to access all fields
        rows = self.db.list_tickets()
        ticket_data = None
        for r in rows:
            if r[0] == tnum:  # r[0] is ticket_number
                ticket_data = r
                break
        
        if not ticket_data:
            messagebox.showerror('Error', 'Could not load ticket data.')
            return
        
        # Parse values based on current display mode
        if self.current_mode == 'sales':
            tcode, first, last, classroom, teacher = v[0], v[1], v[2], v[3], v[4]
        else:
            tcode, first, last, classroom = v[0], v[1], v[2], v[3]
            teacher = ''
        
        # Call the shared edit dialog
        self._show_edit_dialog(tnum, tcode, first, last, classroom, teacher)
    
    def _show_edit_dialog(self, tnum: int, tcode: str, first: str, last: str, classroom: str, teacher: str):
        """Shared method to show edit dialog for a ticket."""
        # Get attendee_id to fetch additional fields
        cur = self.db.conn.cursor()
        cur.execute("SELECT attendee_id FROM tickets WHERE ticket_number=?", (tnum,))
        row = cur.fetchone()
        if not row:
            messagebox.showerror('Error', 'Could not find ticket.')
            return
        attendee_id = row[0]
        
        # Fetch all attendee data including custom fields
        cur.execute("SELECT * FROM attendees WHERE attendee_id=?", (attendee_id,))
        attendee_row = cur.fetchone()
        col_names = [desc[0] for desc in cur.description]
        attendee_dict = dict(zip(col_names, attendee_row))
            
        # Create edit dialog
        dlg = tk.Toplevel(self.root); dlg.title(f'Edit Ticket {tcode}')
        dlg.configure(bg=self.bg_frame)
        tk.Label(dlg, text=f'Ticket ID: {tcode}', bg=self.bg_frame, fg=self.fg_text, font=('Arial', 12, 'bold')).pack(pady=8)
        
        frm = tk.Frame(dlg, bg=self.bg_frame); frm.pack(padx=12, pady=8)
        
        # Core fields (always shown)
        row_idx = 0
        tk.Label(frm, text='First Name', bg=self.bg_frame, fg=self.fg_text).grid(row=row_idx, column=0, padx=6, pady=6, sticky='w')
        e_first = tk.Entry(frm, width=30)
        e_first.insert(0, first)
        e_first.grid(row=row_idx, column=1, padx=6, pady=6)
        row_idx += 1
        
        tk.Label(frm, text='Last Name', bg=self.bg_frame, fg=self.fg_text).grid(row=row_idx, column=0, padx=6, pady=6, sticky='w')
        e_last = tk.Entry(frm, width=30)
        e_last.insert(0, last)
        e_last.grid(row=row_idx, column=1, padx=6, pady=6)
        row_idx += 1
        
        # Dynamic fields based on enabled_fields
        field_entries = {}
        for field in self.enabled_fields:
            # Get field label from available_fields dict
            field_label = self.available_fields.get(field, field.title())
            
            tk.Label(frm, text=field_label, bg=self.bg_frame, fg=self.fg_text).grid(row=row_idx, column=0, padx=6, pady=6, sticky='w')
            entry = tk.Entry(frm, width=30)
            
            # Load existing value if available
            existing_value = attendee_dict.get(field, '')
            if existing_value:
                entry.insert(0, existing_value)
            
            entry.grid(row=row_idx, column=1, padx=6, pady=6)
            field_entries[field] = entry
            row_idx += 1
            
        def save():
            nf = e_first.get().strip()
            nl = e_last.get().strip()
            if not nf or not nl:
                messagebox.showwarning('Missing', 'First and Last name are required'); return
            
            # Collect custom field values
            custom_fields = {}
            for field, entry in field_entries.items():
                custom_fields[field] = entry.get().strip()
            
            try:
                self.db.update_attendee_name_for_ticket(tnum, nf, nl, custom_fields)
                dlg.destroy()
                self.refresh()
                messagebox.showinfo('Saved', 'Ticket updated successfully!')
            except Exception as e:
                messagebox.showerror('Error', f'Could not update ticket:\n{e}')
        
        # Buttons
        btn_frame = tk.Frame(dlg, bg=self.bg_frame)
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text='Save', command=save,
                  bg=self.accent, fg='#0f1216', activebackground=self.selection_bg, activeforeground='#0f1216', 
                  takefocus=0, relief='flat', bd=0, highlightthickness=0, padx=20, pady=6).pack(side='left', padx=5)
        tk.Button(btn_frame, text='Cancel', command=dlg.destroy,
                  bg=self.btn_secondary, fg=self.fg_text, activebackground=self.btn_secondary_active, activeforeground=self.fg_text, 
                  takefocus=0, relief='flat', bd=0, highlightthickness=0, padx=20, pady=6).pack(side='left', padx=5)

    def on_delete(self):
        nums = self._selected_nums()
        if not nums:
            messagebox.showwarning('No Selection', 'Select ticket(s) to delete.'); return
        if not messagebox.askyesno('Confirm', f'Delete {len(nums)} ticket(s)? This cannot be undone.'):
            return
        deleted = self.db.delete_tickets(nums); self.refresh()
        messagebox.showinfo('Deleted', f'Removed {deleted} ticket(s).')

    def _tickets_by_numbers(self, nums: List[int]) -> List[Tuple]:
        rows = self.db.list_tickets(); m = {r[0]: r for r in rows}
        return [m[n] for n in nums if n in m]

    def on_print_selected(self):
        nums = self._selected_nums()
        if not nums:
            messagebox.showwarning('No Selection', 'Select tickets to print.')
            return
        self._print_tickets(nums)

    def on_print_all_unprinted(self):
        nums = self.db.unprinted_ticket_numbers()
        if not nums:
            messagebox.showinfo('None', 'All tickets are already printed.')
            return
        self._print_tickets(nums)

    def _print_tickets(self, nums: List[int]):
        rows = self._tickets_by_numbers(nums)
        if not rows:
            return
        # Ask format
        fmt = messagebox.askyesnocancel('Format', 'PDF (Yes) or HTML (No)?')
        if fmt is None:
            return
        ext = '.pdf' if fmt else '.html'
        out = filedialog.asksaveasfilename(defaultextension=ext, filetypes=[('PDF','*.pdf'),('HTML','*.html')])
        if not out:
            return
        try:
            if fmt:
                self.renderer.generate_pdf(rows, Path(out))
            else:
                self.renderer.generate_html(rows, Path(out))
            self.db.mark_printed(nums, 1)
            messagebox.showinfo('Success', f'Printed {len(nums)} tickets to {out}')
            self.refresh()
        except Exception as e:
            messagebox.showerror('Error', str(e))

    def on_print_labels_selected(self):
        """Print Avery 5160 labels for selected tickets from Labels tab (deduplicated by name+room)."""
        nums = []
        for iid in self.labels_tree.selection():
            num = self._labels_tree_num_by_item.get(iid)
            if num is not None:
                nums.append(num)
        
        if not nums:
            messagebox.showwarning('No Selection', 'Select tickets in the Labels tab to print labels for.')
            return
        
        # Get only the selected tickets
        rows = self._tickets_by_numbers(nums)
        if not rows:
            messagebox.showwarning('No Data', 'No tickets found for selection.')
            return
        
        self._print_labels(rows, f'{len(nums)} selected')

    def on_print_labels_all(self):
        """Print Avery 5160 labels for all tickets (deduplicated by name+room)."""
        rows = self.db.list_tickets()
        if not rows:
            messagebox.showwarning('No Data', 'No tickets to print labels for.')
            return
        
        self._print_labels(rows, 'all')

    def _print_labels(self, rows, description):
        """Common label printing logic with deduplication."""
        # Deduplicate by (first, last, classroom)
        seen = set()
        dedup = []
        for r in rows:
            tnum, tcode, first, last, printed, checked, checked_at, created, classroom, teacher = r
            key = (first.lower(), last.lower(), (classroom or '').lower())
            if key not in seen:
                seen.add(key)
                # For labels, we need: (ticket_number, ticket_code, first, last, classroom, teacher)
                dedup.append((tnum, tcode, first, last, classroom or '', teacher or ''))
        
        if not dedup:
            messagebox.showwarning('No Labels', 'No unique labels to print.')
            return
        
        out = filedialog.asksaveasfilename(defaultextension='.pdf', filetypes=[('PDF','*.pdf')])
        if not out:
            return
        
        try:
            self.renderer.generate_labels_pdf(dedup, Path(out))
            messagebox.showinfo('Success', f'Printed {len(dedup)} unique labels ({description}) to {out}')
        except Exception as e:
            messagebox.showerror('Error', str(e))

    def on_import(self):
        """Import from CSV or Excel."""
        p = filedialog.askopenfilename(filetypes=[('CSV','*.csv'),('Excel','*.xlsx *.xls'),('All','*.*')])
        if not p:
            return
        p = Path(p)
        rows = []
        try:
            if p.suffix.lower() == '.csv':
                with open(p, 'r', encoding='utf-8-sig') as f:
                    rdr = csv.DictReader(f)
                    for row in rdr:
                        # Try to get separate first/last columns
                        first = (row.get('First') or row.get('first') or row.get('First Name') or '').strip()
                        last = (row.get('Last') or row.get('last') or row.get('Last Name') or '').strip()

                        # If no separate columns, try "Student Name" or similar full name column
                        if not first and not last:
                            full_name = (row.get('Student Name') or row.get('Name') or row.get('name') or
                                         row.get('Full Name') or row.get('full name') or '').strip()
                            if full_name:
                                # Gentle warning for multi-names
                                if '&' in full_name or ',' in full_name:
                                    messagebox.showwarning('Multi-name Row',
                                                           f'Row "{full_name}" appears to include multiple names. '
                                                           f'Please split into separate rows for accuracy.')
                                first, last = self._split_name(full_name)

                        qty_s = (row.get('Qty') or row.get('qty') or row.get('Quantity') or '1')
                        classroom = (row.get('Classroom') or row.get('classroom') or row.get('Room') or
                                     row.get('room') or row.get('Class') or row.get('class') or '').strip()
                        teacher = (row.get('Teacher') or row.get('teacher') or 
                                   row.get('Teacher Name') or row.get('teacher name') or '').strip()

                        if not first and not last:
                            continue

                        # Handle cases where only one token parsed; treat as last name to avoid blank display
                        if not last:
                            last = first
                            first = ''

                        try:
                            qty = max(1, int(float(qty_s)))
                        except Exception:
                            qty = 1
                        rows.append((first, last, qty, classroom, teacher))
            else:
                if not HAS_PANDAS:
                    messagebox.showerror('Missing Library', 'To import Excel, install: pip install pandas openpyxl'); return
                df = pd.read_excel(str(p))

                def pick(*cands):
                    lower = [c.lower() for c in df.columns]
                    for c in cands:
                        if c in lower:
                            return df.columns[lower.index(c)]
                    return None

                # Try to find first/last name columns
                cf = pick('first', 'first name')
                cl = pick('last', 'last name')

                # If no separate columns, look for full name column
                full_name_col = pick('student name', 'name', 'full name')

                cq = pick('qty', 'quantity')
                cc = pick('classroom', 'room', 'class')
                ct = pick('teacher', 'teacher name')

                for _, r in df.iterrows():
                    first = ''
                    last = ''

                    if cf and cl:
                        first = str(r.get(cf, '')).strip()
                        last = str(r.get(cl, '')).strip()
                    elif full_name_col:
                        full_name = str(r.get(full_name_col, '')).strip()
                        if full_name and full_name.lower() != 'nan':
                            if '&' in full_name or ',' in full_name:
                                messagebox.showwarning('Multi-name Row',
                                                       f'Row "{full_name}" appears to include multiple names. '
                                                       f'Please split into separate rows for accuracy.')
                            first, last = self._split_name(full_name)
                    else:
                        # Fallback to first two columns
                        if len(df.columns) >= 2:
                            first = str(r.get(df.columns[0], '')).strip()
                            last = str(r.get(df.columns[1], '')).strip()

                    if (not first and not last) or first.lower() == 'nan' or last.lower() == 'nan':
                        continue

                    if not last:
                        last = first
                        first = ''

                    qty = 1
                    if cq is not None:
                        try:
                            qty = max(1, int(float(r.get(cq, 1))))
                        except Exception:
                            qty = 1

                    classroom = ''
                    if cc is not None:
                        classroom = str(r.get(cc, '')).strip()
                        if classroom.lower() == 'nan':
                            classroom = ''

                    teacher = ''
                    if ct is not None:
                        teacher = str(r.get(ct, '')).strip()
                        if teacher.lower() == 'nan':
                            teacher = ''

                    rows.append((first, last, qty, classroom, teacher))
        except Exception as e:
            messagebox.showerror('Import Error', f'Could not read file:\n{e}'); return
        if not rows:
            messagebox.showwarning('No Rows', 'No valid rows found.'); return
        created = 0
        for f, l, q, c, t in rows:
            custom_fields = {}
            if c:
                custom_fields['classroom'] = c
            if t:
                custom_fields['teacher'] = t
            self.db.create_attendee_with_tickets(f, l, q, custom_fields=custom_fields)
            created += q
        self.refresh()
        mode_label = "orders" if self.current_mode == 'sales' else "tickets"
        messagebox.showinfo('Imported', f'Imported {created} {mode_label} from {p.name}.')

    def _split_name(self, full: str) -> Tuple[str, str]:
        """Split full name into first/last. Handles most common cases."""
        parts = full.strip().split()
        if len(parts) == 1:
            return ('', parts[0])
        elif len(parts) == 2:
            return (parts[0], parts[1])
        else:
            return (parts[0], ' '.join(parts[1:]))

    def on_export(self):
        """Export all tickets to CSV."""
        rows = self.db.list_tickets()
        if not rows:
            messagebox.showwarning('No Data', 'No tickets to export.'); return
        out = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV','*.csv')])
        if not out:
            return
        try:
            with open(out, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['Ticket ID', 'First', 'Last', 'Room', 'Teacher', 'Printed', 'Checked In', 'Checked At', 'Created'])
                for r in rows:
                    if len(r) != 10:
                        print(f"Warning: Skipping row with incorrect number of fields: {len(r)}")
                        continue
                    tnum, tcode, first, last, printed, checked, checked_at, created, classroom, teacher = r
                    w.writerow([tcode or '', first, last, classroom or '', teacher or '', 'Yes' if printed else 'No', 'Yes' if checked else 'No', checked_at, created])
            messagebox.showinfo('Exported', f'Exported {len(rows)} tickets to {out}')
        except IOError as e:
            messagebox.showerror('File Error', f'Could not write to file:\n{e}')
        except Exception as e:
            messagebox.showerror('Export Error', f'Error during export:\n{type(e).__name__}: {e}')

    def on_export_checkins(self):
        """Export checked-in tickets to CSV."""
        rows = [r for r in self.db.list_tickets() if r[5]]  # r[5] is checked_in
        if not rows:
            messagebox.showwarning('No Data', 'No check-ins to export.'); return
        out = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV','*.csv')], initialfile='checkins.csv')
        if not out:
            return
        try:
            with open(out, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['Ticket ID', 'First', 'Last', 'Room', 'Teacher', 'Checked In At'])
                for r in rows:
                    if len(r) != 10:
                        print(f"Warning: Skipping row with incorrect number of fields: {len(r)}")
                        continue
                    tnum, tcode, first, last, printed, checked, checked_at, created, classroom, teacher = r
                    w.writerow([tcode or '', first, last, classroom or '', teacher or '', checked_at])
            messagebox.showinfo('Exported', f'Exported {len(rows)} check-ins to {out}')
        except IOError as e:
            messagebox.showerror('File Error', f'Could not write to file:\n{e}')
        except Exception as e:
            messagebox.showerror('Export Error', f'Error during export:\n{type(e).__name__}: {e}')

    def on_export_order_summary(self):
        """Export order summary for Product Sales mode - grouped by teacher."""
        summary = self.db.get_order_summary()
        if not summary:
            messagebox.showwarning('No Data', 'No orders with teacher information to export.')
            return
        
        out = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV', '*.csv')],
            initialfile='order_summary.csv'
        )
        if not out:
            return
        
        try:
            with open(out, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Teacher', 'Room', 'Total Quantity'])
                
                total_qty = 0
                for teacher, classroom, qty in summary:
                    writer.writerow([teacher, classroom or '', qty])
                    total_qty += qty
                
                # Add total row
                writer.writerow(['', 'TOTAL', total_qty])
            
            messagebox.showinfo('Exported', f'Order summary exported to {out}\nTotal items: {total_qty}')
        except IOError as e:
            messagebox.showerror('File Error', f'Could not write to file:\n{e}')
        except Exception as e:
            messagebox.showerror('Export Error', f'Error during export:\n{type(e).__name__}: {e}')

    def on_checkin(self):
        """Handle check-in when user scans or enters a ticket ID."""
        raw = self.checkin_var.get().strip()
        if not raw:
            return
        # Accept numeric or code like EVT-K7R4Z9; if scanner pasted extra chars, extract last plausible token
        m = SCAN_PATTERN.search(raw.strip().upper())
        if not m:
            messagebox.showwarning('Invalid', 'Scan or enter a valid ticket ID (e.g., EVT-K7R4Z9 or 42).'); return
        ident = m.group(0)
        parsed = int(ident) if ident.isdigit() else ident
        status, ts = self.db.check_in(parsed)
        self.checkin_var.set('')
        self._log_checkin(ident, status, ts)
        # Audible feedback (portable)
        try:
            if status in ('checked_in', 'already'):
                if platform.system() == 'Windows' and winsound:
                    winsound.MessageBeep()
                else:
                    self.root.bell()
        except Exception:
            # Sound feedback is optional, don't crash if it fails
            pass
        self.refresh()

    def _log_checkin(self, ident: str, status: str, ts: Optional[str]):
        self.checkin_log.config(state='normal')
        now = datetime.now().strftime('%H:%M:%S')
        if status == 'checked_in':
            line = f"[{now}] Ticket {ident} ✓ checked in"
        elif status == 'already':
            when = f" at {ts.split(' ')[1]}" if ts else ""
            line = f"[{now}] Ticket {ident} • already checked in{when}"
        else:
            line = f"[{now}] Ticket {ident} ✗ not found"
        self.checkin_log.insert('end', line + "\n")
        self.checkin_log.see('end'); self.checkin_log.config(state='disabled')

    def _update_color_preview(self) -> None:
        """
        Update the color preview box when hex value changes.
        Validates hex color format and supports both #RRGGBB and #RGB formats.
        """
        try:
            color = self.var_color.get().strip()
            if not color.startswith('#'):
                color = '#' + color
            
            # Validate hex color more robustly
            if len(color) == 7:
                try:
                    int(color[1:], 16)  # Validate it's valid hex
                    self.color_preview.config(bg=color)
                except ValueError:
                    # Invalid hex color, silently ignore
                    pass
            elif len(color) == 4:  # Support shorthand like #f00
                try:
                    int(color[1:], 16)
                    # Expand shorthand
                    expanded = '#' + ''.join([c*2 for c in color[1:]])
                    self.color_preview.config(bg=expanded)
                except ValueError:
                    pass
        except (tk.TclError, Exception):
            # Color not valid for Tk, ignore silently
            pass

    def on_pick_color(self):
        """Open color picker dialog."""
        current_color = self.var_color.get().strip()
        color = colorchooser.askcolor(color=current_color, title="Choose Accent Color")
        if color and color[1]:  # color is ((r,g,b), '#hexcode')
            self.var_color.set(color[1])
            self.color_preview.config(bg=color[1])

    def on_save_settings(self):
        """Save settings and apply changes dynamically without restart."""
        org = (self.var_org.get() or 'Your Organization Name').strip()
        ev = (self.var_event.get() or 'TRUNK OR TREAT').strip()
        evc = (self.var_event_code.get() or 'EVT').strip().upper()
        col = (self.var_color.get() or '#ff7a00').strip()
        qr_enabled = '1' if self.var_qr_enabled.get() else '0'
        mode = self.var_mode.get()
        
        # Save custom fields configuration
        enabled_fields = [field for field, var in self.field_vars.items() if var.get()]
        label_fields = [field for field, var in self.label_field_vars.items() if var.get()]
        
        # Save label printing settings
        label_settings = {
            'show_border': self.var_label_show_border.get(),
            'vertical_gap': float(self.var_label_vgap.get() or 0.0),
            'horizontal_gap': float(self.var_label_hgap.get() or 0.125),
            'margin_top': float(self.var_label_margin_top.get() or 0.5),
            'margin_left': float(self.var_label_margin_left.get() or 0.1875),
        }
        
        self.db.set_setting('organization_name', org)
        self.db.set_setting('event_name', ev)
        self.db.set_setting('event_code', evc)
        self.db.set_setting('ticket_color', col)
        self.db.set_setting('qr_enabled', qr_enabled)
        self.db.set_setting('mode', mode)
        self.db.set_enabled_fields(enabled_fields)
        self.db.set_label_fields(label_fields)
        self.db.set_label_settings(label_settings)
        
        # Ensure columns exist for newly enabled fields
        self.db.ensure_field_columns(enabled_fields)
        
        self.renderer = TicketRenderer(self.db)
        self.accent = col
        old_mode = self.current_mode
        old_fields = self.enabled_fields
        self.current_mode = mode
        self.enabled_fields = enabled_fields
        self.label_fields = label_fields

        # Update header color immediately
        self.header_frame.config(bg=col)
        self.header_label.config(bg=col)
        
        # Update mode indicator badge
        mode_text = "🎟️ Ticketing Mode" if mode == 'ticketing' else "📦 Sales Mode"
        self.mode_indicator.config(text=mode_text)

        # Handle mode switch or field changes: rebuild tabs if needed
        if old_mode != mode or old_fields != enabled_fields:
            # Remember which tab was selected
            current_tab_index = self.nb.index(self.nb.select())
            
            # Clear and rebuild manage tab
            for widget in self.tab_manage.winfo_children():
                widget.destroy()
            self._build_manage_tab()
            
            # Clear and rebuild labels tab (in case field changes affect it)
            for widget in self.tab_labels.winfo_children():
                widget.destroy()
            self._build_labels_tab()
            
            # Show/hide check-in tab based on mode
            if mode == 'sales':
                # Remove check-in tab
                try:
                    for i, tab_id in enumerate(self.nb.tabs()):
                        if self.nb.tab(i, "text") == "Check-In":
                            self.nb.forget(i)
                            break
                except tk.TclError:
                    pass
            else:
                # Add check-in tab back (before Settings)
                try:
                    # Find the position to insert (before Settings)
                    tabs = [self.nb.tab(i, "text") for i in range(len(self.nb.tabs()))]
                    if "Check-In" not in tabs:
                        settings_idx = tabs.index("Settings") if "Settings" in tabs else len(tabs)
                        self.nb.insert(settings_idx, self.tab_checkin, text='Check-In')
                except tk.TclError:
                    pass
            
            # Try to restore the previously selected tab (or closest valid tab)
            try:
                total_tabs = len(self.nb.tabs())
                if current_tab_index >= total_tabs:
                    current_tab_index = total_tabs - 1
                self.nb.select(current_tab_index)
            except tk.TclError:
                pass
        
        # Always rebuild Settings tab to update label input fields with saved values
        for widget in self.tab_settings.winfo_children():
            widget.destroy()
        self._build_settings_tab()

        self.refresh()
        
        # More informative success message
        changes_msg = []
        if old_mode != mode:
            changes_msg.append(f"Mode changed to {mode.title()}")
        if old_fields != enabled_fields:
            changes_msg.append(f"{len(enabled_fields)} fields enabled")
        
        border_status = "ON (testing mode)" if label_settings['show_border'] else "OFF (production mode)"
        changes_msg.append(f"Label borders: {border_status}")
        
        if changes_msg:
            msg = f"Settings saved and applied!\n\n" + "\n".join(f"• {c}" for c in changes_msg)
        else:
            msg = "Settings saved!"
        
        messagebox.showinfo('Saved', msg)


def main():
    root = tk.Tk()
    app = App(root)
    root.mainloop()


if __name__ == '__main__':
    main()