
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PTA Ticketing System — Dark-Mode-First, High-Contrast (Hardened Full Build)
---------------------------------------------------------------------------

Key improvements (backward compatible):
- DB: backfills missing ticket_code on legacy rows; adds index on checked_in.
- Ticket codes: unbiased secure generation; same short format (EVT-XXXXXX).
- Scanner: accepts only numeric or PREFIX-BASE36 forms; less false positives.
- Exports: include Classroom column.
- Labels: de-duplicate by (name, classroom), not just name.
- Check-in: distinct feedback for "checked now" vs "already checked", with time.
- Small UX nits: safe theme guards; optional beep on scan.

Drop-in: replace your current file. Uses your existing SQLite DB.
"""

from __future__ import annotations
import csv
import re
import secrets
import sqlite3
import string
import time
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Iterable, Optional, Dict

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# ---- Optional imports (guarded) ----
HAS_PANDAS = False
try:
    import pandas as pd  # type: ignore
    HAS_PANDAS = True
except Exception:
    pass

HAS_RL = False
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas as rl_canvas
    HAS_RL = True
except Exception:
    pass

HAS_QR = False
try:
    import qrcode  # type: ignore
    from PIL import Image
    HAS_QR = True
except Exception:
    pass

APP_TITLE = "PTA Tickets — Manager"
DB_NAME = "pta_tickets.db"

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

    def _migrate(self):
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
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(tickets)")
            cols = [r[1] for r in cur.fetchall()]
            if 'ticket_code' not in cols:
                cur.execute("ALTER TABLE tickets ADD COLUMN ticket_code TEXT")
                self.conn.commit()
        except Exception:
            pass

        # Now it's safe to create the UNIQUE index on ticket_code
        try:
            self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tickets_code ON tickets(ticket_code)")
            self.conn.commit()
        except Exception:
            pass

        # --- Add classroom column to attendees if missing ---
        try:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(attendees)")
            cols = [r[1] for r in cur.fetchall()]
            if 'classroom' not in cols:
                cur.execute("ALTER TABLE attendees ADD COLUMN classroom TEXT")
                self.conn.commit()
        except Exception:
            pass

        # --- Index for check-in filters/stats ---
        try:
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_checked ON tickets(checked_in)")
            self.conn.commit()
        except Exception:
            pass

        # --- Backfill missing ticket_code values on legacy rows ---
        try:
            self._backfill_ticket_codes()
        except Exception:
            # Non-fatal; UI will still function
            pass

    def _backfill_ticket_codes(self) -> None:
        cur = self.conn.cursor()
        evc = (self.get_setting('event_code', 'EVT') or 'EVT').strip().upper()
        cur.execute("SELECT ticket_number FROM tickets WHERE ticket_code IS NULL OR ticket_code=''")
        missing = [r[0] for r in cur.fetchall()]
        if not missing:
            return
        for tnum in missing:
            while True:
                try:
                    code = generate_ticket_code(evc)
                    cur.execute("UPDATE tickets SET ticket_code=? WHERE ticket_number=?", (code, tnum))
                    break
                except sqlite3.IntegrityError:
                    # extremely unlikely collision; try again
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

    # Attendees & Tickets
    def create_attendee_with_tickets(
        self, first: str, last: str, qty: int, event_code: Optional[str] = None, classroom: Optional[str] = None
    ) -> List[str]:
        qty = max(1, int(qty))
        cur = self.conn.cursor()
        cur.execute("INSERT INTO attendees(first_name,last_name,classroom) VALUES(?,?,?)", (first, last, classroom or ''))
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

    def list_tickets(self) -> List[Tuple]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT t.ticket_number, t.ticket_code, a.first_name, a.last_name,
                   t.printed, t.checked_in, COALESCE(t.checked_in_at,''), t.created_at,
                   COALESCE(a.classroom, '')
              FROM tickets t
              JOIN attendees a ON a.attendee_id = t.attendee_id
             ORDER BY t.ticket_number DESC
            """
        )
        return cur.fetchall()

    def delete_tickets(self, ticket_numbers: Iterable[int]) -> int:
        nums = list(ticket_numbers)
        if not nums:
            return 0
        q = ",".join(["?"] * len(nums))
        self.conn.execute(f"DELETE FROM tickets WHERE ticket_number IN ({q})", nums)
        self.conn.commit()
        return len(nums)

    def update_attendee_name_for_ticket(self, ticket_number: int, first: str, last: str, classroom: Optional[str] = None) -> None:
        cur = self.conn.cursor()
        cur.execute("SELECT attendee_id FROM tickets WHERE ticket_number=?", (ticket_number,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Ticket not found")
        self.conn.execute("UPDATE attendees SET first_name=?, last_name=?, classroom=? WHERE attendee_id=?", (first, last, classroom or '', row[0]))
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


# ============ Ticket Rendering ============
class TicketRenderer:
    def __init__(self, db: Database):
        self.db = db
        self.org = db.get_setting('organization_name', 'Joyce Kilmer Elementary PTA') or 'Joyce Kilmer Elementary PTA'
        self.event = db.get_setting('event_name', 'TRUNK OR TREAT') or 'TRUNK OR TREAT'
        self.event_code = db.get_setting('event_code', 'EVT') or 'EVT'
        self.accent = db.get_setting('ticket_color', '#ff7a00') or '#ff7a00'
        self.qr_enabled = db.get_setting('qr_enabled', '1') == '1'

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
        for tnum, tcode, first, last, printed, checked, checked_at, created, classroom in rows:
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
            if self.qr_enabled and HAS_QR and (tcode or ""):
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
        for tnum, tcode, first, last, printed, checked, checked_at, created, classroom in rows:
            html += ["<div class='t'>",
                     f"<div class='h1'>{self.org}</div>",
                     f"<div class='h2'>{self.event}</div>",
                     "<div class='lbl'>ACCESS TICKET</div>",
                     f"<div class='nr'>{tcode}</div>",
                     f"<div class='nm'>Registered: {first} {last}</div>",
                     "</div>"]
        html += ["</body></html>"]
        out_path.write_text("\n".join(html), encoding='utf-8')


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

        # Dark-mode-first palette & ttk theme
        self._init_theme()

        self._build_ui()
        self.refresh()

    def _init_theme(self):
        # Palette (dark-first)
        self.bg_main = '#0f1216'     # app background
        self.bg_frame = '#151a21'    # frames/cards
        self.fg_text = '#eaeff4'     # primary text
        self.fg_muted = '#b6c2cf'    # secondary text
        self.accent = self.db.get_setting('ticket_color', '#ff7a00') or '#ff7a00'  # bright orange
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
        import platform
        try:
            if platform.system() == 'Windows':
                try:
                    style.theme_use('vista')  # Modern Windows look
                except Exception:
                    style.theme_use('winnative')  # Fallback
                style.configure('Treeview', rowheight=24)
                style.map('Treeview', background=[('selected', self.selection_bg)],
                          foreground=[('selected', '#ffffff')])
            else:
                try:
                    style.theme_use('clam')
                except Exception:
                    pass
                style.configure('Treeview', background=self.bg_frame, fieldbackground=self.bg_frame,
                                foreground=self.fg_text, rowheight=24)
                style.map('Treeview', background=[('selected', self.selection_bg)], foreground=[('selected', '#ffffff')])
                try:
                    style.configure('Treeview.Heading', background='#1c232d', foreground=self.fg_text, relief='flat')
                    style.map('Treeview.Heading', background=[('active', self.selection_bg)])
                except Exception:
                    pass
                style.configure('TNotebook', background=self.bg_main, borderwidth=0)
                style.configure('TNotebook.Tab', background='#1c232d', foreground=self.fg_text)
                style.map('TNotebook.Tab', background=[('selected', self.bg_frame)])
        except Exception:
            pass

    def _build_ui(self):
        # Header
        self.header_frame = tk.Frame(self.root, bg=self.accent, height=64)
        self.header_frame.pack(fill='x')
        self.header_label = tk.Label(self.header_frame, text='PTA Ticket Manager', bg=self.accent, fg='#0f1216', font=('Arial', 20, 'bold'))
        self.header_label.pack(pady=12)

        # Tabs
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill='both', expand=True, padx=10, pady=10)
        self.tab_manage = tk.Frame(self.nb, bg=self.bg_main)
        self.tab_checkin = tk.Frame(self.nb, bg=self.bg_main)
        self.tab_settings = tk.Frame(self.nb, bg=self.bg_main)
        self.tab_help = tk.Frame(self.nb, bg=self.bg_main)
        self.tab_about = tk.Frame(self.nb, bg=self.bg_main)
        self.nb.add(self.tab_manage, text='Manage')
        self.nb.add(self.tab_checkin, text='Check-In')
        self.nb.add(self.tab_settings, text='Settings')
        self.nb.add(self.tab_help, text='Help')
        self.nb.add(self.tab_about, text='About')

        self._build_manage_tab()
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
        tk.Label(lf, text='Ticket Qty',  bg=self.bg_frame, fg=self.fg_text).grid(row=3, column=0, padx=8, pady=6, sticky='w')
        self.ent_first = tk.Entry(lf, width=24)
        self.ent_last = tk.Entry(lf, width=24)
        self.ent_classroom = tk.Entry(lf, width=12)
        self.ent_qty = tk.Spinbox(lf, from_=1, to=20, width=6)
        self.ent_first.grid(row=0, column=1, padx=8, pady=6)
        self.ent_last.grid(row=1, column=1, padx=8, pady=6)
        self.ent_classroom.grid(row=2, column=1, padx=8, pady=6, sticky='w')
        self.ent_qty.grid(row=3, column=1, padx=8, pady=6, sticky='w')

        btns = tk.Frame(lf, bg=self.bg_frame); btns.grid(row=4, column=0, columnspan=2, pady=8)
        # Primary (accent) - already has dark text
        tk.Button(btns, text='Generate', command=self.on_generate,
                  bg=self.accent, fg='#0f1216', activebackground=self.selection_bg, activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(side='left', padx=4)
        # Secondary - light gray with black text
        tk.Button(btns, text='Import CSV/Excel', command=self.on_import,
                  bg='#c9d5df', fg='#0f1216', activebackground='#b0bec8', activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(side='left', padx=4)
        tk.Button(btns, text='Export CSV', command=self.on_export,
                  bg='#c9d5df', fg='#0f1216', activebackground='#b0bec8', activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(side='left', padx=4)
        tk.Button(btns, text='Print Envelope Labels', command=self.on_print_labels,
                  bg='#c9d5df', fg='#0f1216', activebackground='#b0bec8', activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(side='left', padx=4)

        table = tk.LabelFrame(frm, text='Tickets', bg=self.bg_frame, fg=self.fg_text)
        table.pack(fill='both', expand=True, padx=8, pady=8)
        cols = ('Ticket ID', 'First', 'Last', 'Room', 'Printed', 'Checked In', 'Checked At', 'Created')
        self.tree = ttk.Treeview(table, columns=cols, show='headings', height=14)
        for c in cols:
            self.tree.heading(c, text=c)
        widths = [120, 120, 120, 60, 80, 90, 140, 140]
        for c, w in zip(cols, widths):
            self.tree.column(c, width=w, anchor='center')
        vsb = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        fbar = tk.Frame(frm, bg=self.bg_main); fbar.pack(fill='x', padx=8, pady=(0, 8))
        tk.Label(fbar, text='Filter:', bg=self.bg_main, fg=self.fg_text).pack(side='left')
        self.filter_var = tk.StringVar(); tk.Entry(fbar, textvariable=self.filter_var, width=32).pack(side='left', padx=6)
        self.filter_var.trace_add('write', lambda *_: self.apply_filter())
        # Edit and Delete - light backgrounds with black text
        tk.Button(fbar, text='Edit', command=self.on_edit,
                  bg='#c9d5df', fg='#0f1216', activebackground='#b0bec8', activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(side='left', padx=4)
        tk.Button(fbar, text='Delete', command=self.on_delete,
                  bg='#ffb3b3', fg='#0f1216', activebackground='#ff9999', activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(side='left', padx=4)
        # Primary on right - already has dark text
        tk.Button(fbar, text='Print Selected', command=self.on_print_selected,
                  bg=self.accent, fg='#0f1216', activebackground=self.selection_bg, activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(side='right', padx=4)
        tk.Button(fbar, text='Print All Unprinted', command=self.on_print_all_unprinted,
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

        # Map tree item -> internal ticket_number
        self._tree_num_by_item: Dict[str, int] = {}

    # ---- Check-In Tab ----
    def _build_checkin_tab(self):
        frm = self.tab_checkin
        box = tk.LabelFrame(frm, text='Scan / Enter Ticket ID', bg=self.bg_frame, fg=self.fg_text)
        box.pack(padx=8, pady=12, fill='x')
        self.checkin_var = tk.StringVar()
        ent = tk.Entry(box, textvariable=self.checkin_var, font=('Arial', 16), width=18)
        ent.pack(padx=8, pady=10); ent.focus_set()
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
        box = tk.LabelFrame(frm, text='Event Settings', bg=self.bg_frame, fg=self.fg_text)
        box.pack(padx=8, pady=12, fill='x')

        # Organization Name (now editable)
        tk.Label(box, text='Organization Name:', bg=self.bg_frame, fg=self.fg_text).grid(row=0, column=0, padx=8, pady=6, sticky='w')
        self.var_org = tk.StringVar(value=self.db.get_setting('organization_name', 'Joyce Kilmer Elementary PTA') or 'Joyce Kilmer Elementary PTA')
        tk.Entry(box, textvariable=self.var_org, width=30).grid(row=0, column=1, padx=8, pady=6, sticky='w')

        tk.Label(box, text='Event Name:', bg=self.bg_frame, fg=self.fg_text).grid(row=1, column=0, padx=8, pady=6, sticky='w')
        self.var_event = tk.StringVar(value=self.db.get_setting('event_name', 'TRUNK OR TREAT') or 'TRUNK OR TREAT')
        tk.Entry(box, textvariable=self.var_event, width=30).grid(row=1, column=1, padx=8, pady=6, sticky='w')

        tk.Label(box, text='Event Code (prefix):', bg=self.bg_frame, fg=self.fg_text).grid(row=2, column=0, padx=8, pady=6, sticky='w')
        self.var_event_code = tk.StringVar(value=self.db.get_setting('event_code', 'EVT') or 'EVT')
        tk.Entry(box, textvariable=self.var_event_code, width=10).grid(row=2, column=1, padx=8, pady=6, sticky='w')

        # Accent Color with picker button
        tk.Label(box, text='Accent Color:', bg=self.bg_frame, fg=self.fg_text).grid(row=3, column=0, padx=8, pady=6, sticky='w')
        color_frame = tk.Frame(box, bg=self.bg_frame)
        color_frame.grid(row=3, column=1, padx=8, pady=6, sticky='w')
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
        tk.Label(box, text='Include QR Codes:', bg=self.bg_frame, fg=self.fg_text).grid(row=4, column=0, padx=8, pady=6, sticky='w')
        self.var_qr_enabled = tk.BooleanVar(value=self.db.get_setting('qr_enabled', '1') == '1')
        chk = tk.Checkbutton(box, variable=self.var_qr_enabled, bg=self.bg_frame, fg=self.fg_text,
                             selectcolor=self.bg_frame, activebackground=self.bg_frame)
        chk.grid(row=4, column=1, padx=8, pady=6, sticky='w')

        tk.Button(box, text='Save', command=self.on_save_settings,
                  bg=self.accent, fg='#0f1216', activebackground=self.selection_bg, activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).grid(row=5, column=0, columnspan=2, pady=8)

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

        optional_text = """• Classroom (or Room, Class) - Room number for label printing"""

        tk.Label(csv_box, text=optional_text, bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10), justify='left').pack(anchor='w', padx=30, pady=5)

        tk.Label(csv_box, text='Example CSV Format:', bg=self.bg_frame, fg=self.accent, font=('Arial', 11, 'bold')).pack(anchor='w', padx=15, pady=(15, 5))

        example_frame = tk.Frame(csv_box, bg='#1c232d', relief='solid', borderwidth=1)
        example_frame.pack(padx=30, pady=(5, 15), fill='x')

        example_text = """Quantity,Student Name,Classroom
2,Julia McSweeney,101
2,Haley DiPaolo,202
4,Emmett Potts,101
1,Felix Dambach,204"""

        tk.Label(example_frame, text=example_text, bg='#1c232d', fg='#c9d5df', font=('Courier', 9), justify='left').pack(padx=10, pady=10, anchor='w')

        tk.Label(csv_box, text='Note: Column names are case-insensitive. Classroom is optional.',
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
• Event name (from Settings)

Labels are deduplicated - one label per (student, room), regardless of ticket quantity."""

        tk.Label(label_box, text=printed_text, bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10), justify='left').pack(anchor='w', padx=30, pady=(5, 15))

        # Quick Tips
        tips_box = tk.LabelFrame(content, text='Quick Tips', bg=self.bg_frame, fg=self.fg_text, font=('Arial', 12, 'bold'))
        tips_box.pack(padx=20, pady=20, fill='x')

        tips_text = """• Import your CSV first, then print tickets and labels
• Tickets show name only (privacy)
• Labels show name + room (for distribution)
• Use Filter box to search tickets by name or room
• Check-In accepts QR codes or ticket IDs
• Export CSV anytime to get attendance reports"""

        tk.Label(tips_box, text=tips_text, bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10), justify='left').pack(anchor='w', padx=30, pady=15)

    # ---- About Tab ----
    def _build_about_tab(self):
        frm = self.tab_about

        # Center container
        container = tk.Frame(frm, bg=self.bg_main)
        container.pack(expand=True)

        # App info
        tk.Label(container, text='PTA Ticket Manager', bg=self.bg_main, fg=self.accent,
                 font=('Arial', 24, 'bold')).pack(pady=(20, 10))

        tk.Label(container, text='Version 1.1', bg=self.bg_main, fg=self.fg_muted,
                 font=('Arial', 12)).pack(pady=5)

        tk.Label(container, text='A professional ticketing system for school events', bg=self.bg_main, fg=self.fg_text,
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
            '✓ Customizable branding and colors'
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

        tk.Label(container, text='Built with ❤️ for PTAs everywhere', bg=self.bg_main, fg=self.fg_muted,
                 font=('Arial', 10, 'italic')).pack(pady=(20, 40))

    def _open_email(self):
        """Open default email client."""
        import webbrowser
        webbrowser.open('mailto:him@mattgrilli.com')

    # ============ Actions ============
    def refresh(self):
        # table reload
        self._tree_num_by_item.clear()
        for it in self.tree.get_children():
            self.tree.delete(it)
        for r in self.db.list_tickets():
            tnum, tcode, f, l, pr, ch, cha, cr, classroom = r
            iid = self.tree.insert('', 'end', values=(tcode or '', f, l, classroom or '', 'Yes' if pr else 'No', 'Yes' if ch else 'No', cha, cr))
            self._tree_num_by_item[iid] = tnum
        total, printed, unprinted, checked = self.db.stats()
        self.stats_lbl.config(text=f"Total Tickets: {total}  |  Printed: {printed}  |  Unprinted: {unprinted}  |  Checked-In: {checked}")
        self.apply_filter()

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

    def on_generate(self):
        first = self.ent_first.get().strip(); last = self.ent_last.get().strip()
        classroom = self.ent_classroom.get().strip()
        try:
            qty = int(self.ent_qty.get())
        except Exception:
            qty = 1
        if not first or not last:
            messagebox.showwarning('Missing Info', 'Please provide first and last name.')
            return
        codes = self.db.create_attendee_with_tickets(first, last, qty, classroom=classroom or None)
        if len(codes) == 1:
            message = f"Created ticket ID {codes[0]} for {first} {last}."
        else:
            message = f"Created {len(codes)} tickets ({codes[0]} … {codes[-1]}) for {first} {last}."
        messagebox.showinfo('Success', message)
        self.ent_first.delete(0, 'end'); self.ent_last.delete(0, 'end'); self.ent_classroom.delete(0, 'end'); self.ent_qty.delete(0, 'end'); self.ent_qty.insert(0, '1')
        self.refresh()

    def _selected_nums(self) -> List[int]:
        nums: List[int] = []
        for iid in self.tree.selection():
            num = self._tree_num_by_item.get(iid)
            if num is not None:
                nums.append(num)
        return nums

    def on_edit(self):
        sels = self.tree.selection()
        if len(sels) != 1:
            messagebox.showwarning('Select One', 'Select exactly one ticket to edit.')
            return
        iid = sels[0]
        v = self.tree.item(iid)['values']
        tnum = self._tree_num_by_item.get(iid)
        if tnum is None:
            messagebox.showerror('Error', 'Could not find selected ticket.'); return
        tcode, first, last, classroom = v[0], v[1], v[2], v[3]
        dlg = tk.Toplevel(self.root); dlg.title(f'Edit Ticket {tcode}')
        dlg.configure(bg=self.bg_frame)
        tk.Label(dlg, text=f'Ticket ID: {tcode}', bg=self.bg_frame, fg=self.fg_text, font=('Arial', 12, 'bold')).pack(pady=8)
        frm = tk.Frame(dlg, bg=self.bg_frame); frm.pack(padx=12, pady=8)
        tk.Label(frm, text='First', bg=self.bg_frame, fg=self.fg_text).grid(row=0, column=0, padx=6, pady=6)
        tk.Label(frm, text='Last',  bg=self.bg_frame, fg=self.fg_text).grid(row=1, column=0, padx=6, pady=6)
        tk.Label(frm, text='Classroom',  bg=self.bg_frame, fg=self.fg_text).grid(row=2, column=0, padx=6, pady=6)
        e1 = tk.Entry(frm); e2 = tk.Entry(frm); e3 = tk.Entry(frm)
        e1.insert(0, first); e2.insert(0, last); e3.insert(0, classroom or '')
        e1.grid(row=0, column=1, padx=6, pady=6); e2.grid(row=1, column=1, padx=6, pady=6); e3.grid(row=2, column=1, padx=6, pady=6)
        def save():
            nf, nl, nc = e1.get().strip(), e2.get().strip(), e3.get().strip()
            if not nf or not nl:
                messagebox.showwarning('Missing', 'Fill name fields'); return
            self.db.update_attendee_name_for_ticket(tnum, nf, nl, nc or None)
            dlg.destroy(); self.refresh(); messagebox.showinfo('Saved', 'Updated.')
        tk.Button(dlg, text='Save', command=save,
                  bg=self.accent, fg='#0f1216', activebackground=self.selection_bg, activeforeground='#0f1216', takefocus=0, relief='flat', bd=0, highlightthickness=0).pack(pady=6)
        tk.Button(dlg, text='Cancel', command=dlg.destroy,
                  bg=self.btn_secondary, fg=self.fg_text, activebackground=self.btn_secondary_active, activeforeground=self.fg_text, takefocus=0, relief='flat', bd=0, highlightthickness=0).pack()

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

    def _split_name(self, full_name: str) -> Tuple[str, str]:
        """Split a full name into first and last names. Handles multiple names gracefully."""
        parts = full_name.strip().split()
        if not parts:
            return '', ''
        if len(parts) == 1:
            return parts[0], ''
        return ' '.join(parts[:-1]), parts[-1]

    def _save_output_dir(self) -> Path:
        out = self.data_dir / 'Tickets'; out.mkdir(parents=True, exist_ok=True); return out

    def _export_tickets(self, rows: List[Tuple]) -> Optional[Path]:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_dir = self._save_output_dir()
        if HAS_RL:
            out_path = out_dir / f'tickets_{ts}.pdf'
            try:
                self.renderer.generate_pdf(rows, out_path); return out_path
            except Exception as e:
                messagebox.showwarning('PDF Error', f'Falling back to HTML: {e}')
        out_path = out_dir / f'tickets_{ts}.html'
        self.renderer.generate_html(rows, out_path); return out_path

    def _post_print_prompt(self, nums: List[int], out_path: Path):
        import webbrowser
        if messagebox.askyesno('Open / Mark Printed', f'Saved to:\n{out_path}\n\nOpen now and mark as Printed?'):
            try:
                webbrowser.open(out_path.as_uri())
            except Exception:
                pass
            self.db.mark_printed(nums, 1); self.refresh()
        else:
            messagebox.showinfo('Not Marked', 'Tickets not marked as printed.')

    def on_print_selected(self):
        nums = self._selected_nums()
        if not nums:
            messagebox.showwarning('No Selection', 'Select tickets to print.'); return
        rows = self._tickets_by_numbers(nums)
        out = self._export_tickets(rows)
        if out: self._post_print_prompt(nums, out)

    def on_print_all_unprinted(self):
        nums = self.db.unprinted_ticket_numbers()
        if not nums:
            messagebox.showinfo('All Set', 'No unprinted tickets.'); return
        rows = self._tickets_by_numbers(nums)
        out = self._export_tickets(rows)
        if out: self._post_print_prompt(nums, out)

    def on_print_labels(self):
        """Generate Avery 5160 labels (30 per sheet) with student names for envelopes."""
        if not HAS_RL:
            messagebox.showerror('Missing Library', 'ReportLab required for PDF labels.\nInstall: pip install reportlab')
            return

        rows = self.db.list_tickets()
        if not rows:
            messagebox.showinfo('No Tickets', 'No tickets to print labels for.')
            return

        # Group by attendee AND classroom to avoid collapsing same-name students in different rooms
        attendees = {}  # {(name, classroom): True}
        for _tnum, _tcode, first, last, _printed, _checked, _checked_at, _created, classroom in rows:
            name = f"{first} {last}".strip()
            key = (name, classroom or '')
            if key not in attendees:
                attendees[key] = True

        if not attendees:
            messagebox.showinfo('No Data', 'No valid attendee names found.')
            return

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_dir = self._save_output_dir()
        out_path = out_dir / f'envelope_labels_{ts}.pdf'

        try:
            self._generate_avery_5160_labels(list(attendees.keys()), out_path)
            import webbrowser
            if messagebox.askyesno('Labels Ready', f'Generated {len(attendees)} labels.\n\nSaved to:\n{out_path}\n\nOpen now?'):
                try:
                    webbrowser.open(out_path.as_uri())
                except Exception:
                    pass
        except Exception as e:
            messagebox.showerror('Error', f'Failed to generate labels:\n{e}')

    def _generate_avery_5160_labels(self, attendee_keys: List[Tuple[str, str]], out_path: Path):
        """Generate Avery 5160 format labels (3 columns x 10 rows = 30 per page).
        attendee_keys: list of (name, classroom)
        """
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas as rl_canvas

        # Avery 5160 specs (in inches)
        page_width, page_height = letter
        label_width = 2.625 * inch
        label_height = 1.0 * inch
        left_margin = 0.21975 * inch  # ~0.22"
        top_margin = 0.5 * inch
        horizontal_gap = 0.125 * inch
        vertical_gap = 0.0 * inch

        cols = 3
        rows = 10
        labels_per_page = cols * rows

        c = rl_canvas.Canvas(str(out_path), pagesize=letter)

        for idx, (name, classroom) in enumerate(attendee_keys):
            page_num = idx // labels_per_page
            label_on_page = idx % labels_per_page

            row = label_on_page // cols
            col = label_on_page % cols

            # Calculate position
            x = left_margin + col * (label_width + horizontal_gap)
            y = page_height - top_margin - (row + 1) * label_height - row * vertical_gap

            # Draw label content (centered text)
            text_x = x + label_width / 2

            # Name at top
            c.setFont('Helvetica-Bold', 12)
            text_y = y + label_height / 2 + 12
            c.drawCentredString(text_x, text_y, name)

            # Classroom in middle (if exists)
            if classroom:
                c.setFont('Helvetica', 9)
                c.drawCentredString(text_x, text_y - 16, f"Room {classroom}" if not classroom.lower().startswith('room') else classroom)

            # Event name at bottom
            c.setFont('Helvetica', 8)
            bottom_y = text_y - 28 if classroom else text_y - 16
            c.drawCentredString(text_x, bottom_y, self.db.get_setting('event_name', 'TRUNK OR TREAT'))

            # New page when needed
            if (idx + 1) % labels_per_page == 0 and idx + 1 < len(attendee_keys):
                c.showPage()

        c.save()

    def on_export(self):
        rows = self.db.list_tickets()
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        default = self._save_output_dir() / f'ticket_list_{ts}.csv'
        fname = filedialog.asksaveasfilename(title='Export CSV', defaultextension='.csv', initialfile=default.name,
                                             filetypes=[('CSV', '*.csv'), ('All', '*.*')])
        if not fname:
            return
        with open(fname, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['Ticket ID', 'First Name', 'Last Name', 'Classroom', 'Printed', 'Checked In', 'Checked In At', 'Created At'])
            for tnum, tcode, fst, lst, pr, ch, cha, cr, classroom in rows:
                w.writerow([tcode, fst, lst, classroom, 'Yes' if pr else 'No', 'Yes' if ch else 'No', cha, cr])
        messagebox.showinfo('Exported', f'Saved: {fname}')

    def on_export_checkins(self):
        rows = self.db.list_tickets()
        # Filter to only checked-in tickets
        checked_in_rows = [r for r in rows if r[5] == 1]  # r[5] is checked_in column

        if not checked_in_rows:
            messagebox.showinfo('No Check-Ins', 'No tickets have been checked in yet.')
            return

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        default = self._save_output_dir() / f'checkins_{ts}.csv'
        fname = filedialog.asksaveasfilename(title='Export Check-Ins', defaultextension='.csv', initialfile=default.name,
                                             filetypes=[('CSV', '*.csv'), ('All', '*.*')])
        if not fname:
            return

        with open(fname, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['Ticket ID', 'First Name', 'Last Name', 'Classroom', 'Checked In At'])
            for tnum, tcode, fst, lst, pr, ch, cha, cr, classroom in checked_in_rows:
                w.writerow([tcode, fst, lst, classroom, cha])

        messagebox.showinfo('Exported', f'Saved {len(checked_in_rows)} check-ins to:\n{fname}')

    def on_import(self):
        pth = filedialog.askopenfilename(title='Import CSV/Excel', filetypes=[('CSV', '*.csv'), ('Excel', '*.xlsx *.xls'), ('All', '*.*')])
        if not pth:
            return
        p = Path(pth); rows: List[Tuple[str, str, int, str]] = []
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
                        rows.append((first, last, qty, classroom))
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

                    rows.append((first, last, qty, classroom))
        except Exception as e:
            messagebox.showerror('Import Error', f'Could not read file:\n{e}'); return
        if not rows:
            messagebox.showwarning('No Rows', 'No valid rows found.'); return
        created = 0
        for f, l, q, c in rows:
            self.db.create_attendee_with_tickets(f, l, q, classroom=c); created += q
        self.refresh(); messagebox.showinfo('Imported', f'Imported {created} tickets from {p.name}.')

    def on_checkin(self):
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
            import platform
            if status in ('checked_in', 'already'):
                if platform.system() == 'Windows':
                    import winsound  # type: ignore
                    winsound.MessageBeep()
                else:
                    self.root.bell()
        except Exception:
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

    def _update_color_preview(self):
        """Update the color preview box when hex value changes."""
        try:
            color = self.var_color.get().strip()
            if not color.startswith('#'):
                color = '#' + color
            # Validate hex color
            if len(color) == 7 and all(c in '0123456789ABCDEFabcdef' for c in color[1:]):
                self.color_preview.config(bg=color)
        except Exception:
            pass

    def on_pick_color(self):
        """Open color picker dialog."""
        from tkinter import colorchooser
        current_color = self.var_color.get().strip()
        color = colorchooser.askcolor(color=current_color, title="Choose Accent Color")
        if color and color[1]:  # color is ((r,g,b), '#hexcode')
            self.var_color.set(color[1])
            self.color_preview.config(bg=color[1])

    def on_save_settings(self):
        org = (self.var_org.get() or 'Joyce Kilmer Elementary PTA').strip()
        ev = (self.var_event.get() or 'TRUNK OR TREAT').strip()
        evc = (self.var_event_code.get() or 'EVT').strip().upper()
        col = (self.var_color.get() or '#ff7a00').strip()
        qr_enabled = '1' if self.var_qr_enabled.get() else '0'
        self.db.set_setting('organization_name', org)
        self.db.set_setting('event_name', ev)
        self.db.set_setting('event_code', evc)
        self.db.set_setting('ticket_color', col)
        self.db.set_setting('qr_enabled', qr_enabled)
        self.renderer = TicketRenderer(self.db)
        self.accent = col

        # Update header color immediately
        self.header_frame.config(bg=col)
        self.header_label.config(bg=col)

        messagebox.showinfo('Saved', 'Settings updated. Header color changed instantly!')


def main():
    root = tk.Tk()
    app = App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
