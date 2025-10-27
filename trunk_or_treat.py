import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
import os
import sys

class TrunkOrTreatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎃 Trunk or Treat - Ticket Manager 👻")
        self.root.geometry("900x700")
        
        # Detect dark mode (works on macOS)
        self.is_dark_mode = self.detect_dark_mode()
        
        # Set color scheme based on mode
        if self.is_dark_mode:
            self.bg_main = '#2b1810'  # Dark brown
            self.bg_frame = '#3d2415'  # Lighter dark brown
            self.bg_header = '#d2691e'  # Chocolate orange (more visible on dark)
            self.fg_text = '#ffd700'  # Gold text
            self.fg_secondary = '#ffb347'  # Light orange
            self.button_bg = '#ff6600'  # Bright orange
            self.button_secondary = '#8b4513'  # Saddle brown
            self.button_active = '#4d4d4d'  # Dark gray for active state
        else:
            self.bg_main = '#ff8c00'  # Original orange
            self.bg_frame = '#ffb347'  # Original light orange
            self.bg_header = '#ff6600'  # Original dark orange
            self.fg_text = '#4d2600'  # Dark brown
            self.fg_secondary = '#4d2600'
            self.button_bg = '#4d2600'
            self.button_secondary = '#ff6600'
            self.button_active = '#4d4d4d'  # Dark gray for active state
        
        self.root.configure(bg=self.bg_main)
        
        # Initialize database
        self.init_database()
        
        # Create UI
        self.create_widgets()
        self.refresh_table()
    
    def detect_dark_mode(self):
        """Detect if system is in dark mode (macOS)"""
        try:
            # Try to detect macOS dark mode
            if sys.platform == 'darwin':  # macOS
                import subprocess
                result = subprocess.run(
                    ['defaults', 'read', '-g', 'AppleInterfaceStyle'],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0 and 'Dark' in result.stdout
        except:
            pass
        return False
        
    def init_database(self):
        """Initialize SQLite database"""
        self.conn = sqlite3.connect('trunk_or_treat.db')
        self.cursor = self.conn.cursor()
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendees (
                ticket_number INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                num_tickets INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                printed BOOLEAN DEFAULT 0
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        # Set default settings if they don't exist
        defaults = {
            'organization_name': 'Joyce Kilmer Elementary PTA',
            'event_name': 'TRUNK OR TREAT',
            'ticket_emoji_1': '🎃',
            'ticket_emoji_2': '👻',
            'ticket_emoji_3': '🍬',
            'ticket_color': '#ff6600',
            'ticket_bg_gradient_start': '#fff5e6',
            'ticket_bg_gradient_end': '#ffe6cc'
        }
        
        for key, value in defaults.items():
            self.cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
            if not self.cursor.fetchone():
                self.cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))
            
        self.conn.commit()
        
    def get_setting(self, key, default=''):
        """Get a setting value"""
        self.cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        result = self.cursor.fetchone()
        return result[0] if result else default
    
    def set_setting(self, key, value):
        """Set a setting value"""
        self.cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()
        
    def create_widgets(self):
        """Create the UI components"""
        
        # Header
        header_frame = tk.Frame(self.root, bg=self.bg_header, height=80)
        header_frame.pack(fill='x', pady=(0, 10))
        
        title_label = tk.Label(
            header_frame, 
            text="🎃 TRUNK OR TREAT TICKET SYSTEM 🍬",
            font=('Arial', 24, 'bold'),
            bg=self.bg_header,
            fg='white'
        )
        title_label.pack(pady=20)
        
        # Input Frame
        input_frame = tk.LabelFrame(
            self.root,
            text="👻 Register Participant",
            font=('Arial', 14, 'bold'),
            bg=self.bg_frame,
            fg=self.fg_text,
            padx=20,
            pady=20
        )
        input_frame.pack(padx=20, pady=10, fill='x')
        
        # First Name
        tk.Label(input_frame, text="First Name:", bg=self.bg_frame, fg=self.fg_text, font=('Arial', 11)).grid(row=0, column=0, sticky='w', pady=5)
        self.first_name_entry = tk.Entry(input_frame, font=('Arial', 11), width=25)
        self.first_name_entry.grid(row=0, column=1, padx=10, pady=5)
        
        # Last Name
        tk.Label(input_frame, text="Last Name:", bg=self.bg_frame, fg=self.fg_text, font=('Arial', 11)).grid(row=1, column=0, sticky='w', pady=5)
        self.last_name_entry = tk.Entry(input_frame, font=('Arial', 11), width=25)
        self.last_name_entry.grid(row=1, column=1, padx=10, pady=5)
        
        # Number of Tickets
        tk.Label(input_frame, text="Number of Tickets:", bg=self.bg_frame, fg=self.fg_text, font=('Arial', 11)).grid(row=2, column=0, sticky='w', pady=5)
        self.num_tickets_spinbox = tk.Spinbox(input_frame, from_=1, to=10, font=('Arial', 11), width=23)
        self.num_tickets_spinbox.grid(row=2, column=1, padx=10, pady=5)
        
        # Buttons frame
        btn_container = tk.Frame(input_frame, bg=self.bg_frame)
        btn_container.grid(row=3, column=0, columnspan=2, pady=15)
        
        # Add Button
        add_btn = tk.Button(
            btn_container,
            text="🎟️ Generate Tickets",
            command=self.add_attendee,
            bg=self.button_secondary,
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=20,
            pady=10,
            relief='raised',
            borderwidth=2,
            activebackground=self.button_active,
            activeforeground='white'
        )
        add_btn.pack(side='left', padx=5)
        
        # Import Button
        import_btn = tk.Button(
            btn_container,
            text="📥 Import from CSV/Excel",
            command=self.import_file,
            bg=self.button_bg,
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=20,
            pady=10,
            relief='raised',
            borderwidth=2,
            activebackground=self.button_active,
            activeforeground='white'
        )
        import_btn.pack(side='left', padx=5)
        
        # Table Frame
        table_frame = tk.LabelFrame(
            self.root,
            text="🎫 Participant Registry (Internal Use)",
            font=('Arial', 14, 'bold'),
            bg=self.bg_frame,
            fg=self.fg_text,
            padx=10,
            pady=10
        )
        table_frame.pack(padx=20, pady=10, fill='both', expand=True)
        
        # Treeview
        columns = ('Ticket #', 'First Name', 'Last Name', 'Qty', 'Created', 'Printed')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=12)
        
        # Define headings
        self.tree.heading('Ticket #', text='Ticket #')
        self.tree.heading('First Name', text='First Name')
        self.tree.heading('Last Name', text='Last Name')
        self.tree.heading('Qty', text='Qty')
        self.tree.heading('Created', text='Created')
        self.tree.heading('Printed', text='Printed')
        
        # Define column widths
        self.tree.column('Ticket #', width=100)
        self.tree.column('First Name', width=120)
        self.tree.column('Last Name', width=120)
        self.tree.column('Qty', width=60)
        self.tree.column('Created', width=120)
        self.tree.column('Printed', width=80)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Button Frame
        btn_frame = tk.Frame(self.root, bg=self.bg_main)
        btn_frame.pack(padx=20, pady=10, fill='x')
        
        # Left side - CRUD operations
        crud_frame = tk.Frame(btn_frame, bg=self.bg_main)
        crud_frame.pack(side='left')
        
        edit_btn = tk.Button(
            crud_frame,
            text="✏️ Edit Selected",
            command=self.edit_selected,
            bg=self.button_secondary,
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=15,
            pady=8,
            relief='raised',
            borderwidth=2,
            activebackground=self.button_active,
            activeforeground='white'
        )
        edit_btn.pack(side='left', padx=5)
        
        delete_btn = tk.Button(
            crud_frame,
            text="🗑️ Delete Selected",
            command=self.delete_selected,
            bg='#CC0000',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=15,
            pady=8,
            relief='raised',
            borderwidth=2,
            activebackground='#8B0000',
            activeforeground='white'
        )
        delete_btn.pack(side='left', padx=5)
        
        export_btn = tk.Button(
            crud_frame,
            text="📤 Export to CSV",
            command=self.export_to_csv,
            bg=self.button_secondary,
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=15,
            pady=8,
            relief='raised',
            borderwidth=2,
            activebackground=self.button_active,
            activeforeground='white'
        )
        export_btn.pack(side='left', padx=5)
        
        # Right side - Print operations
        print_frame = tk.Frame(btn_frame, bg=self.bg_main)
        print_frame.pack(side='right')
        
        settings_btn = tk.Button(
            print_frame,
            text="⚙️ Settings",
            command=self.show_settings,
            bg=self.button_secondary,
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=15,
            pady=8,
            relief='raised',
            borderwidth=2,
            activebackground=self.button_active,
            activeforeground='white'
        )
        settings_btn.pack(side='left', padx=5)
        
        print_selected_btn = tk.Button(
            print_frame,
            text="🖨️ Print Selected",
            command=self.print_selected,
            bg=self.button_bg,
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=15,
            pady=8,
            relief='raised',
            borderwidth=2,
            activebackground=self.button_active,
            activeforeground='white'
        )
        print_selected_btn.pack(side='left', padx=5)
        
        print_all_btn = tk.Button(
            print_frame,
            text="🖨️ Print All Unprinted",
            command=self.print_all_unprinted,
            bg=self.button_bg,
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=15,
            pady=8,
            relief='raised',
            borderwidth=2,
            activebackground=self.button_active,
            activeforeground='white'
        )
        print_all_btn.pack(side='left', padx=5)
        
        refresh_btn = tk.Button(
            print_frame,
            text="🔄 Refresh",
            command=self.refresh_table,
            bg=self.button_secondary,
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=15,
            pady=8,
            relief='raised',
            borderwidth=2,
            activebackground=self.button_active,
            activeforeground='white'
        )
        refresh_btn.pack(side='left', padx=5)
        
        # Stats Label
        self.stats_label = tk.Label(
            self.root,
            text="",
            bg=self.bg_main,
            fg=self.fg_secondary,
            font=('Arial', 11, 'bold')
        )
        self.stats_label.pack(pady=5)
        
    def add_attendee(self):
        """Add a new attendee to the database with multiple tickets"""
        first_name = self.first_name_entry.get().strip()
        last_name = self.last_name_entry.get().strip()
        num_tickets = int(self.num_tickets_spinbox.get())
        
        if not all([first_name, last_name]):
            messagebox.showwarning("Missing Information", "Please fill in first and last name!")
            return
        
        try:
            ticket_numbers = []
            
            # Generate multiple tickets for this person
            for i in range(num_tickets):
                self.cursor.execute('''
                    INSERT INTO attendees (first_name, last_name, num_tickets)
                    VALUES (?, ?, ?)
                ''', (first_name, last_name, num_tickets))
                self.conn.commit()
                ticket_numbers.append(self.cursor.lastrowid)
            
            if num_tickets == 1:
                msg = f"🎉 TICKET #{ticket_numbers[0]:05d}\n\nGenerated for: {first_name} {last_name}"
            else:
                ticket_range = f"#{ticket_numbers[0]:05d} - #{ticket_numbers[-1]:05d}"
                msg = f"🎉 {num_tickets} TICKETS GENERATED!\n\n{ticket_range}\n\nFor: {first_name} {last_name}"
            
            messagebox.showinfo("Tickets Generated!", msg)
            
            # Clear entries
            self.first_name_entry.delete(0, tk.END)
            self.last_name_entry.delete(0, tk.END)
            self.num_tickets_spinbox.delete(0, tk.END)
            self.num_tickets_spinbox.insert(0, "1")
            
            self.refresh_table()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error adding attendee: {e}")
    
    def refresh_table(self):
        """Refresh the attendee table"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        self.cursor.execute('SELECT * FROM attendees ORDER BY ticket_number DESC')
        rows = self.cursor.fetchall()
        
        for row in rows:
            ticket, first, last, qty, created, printed = row
            printed_status = "✓ Yes" if printed else "✗ No"
            created_date = created.split()[0] if created else ""
            
            self.tree.insert('', 'end', values=(
                f"#{ticket:05d}",
                first,
                last,
                qty,
                created_date,
                printed_status
            ))
        
        # Update stats
        total = len(rows)
        printed = sum(1 for row in rows if row[5])
        unprinted = total - printed
        self.stats_label.config(text=f"📊 Total Tickets: {total} | Printed: {printed} | Unprinted: {unprinted}")
    
    def import_file(self):
        """Import attendees from CSV or Excel file"""
        from tkinter import filedialog
        
        filename = filedialog.askopenfilename(
            title="Select CSV or Excel file",
            filetypes=[
                ("CSV files", "*.csv"),
                ("Excel files", "*.xlsx *.xls"),
                ("All files", "*.*")
            ]
        )
        
        if not filename:
            return
        
        try:
            import pandas as pd
            
            # Read file based on extension
            if filename.lower().endswith('.csv'):
                df = pd.read_csv(filename)
            elif filename.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(filename)
            else:
                messagebox.showerror("Error", "Unsupported file type. Please use CSV or Excel files.")
                return
            
            # Show column mapping dialog
            self.show_column_mapping_dialog(df)
            
        except ImportError:
            messagebox.showerror(
                "Missing Library",
                "Please install required libraries:\n\npip install pandas openpyxl --break-system-packages"
            )
        except Exception as e:
            messagebox.showerror("Import Error", f"Error reading file:\n{str(e)}")
    
    def show_column_mapping_dialog(self, df):
        """Show dialog to map columns and preview data for selective import"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Import Preview & Selection")
        dialog.geometry("800x600")
        dialog.configure(bg=self.bg_frame)
        
        tk.Label(
            dialog,
            text="Step 1: Map your spreadsheet columns",
            font=('Arial', 12, 'bold'),
            bg=self.bg_frame,
            fg=self.fg_text
        ).pack(pady=10)
        
        # Get column names from dataframe
        columns = ['-- Skip --'] + list(df.columns)
        
        # Frame for mappings
        map_frame = tk.Frame(dialog, bg=self.bg_frame)
        map_frame.pack(pady=5, padx=20)
        
        # First Name mapping
        tk.Label(map_frame, text="First Name:", bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10)).grid(row=0, column=0, sticky='w', pady=3, padx=5)
        first_name_var = tk.StringVar(value=columns[1] if len(columns) > 1 else columns[0])
        first_name_combo = ttk.Combobox(map_frame, textvariable=first_name_var, values=columns, width=20, state='readonly')
        first_name_combo.grid(row=0, column=1, pady=3, padx=5)
        
        # Last Name mapping
        tk.Label(map_frame, text="Last Name:", bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10)).grid(row=0, column=2, sticky='w', pady=3, padx=5)
        last_name_var = tk.StringVar(value=columns[2] if len(columns) > 2 else columns[0])
        last_name_combo = ttk.Combobox(map_frame, textvariable=last_name_var, values=columns, width=20, state='readonly')
        last_name_combo.grid(row=0, column=3, pady=3, padx=5)
        
        # Quantity mapping (optional)
        tk.Label(map_frame, text="Quantity (optional):", bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10)).grid(row=0, column=4, sticky='w', pady=3, padx=5)
        qty_var = tk.StringVar(value='-- Skip --')
        qty_combo = ttk.Combobox(map_frame, textvariable=qty_var, values=columns, width=15, state='readonly')
        qty_combo.grid(row=0, column=5, pady=3, padx=5)
        
        # Preview section
        tk.Label(
            dialog,
            text="Step 2: Select which participants to import (check boxes)",
            font=('Arial', 12, 'bold'),
            bg=self.bg_frame,
            fg=self.fg_text
        ).pack(pady=10)
        
        # Create frame for tree and scrollbar
        tree_frame = tk.Frame(dialog, bg=self.bg_frame)
        tree_frame.pack(pady=5, padx=20, fill='both', expand=True)
        
        # Create treeview for preview with checkboxes
        preview_tree = ttk.Treeview(tree_frame, columns=('Select', 'First', 'Last', 'Qty'), show='headings', height=15)
        preview_tree.heading('Select', text='✓')
        preview_tree.heading('First', text='First Name')
        preview_tree.heading('Last', text='Last Name')
        preview_tree.heading('Qty', text='Qty')
        
        preview_tree.column('Select', width=40)
        preview_tree.column('First', width=150)
        preview_tree.column('Last', width=150)
        preview_tree.column('Qty', width=50)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=preview_tree.yview)
        preview_tree.configure(yscrollcommand=scrollbar.set)
        
        preview_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Store selection state
        selected_rows = {}
        
        def toggle_selection(event):
            item = preview_tree.identify_row(event.y)
            if item:
                selected_rows[item] = not selected_rows.get(item, False)
                # Update display
                values = list(preview_tree.item(item)['values'])
                values[0] = '☑' if selected_rows[item] else '☐'
                preview_tree.item(item, values=values)
        
        preview_tree.bind('<Button-1>', toggle_selection)
        
        def preview_data():
            # Clear existing items
            for item in preview_tree.get_children():
                preview_tree.delete(item)
            selected_rows.clear()
            
            first_col = first_name_var.get()
            last_col = last_name_var.get()
            qty_col = qty_var.get()
            
            if first_col == '-- Skip --' or last_col == '-- Skip --':
                messagebox.showwarning("Missing Mapping", "Please map First Name and Last Name columns!")
                return
            
            # Populate preview
            for idx, row in df.iterrows():
                try:
                    first = str(row[first_col]).strip() if first_col in row else ''
                    last = str(row[last_col]).strip() if last_col in row else ''
                    
                    if not first or not last or first == 'nan' or last == 'nan':
                        continue
                    
                    if qty_col != '-- Skip --' and qty_col in row:
                        try:
                            qty = int(row[qty_col])
                        except:
                            qty = 1
                    else:
                        qty = 1
                    
                    item_id = preview_tree.insert('', 'end', values=('☑', first, last, qty))
                    selected_rows[item_id] = True  # Default to selected
                    
                except Exception as e:
                    pass
            
            count_label.config(text=f"Found {len(selected_rows)} participants")
        
        # Auto-preview when dialog opens
        dialog.after(100, preview_data)
        
        # Count label
        count_label = tk.Label(
            dialog,
            text=f"Found {len(df)} rows in spreadsheet",
            bg=self.bg_frame,
            fg=self.fg_secondary,
            font=('Arial', 10)
        )
        count_label.pack(pady=5)
        
        def select_all():
            for item in preview_tree.get_children():
                selected_rows[item] = True
                values = list(preview_tree.item(item)['values'])
                values[0] = '☑'
                preview_tree.item(item, values=values)
        
        def deselect_all():
            for item in preview_tree.get_children():
                selected_rows[item] = False
                values = list(preview_tree.item(item)['values'])
                values[0] = '☐'
                preview_tree.item(item, values=values)
        
        def do_import():
            first_col = first_name_var.get()
            last_col = last_name_var.get()
            qty_col = qty_var.get()
            
            if first_col == '-- Skip --' or last_col == '-- Skip --':
                messagebox.showwarning("Missing Mapping", "Please map First Name and Last Name columns!")
                return
            
            imported = 0
            errors = []
            
            for item in preview_tree.get_children():
                if not selected_rows.get(item, False):
                    continue  # Skip unchecked items
                
                values = preview_tree.item(item)['values']
                first = values[1]
                last = values[2]
                qty = values[3]
                
                try:
                    # Generate tickets
                    for i in range(qty):
                        self.cursor.execute('''
                            INSERT INTO attendees (first_name, last_name, num_tickets)
                            VALUES (?, ?, ?)
                        ''', (first, last, qty))
                    
                    imported += qty
                    
                except Exception as e:
                    errors.append(f"{first} {last}: {str(e)}")
            
            self.conn.commit()
            self.refresh_table()
            dialog.destroy()
            
            msg = f"✓ Successfully imported {imported} ticket(s)!"
            if errors:
                msg += f"\n\n⚠ {len(errors)} error(s):\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    msg += f"\n... and {len(errors) - 5} more"
            
            messagebox.showinfo("Import Complete", msg)
        
        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.bg_frame)
        btn_frame.pack(pady=10)
        
        preview_btn = tk.Button(
            btn_frame,
            text="🔄 Refresh Preview",
            command=preview_data,
            bg=self.button_secondary,
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=6,
            relief='raised',
            borderwidth=2,
            activebackground=self.button_active,
            activeforeground='white'
        )
        preview_btn.pack(side='left', padx=3)
        
        select_all_btn = tk.Button(
            btn_frame,
            text="☑ Select All",
            command=select_all,
            bg=self.button_secondary,
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=6,
            relief='raised',
            borderwidth=2,
            activebackground=self.button_active,
            activeforeground='white'
        )
        select_all_btn.pack(side='left', padx=3)
        
        deselect_all_btn = tk.Button(
            btn_frame,
            text="☐ Deselect All",
            command=deselect_all,
            bg=self.button_secondary,
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=6,
            relief='raised',
            borderwidth=2,
            activebackground=self.button_active,
            activeforeground='white'
        )
        deselect_all_btn.pack(side='left', padx=3)
        
        import_btn = tk.Button(
            btn_frame,
            text="✅ Import Selected",
            command=do_import,
            bg=self.button_bg,
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=20,
            pady=6,
            relief='raised',
            borderwidth=2,
            activebackground=self.button_active,
            activeforeground='white'
        )
        import_btn.pack(side='left', padx=3)
        
        cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            command=dialog.destroy,
            bg='#CC0000',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=6,
            relief='raised',
            borderwidth=2,
            activebackground='#8B0000',
            activeforeground='white'
        )
        cancel_btn.pack(side='left', padx=3)
    
    def edit_selected(self):
        """Edit the selected ticket"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a ticket to edit!")
            return
        
        if len(selected) > 1:
            messagebox.showwarning("Multiple Selection", "Please select only one ticket to edit!")
            return
        
        # Get the ticket data
        values = self.tree.item(selected[0])['values']
        ticket_num = int(values[0].replace('#', ''))
        
        self.cursor.execute('SELECT * FROM attendees WHERE ticket_number = ?', (ticket_num,))
        row = self.cursor.fetchone()
        
        if not row:
            messagebox.showerror("Error", "Ticket not found!")
            return
        
        ticket, first, last, qty, created, printed = row
        
        # Create edit dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Ticket #{ticket:05d}")
        dialog.geometry("400x250")
        dialog.configure(bg=self.bg_frame)
        
        tk.Label(
            dialog,
            text=f"Edit Ticket #{ticket:05d}",
            font=('Arial', 14, 'bold'),
            bg=self.bg_frame,
            fg=self.fg_text
        ).pack(pady=20)
        
        edit_frame = tk.Frame(dialog, bg=self.bg_frame)
        edit_frame.pack(pady=10, padx=20)
        
        # First Name
        tk.Label(edit_frame, text="First Name:", bg=self.bg_frame, fg=self.fg_text, font=('Arial', 11)).grid(row=0, column=0, sticky='w', pady=5)
        first_entry = tk.Entry(edit_frame, font=('Arial', 11), width=25)
        first_entry.insert(0, first)
        first_entry.grid(row=0, column=1, pady=5)
        
        # Last Name
        tk.Label(edit_frame, text="Last Name:", bg=self.bg_frame, fg=self.fg_text, font=('Arial', 11)).grid(row=1, column=0, sticky='w', pady=5)
        last_entry = tk.Entry(edit_frame, font=('Arial', 11), width=25)
        last_entry.insert(0, last)
        last_entry.grid(row=1, column=1, pady=5)
        
        def save_changes():
            new_first = first_entry.get().strip()
            new_last = last_entry.get().strip()
            
            if not new_first or not new_last:
                messagebox.showwarning("Missing Info", "Please fill in all fields!")
                return
            
            self.cursor.execute('''
                UPDATE attendees 
                SET first_name = ?, last_name = ?
                WHERE ticket_number = ?
            ''', (new_first, new_last, ticket_num))
            self.conn.commit()
            
            self.refresh_table()
            dialog.destroy()
            messagebox.showinfo("Success", f"Ticket #{ticket:05d} updated!")
        
        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.bg_frame)
        btn_frame.pack(pady=20)
        
        save_btn = tk.Button(
            btn_frame,
            text="💾 Save",
            command=save_changes,
            bg=self.button_bg,
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8,
            relief='raised',
            borderwidth=2,
            activebackground=self.button_active,
            activeforeground='white'
        )
        save_btn.pack(side='left', padx=5)
        
        cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            command=dialog.destroy,
            bg=self.button_secondary,
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8,
            relief='raised',
            borderwidth=2,
            activebackground=self.button_active,
            activeforeground='white'
        )
        cancel_btn.pack(side='left', padx=5)
    
    def delete_selected(self):
        """Delete selected tickets"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select ticket(s) to delete!")
            return
        
        ticket_nums = []
        for item in selected:
            values = self.tree.item(item)['values']
            ticket_num = int(values[0].replace('#', ''))
            ticket_nums.append(ticket_num)
        
        count = len(ticket_nums)
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete {count} ticket(s)?\n\nThis cannot be undone!"
        )
        
        if not confirm:
            return
        
        try:
            self.cursor.execute(f'''
                DELETE FROM attendees 
                WHERE ticket_number IN ({','.join('?' * len(ticket_nums))})
            ''', ticket_nums)
            self.conn.commit()
            
            self.refresh_table()
            messagebox.showinfo("Deleted", f"Successfully deleted {count} ticket(s)!")
            
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Error deleting tickets: {e}")
    
    def export_to_csv(self):
        """Export all tickets to CSV"""
        from tkinter import filedialog
        import csv
        
        # Ask where to save
        filename = filedialog.asksaveasfilename(
            title="Export Ticket List",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"ticket_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if not filename:
            return
        
        try:
            self.cursor.execute('SELECT * FROM attendees ORDER BY ticket_number')
            rows = self.cursor.fetchall()
            
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Ticket Number', 'First Name', 'Last Name', 'Quantity', 'Created At', 'Printed'])
                
                for row in rows:
                    ticket, first, last, qty, created, printed = row
                    printed_status = 'Yes' if printed else 'No'
                    writer.writerow([f"#{ticket:05d}", first, last, qty, created, printed_status])
            
            messagebox.showinfo("Export Complete", f"✓ Exported {len(rows)} ticket(s) to:\n{filename}")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting data:\n{str(e)}")
    
    def show_settings(self):
        """Show settings dialog for customizing tickets"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Event & Ticket Settings")
        dialog.geometry("600x550")
        dialog.configure(bg=self.bg_frame)
        
        tk.Label(
            dialog,
            text="⚙️ Customize Event & Tickets",
            font=('Arial', 16, 'bold'),
            bg=self.bg_frame,
            fg=self.fg_text
        ).pack(pady=15)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Tab 1: Event Info
        event_frame = tk.Frame(notebook, bg=self.bg_frame)
        notebook.add(event_frame, text='Event Info')
        
        tk.Label(
            event_frame,
            text="Organization (always Joyce Kilmer Elementary PTA)",
            bg=self.bg_frame,
            fg=self.fg_secondary,
            font=('Arial', 9, 'italic')
        ).pack(pady=(20, 5))
        
        tk.Label(event_frame, text="Event Name:", bg=self.bg_frame, fg=self.fg_text, font=('Arial', 11, 'bold')).pack(pady=(10, 5))
        event_entry = tk.Entry(event_frame, font=('Arial', 12), width=35)
        event_entry.insert(0, self.get_setting('event_name'))
        event_entry.pack(pady=5)
        
        tk.Label(
            event_frame,
            text='Examples: "TRUNK OR TREAT", "SPRING CARNIVAL", "BOOK FAIR"',
            bg=self.bg_frame,
            fg=self.fg_secondary,
            font=('Arial', 9, 'italic')
        ).pack(pady=5)
        
        # Tab 2: Ticket Design
        design_frame = tk.Frame(notebook, bg=self.bg_frame)
        notebook.add(design_frame, text='Ticket Design')
        
        design_scroll_frame = tk.Frame(design_frame, bg=self.bg_frame)
        design_scroll_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        tk.Label(
            design_scroll_frame,
            text="Customize Emojis/Decorations:",
            bg=self.bg_frame,
            fg=self.fg_text,
            font=('Arial', 11, 'bold')
        ).grid(row=0, column=0, columnspan=2, pady=(10, 15), sticky='w')
        
        # Emoji 1 (Top Left)
        tk.Label(design_scroll_frame, text="Corner Emoji 1:", bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=5, padx=5)
        emoji1_entry = tk.Entry(design_scroll_frame, font=('Arial', 14), width=10)
        emoji1_entry.insert(0, self.get_setting('ticket_emoji_1', '🎃'))
        emoji1_entry.grid(row=1, column=1, pady=5, padx=5, sticky='w')
        
        # Emoji 2 (Top Right)
        tk.Label(design_scroll_frame, text="Corner Emoji 2:", bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10)).grid(row=2, column=0, sticky='w', pady=5, padx=5)
        emoji2_entry = tk.Entry(design_scroll_frame, font=('Arial', 14), width=10)
        emoji2_entry.insert(0, self.get_setting('ticket_emoji_2', '👻'))
        emoji2_entry.grid(row=2, column=1, pady=5, padx=5, sticky='w')
        
        # Emoji 3 (Bottom)
        tk.Label(design_scroll_frame, text="Bottom Emoji:", bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10)).grid(row=3, column=0, sticky='w', pady=5, padx=5)
        emoji3_entry = tk.Entry(design_scroll_frame, font=('Arial', 14), width=10)
        emoji3_entry.insert(0, self.get_setting('ticket_emoji_3', '🍬'))
        emoji3_entry.grid(row=3, column=1, pady=5, padx=5, sticky='w')
        
        tk.Label(
            design_scroll_frame,
            text="Color Theme:",
            bg=self.bg_frame,
            fg=self.fg_text,
            font=('Arial', 11, 'bold')
        ).grid(row=4, column=0, columnspan=2, pady=(20, 10), sticky='w')
        
        # Border Color
        tk.Label(design_scroll_frame, text="Border/Accent Color:", bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10)).grid(row=5, column=0, sticky='w', pady=5, padx=5)
        color_entry = tk.Entry(design_scroll_frame, font=('Arial', 11), width=15)
        color_entry.insert(0, self.get_setting('ticket_color', '#ff6600'))
        color_entry.grid(row=5, column=1, pady=5, padx=5, sticky='w')
        
        tk.Label(
            design_scroll_frame,
            text='Hex format: #ff6600 (orange), #4169e1 (blue), #32cd32 (green)',
            bg=self.bg_frame,
            fg=self.fg_secondary,
            font=('Arial', 8, 'italic')
        ).grid(row=6, column=0, columnspan=2, pady=(0, 5), padx=5, sticky='w')
        
        # Preset buttons
        preset_frame = tk.Frame(design_scroll_frame, bg=self.bg_frame)
        preset_frame.grid(row=7, column=0, columnspan=2, pady=10)
        
        tk.Label(preset_frame, text="Quick Presets:", bg=self.bg_frame, fg=self.fg_text, font=('Arial', 10, 'bold')).pack(anchor='w', pady=5)
        
        def apply_halloween():
            event_entry.delete(0, tk.END)
            event_entry.insert(0, "TRUNK OR TREAT")
            emoji1_entry.delete(0, tk.END)
            emoji1_entry.insert(0, "🎃")
            emoji2_entry.delete(0, tk.END)
            emoji2_entry.insert(0, "👻")
            emoji3_entry.delete(0, tk.END)
            emoji3_entry.insert(0, "🍬")
            color_entry.delete(0, tk.END)
            color_entry.insert(0, "#ff6600")
        
        def apply_spring():
            event_entry.delete(0, tk.END)
            event_entry.insert(0, "SPRING CARNIVAL")
            emoji1_entry.delete(0, tk.END)
            emoji1_entry.insert(0, "🌸")
            emoji2_entry.delete(0, tk.END)
            emoji2_entry.insert(0, "🦋")
            emoji3_entry.delete(0, tk.END)
            emoji3_entry.insert(0, "🌺")
            color_entry.delete(0, tk.END)
            color_entry.insert(0, "#ff69b4")
        
        def apply_winter():
            event_entry.delete(0, tk.END)
            event_entry.insert(0, "WINTER WONDERLAND")
            emoji1_entry.delete(0, tk.END)
            emoji1_entry.insert(0, "❄️")
            emoji2_entry.delete(0, tk.END)
            emoji2_entry.insert(0, "⛄")
            emoji3_entry.delete(0, tk.END)
            emoji3_entry.insert(0, "🎄")
            color_entry.delete(0, tk.END)
            color_entry.insert(0, "#4169e1")
        
        def apply_generic():
            event_entry.delete(0, tk.END)
            event_entry.insert(0, "SCHOOL EVENT")
            emoji1_entry.delete(0, tk.END)
            emoji1_entry.insert(0, "⭐")
            emoji2_entry.delete(0, tk.END)
            emoji2_entry.insert(0, "📚")
            emoji3_entry.delete(0, tk.END)
            emoji3_entry.insert(0, "🎉")
            color_entry.delete(0, tk.END)
            color_entry.insert(0, "#4169e1")
        
        preset_buttons = tk.Frame(preset_frame, bg=self.bg_frame)
        preset_buttons.pack()
        
        tk.Button(preset_buttons, text="🎃 Halloween", command=apply_halloween, bg='#ff6600', fg='white', font=('Arial', 9, 'bold'), padx=8, pady=4).pack(side='left', padx=3)
        tk.Button(preset_buttons, text="🌸 Spring", command=apply_spring, bg='#ff69b4', fg='white', font=('Arial', 9, 'bold'), padx=8, pady=4).pack(side='left', padx=3)
        tk.Button(preset_buttons, text="❄️ Winter", command=apply_winter, bg='#4169e1', fg='white', font=('Arial', 9, 'bold'), padx=8, pady=4).pack(side='left', padx=3)
        tk.Button(preset_buttons, text="⭐ Generic", command=apply_generic, bg='#32cd32', fg='white', font=('Arial', 9, 'bold'), padx=8, pady=4).pack(side='left', padx=3)
        
        def save_settings():
            self.set_setting('event_name', event_entry.get().strip())
            self.set_setting('ticket_emoji_1', emoji1_entry.get().strip())
            self.set_setting('ticket_emoji_2', emoji2_entry.get().strip())
            self.set_setting('ticket_emoji_3', emoji3_entry.get().strip())
            self.set_setting('ticket_color', color_entry.get().strip())
            messagebox.showinfo("Saved", "Settings saved successfully!\n\nNew tickets will use these settings.")
            dialog.destroy()
        
        # Buttons at bottom
        btn_frame = tk.Frame(dialog, bg=self.bg_frame)
        btn_frame.pack(pady=15)
        
        save_btn = tk.Button(
            btn_frame,
            text="💾 Save Settings",
            command=save_settings,
            bg=self.button_bg,
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8,
            relief='raised',
            borderwidth=2,
            activebackground=self.button_active,
            activeforeground='white'
        )
        save_btn.pack(side='left', padx=5)
        
        cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            command=dialog.destroy,
            bg=self.button_secondary,
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8,
            relief='raised',
            borderwidth=2,
            activebackground=self.button_active,
            activeforeground='white'
        )
        cancel_btn.pack(side='left', padx=5)
    
    def print_selected(self):
        """Print tickets for selected attendees"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select attendees to print!")
            return
        
        tickets = []
        for item in selected:
            values = self.tree.item(item)['values']
            ticket_num = int(values[0].replace('#', ''))
            tickets.append(ticket_num)
        
        self.generate_tickets(tickets)
    
    def print_all_unprinted(self):
        """Print all unprinted tickets"""
        self.cursor.execute('SELECT ticket_number FROM attendees WHERE printed = 0')
        tickets = [row[0] for row in self.cursor.fetchall()]
        
        if not tickets:
            messagebox.showinfo("No Tickets", "All tickets have been printed!")
            return
        
        self.generate_tickets(tickets)
    
    def generate_tickets(self, ticket_numbers):
        """Generate HTML tickets for printing"""
        if not ticket_numbers:
            return
        
        self.cursor.execute(f'''
            SELECT * FROM attendees 
            WHERE ticket_number IN ({','.join('?' * len(ticket_numbers))})
        ''', ticket_numbers)
        
        attendees = self.cursor.fetchall()
        
        # Get custom settings
        org_name = 'Joyce Kilmer Elementary PTA'  # Always this
        event_name = self.get_setting('event_name', 'TRUNK OR TREAT')
        emoji1 = self.get_setting('ticket_emoji_1', '🎃')
        emoji2 = self.get_setting('ticket_emoji_2', '👻')
        emoji3 = self.get_setting('ticket_emoji_3', '🍬')
        border_color = self.get_setting('ticket_color', '#ff6600')
        
        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>{event_name} Tickets</title>
            <style>
                @page {{ margin: 0.5in; }}
                body {{ 
                    font-family: 'Comic Sans MS', cursive;
                    margin: 0;
                    padding: 20px;
                }}
                .ticket {{
                    width: 3.5in;
                    height: 2.5in;
                    border: 5px solid {border_color};
                    border-radius: 15px;
                    padding: 20px;
                    margin: 10px;
                    display: inline-block;
                    background: linear-gradient(135deg, #fff5e6 0%, #ffe6cc 100%);
                    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                    page-break-inside: avoid;
                    position: relative;
                }}
                .ticket-header {{
                    text-align: center;
                    font-size: 16px;
                    font-weight: bold;
                    color: {border_color};
                    margin-bottom: 5px;
                    text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
                }}
                .ticket-event {{
                    text-align: center;
                    font-size: 18px;
                    font-weight: bold;
                    color: #4d2600;
                    margin-bottom: 8px;
                }}
                .ticket-number {{
                    text-align: center;
                    font-size: 48px;
                    font-weight: bold;
                    color: #4d2600;
                    margin: 15px 0;
                    background: white;
                    padding: 10px;
                    border-radius: 10px;
                    border: 3px dashed {border_color};
                }}
                .ticket-info {{
                    font-size: 11px;
                    color: #666;
                    margin: 3px 0;
                    text-align: center;
                    font-style: italic;
                }}
                .access-label {{
                    text-align: center;
                    font-size: 14px;
                    font-weight: bold;
                    color: {border_color};
                    margin-top: 8px;
                }}
                .decorations {{
                    position: absolute;
                    font-size: 24px;
                }}
                .pumpkin-tl {{ top: 5px; left: 5px; }}
                .pumpkin-tr {{ top: 5px; right: 5px; }}
                .ghost-bl {{ bottom: 5px; left: 5px; }}
                .candy-br {{ bottom: 5px; right: 5px; }}
            </style>
        </head>
        <body>
        '''
        
        for attendee in attendees:
            ticket, first, last, qty, created, printed = attendee
            html_content += f'''
            <div class="ticket">
                <div class="decorations pumpkin-tl">{emoji1}</div>
                <div class="decorations pumpkin-tr">{emoji1}</div>
                <div class="decorations ghost-bl">{emoji2}</div>
                <div class="decorations candy-br">{emoji3}</div>
                
                <div class="ticket-header">{org_name}</div>
                <div class="ticket-event">{emoji1} {event_name} {emoji2}</div>
                <div class="access-label">⭐ ACCESS TICKET ⭐</div>
                <div class="ticket-number">#{ticket:05d}</div>
                <div class="ticket-info">Registered: {first} {last}</div>
            </div>
            '''
        
        html_content += '''
        </body>
        </html>
        '''
        
        # Save HTML file
        filename = f'tickets_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
        filepath = f'/mnt/user-data/outputs/{filename}'
        
        with open(filepath, 'w') as f:
            f.write(html_content)
        
        # Mark as printed
        self.cursor.execute(f'''
            UPDATE attendees 
            SET printed = 1 
            WHERE ticket_number IN ({','.join('?' * len(ticket_numbers))})
        ''', ticket_numbers)
        self.conn.commit()
        
        self.refresh_table()
        
        messagebox.showinfo(
            "Tickets Generated!",
            f"✓ {len(attendees)} ticket(s) saved to:\n{filename}\n\nOpen this file in your browser and print!"
        )
    
    def __del__(self):
        """Close database connection"""
        if hasattr(self, 'conn'):
            self.conn.close()

if __name__ == '__main__':
    root = tk.Tk()
    app = TrunkOrTreatApp(root)
    root.mainloop()