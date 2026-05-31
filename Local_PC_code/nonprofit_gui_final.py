import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import mysql.connector
from datetime import datetime

# ========== DATABASE CONFIGURATION ==========
DB_CONFIG = {
    'host': 'localhost',
    'database': 'nonprofit_db',
    'user': 'root',
    'password': 'root123'   # CHANGE THIS to your MySQL root password
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def execute_query(query, params=None, fetch=False, commit=False):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(query, params or ())
        if fetch:
            return cursor.fetchall()
        if commit:
            conn.commit()
            return cursor.lastrowid
    except mysql.connector.Error as e:
        messagebox.showerror("Database Error", str(e))
        return None
    finally:
        cursor.close()
        conn.close()

# ========== GLOBAL USER DATA ==========
current_user_id = None
current_role = None
current_permissions = {}

def load_permissions(user_id):
    global current_permissions
    rows = execute_query("SELECT table_name, can_view, can_edit FROM user_permissions WHERE user_id = %s", (user_id,), fetch=True)
    current_permissions = {row['table_name']: {'view': row['can_view'], 'edit': row['can_edit']} for row in rows}
    if current_role == 'admin':
        for t in ['people_served', 'donors', 'food_locations', 'appointments', 'reports']:
            current_permissions[t] = {'view': True, 'edit': True}

def can_view(table): return current_permissions.get(table, {}).get('view', False)
def can_edit(table): return current_permissions.get(table, {}).get('edit', False)

# ========== LOGIN WINDOW ==========
def login_window():
    def do_login():
        global current_user_id, current_role
        user = execute_query("SELECT user_id, role FROM users WHERE username = %s AND password = %s",
                             (entry_user.get(), entry_pass.get()), fetch=True)
        if user:
            current_user_id = user[0]['user_id']
            current_role = user[0]['role']
            load_permissions(current_user_id)
            root.destroy()
            main_window()
        else:
            messagebox.showerror("Login Failed", "Invalid username/password")
    root = tk.Tk()
    root.title("Nonprofit Database Login")
    root.geometry("300x200")
    tk.Label(root, text="Username:").pack(pady=5)
    entry_user = tk.Entry(root)
    entry_user.pack()
    tk.Label(root, text="Password:").pack(pady=5)
    entry_pass = tk.Entry(root, show="*")
    entry_pass.pack()
    tk.Button(root, text="Login", command=do_login).pack(pady=20)
    root.mainloop()

# ========== USER MANAGEMENT (ADMIN ONLY) ==========
def user_management(parent):
    if current_role != 'admin':
        messagebox.showerror("Access Denied", "Only admin can manage users.")
        return
    child = tk.Toplevel(parent)
    child.title("User Management")
    child.geometry("800x550")

    tree = ttk.Treeview(child, columns=('ID','Username','Role'), show='headings')
    for col in ('ID','Username','Role'):
        tree.heading(col, text=col)
        tree.column(col, width=100)
    tree.pack(fill=tk.BOTH, expand=True)

    perm_frame = tk.LabelFrame(child, text="Table Permissions (View/Edit) for Selected User", padx=5, pady=5)
    perm_frame.pack(fill=tk.X, padx=10, pady=10)

    tables = ['people_served', 'donors', 'food_locations', 'appointments', 'reports']
    perm_vars = {}

    def refresh_users():
        for i in tree.get_children():
            tree.delete(i)
        for u in execute_query("SELECT user_id, username, role FROM users", fetch=True):
            tree.insert('', 'end', values=(u['user_id'], u['username'], u['role']))

    def on_select(event):
        sel = tree.selection()
        if not sel: return
        uid = tree.item(sel[0])['values'][0]
        perms = {p['table_name']:(p['can_view'], p['can_edit']) for p in execute_query("SELECT table_name, can_view, can_edit FROM user_permissions WHERE user_id=%s", (uid,), fetch=True)}
        for w in perm_frame.winfo_children():
            w.destroy()
        perm_vars.clear()
        for i, t in enumerate(tables):
            v, e = perms.get(t, (False, False))
            vv = tk.BooleanVar(value=v)
            ee = tk.BooleanVar(value=e)
            perm_vars[t] = (vv, ee)
            tk.Label(perm_frame, text=t.replace('_',' ').title()).grid(row=i, column=0, sticky='w', padx=5, pady=2)
            tk.Checkbutton(perm_frame, text="View", variable=vv).grid(row=i, column=1, padx=5)
            tk.Checkbutton(perm_frame, text="Edit", variable=ee).grid(row=i, column=2, padx=5)
        def save_perms():
            for t, (vv, ee) in perm_vars.items():
                execute_query("DELETE FROM user_permissions WHERE user_id=%s AND table_name=%s", (uid, t), commit=True)
                if vv.get() or ee.get():
                    execute_query("INSERT INTO user_permissions (user_id, table_name, can_view, can_edit) VALUES (%s,%s,%s,%s)",
                                  (uid, t, vv.get(), ee.get()), commit=True)
            messagebox.showinfo("Saved", f"Permissions updated for user ID {uid}")
        tk.Button(perm_frame, text="Save Permissions", command=save_perms).grid(row=len(tables), column=0, columnspan=3, pady=10)

    tree.bind('<<TreeviewSelect>>', on_select)

    btn_frame = tk.Frame(child)
    btn_frame.pack(pady=10)

    def add_user():
        dlg = tk.Toplevel(child)
        dlg.title("Add New User")
        tk.Label(dlg, text="Username:").grid(row=0, column=0, padx=5, pady=5)
        uname = tk.Entry(dlg)
        uname.grid(row=0, column=1)
        tk.Label(dlg, text="Password:").grid(row=1, column=0)
        pwd = tk.Entry(dlg, show="*")
        pwd.grid(row=1, column=1)
        tk.Label(dlg, text="Role:").grid(row=2, column=0)
        role_var = tk.StringVar(value="viewer")
        ttk.Combobox(dlg, textvariable=role_var, values=['admin','editor','viewer'], state='readonly').grid(row=2, column=1)
        def save():
            if not uname.get() or not pwd.get():
                messagebox.showerror("Error","Username and password required")
                return
            if execute_query("SELECT user_id FROM users WHERE username=%s", (uname.get(),), fetch=True):
                messagebox.showerror("Error","Username already exists")
                return
            uid = execute_query("INSERT INTO users (username, password, role) VALUES (%s,%s,%s)",
                                (uname.get(), pwd.get(), role_var.get()), commit=True)
            if uid:
                messagebox.showinfo("Success","User added. Now assign table permissions.")
                refresh_users()
                dlg.destroy()
        tk.Button(dlg, text="Create User", command=save).grid(row=3, column=0, columnspan=2, pady=10)

    def edit_role():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a user first")
            return
        uid, name, old = tree.item(sel[0])['values']
        new = simpledialog.askstring("Change Role", f"Enter new role for {name} (admin/editor/viewer):", initialvalue=old)
        if new in ['admin','editor','viewer']:
            execute_query("UPDATE users SET role=%s WHERE user_id=%s", (new, uid), commit=True)
            refresh_users()
            messagebox.showinfo("Updated", f"{name} role changed to {new}")
        else:
            messagebox.showerror("Invalid","Role must be admin, editor, or viewer")

    def delete_user():
        sel = tree.selection()
        if not sel: return
        uid, name, _ = tree.item(sel[0])['values']
        if name == 'admin':
            messagebox.showerror("Cannot Delete","The default admin cannot be deleted.")
            return
        if messagebox.askyesno("Confirm", f"Delete user '{name}'? All their permissions will be removed."):
            execute_query("DELETE FROM users WHERE user_id=%s", (uid,), commit=True)
            refresh_users()
            for w in perm_frame.winfo_children():
                w.destroy()

    tk.Button(btn_frame, text="Add User", command=add_user).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="Edit Role", command=edit_role).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="Delete User", command=delete_user).pack(side=tk.LEFT, padx=5)

    refresh_users()

# ========== GENERIC TABLE EDITOR (for simple tables) ==========
def table_editor(parent, table_name):
    config = {
        'people_served': {
            'title':'People Served',
            'cols':('ID','Name','Address','Family Size','Service Date','Consent'),
            'select':"SELECT id, full_name, address, family_size, service_date, consent_given FROM people_served",
            'insert_cols':('full_name','address','family_size','service_date','consent_given'),
            'update_cols':('full_name','address','family_size','service_date','consent_given')
        },
        'donors': {
            'title':'Donors',
            'cols':('ID','Name','Email','Phone','Donation Amount','Donation Date'),
            'select':"SELECT id, name, email, contact_phone, donation_amount, donation_date FROM donors",
            'insert_cols':('name','email','contact_phone','donation_amount','donation_date'),
            'update_cols':('name','email','contact_phone','donation_amount','donation_date')
        },
        'food_locations': {
            'title':'Food Locations',
            'cols':('ID','Name','Address','Days of Operation','Contact Person'),
            'select':"SELECT id, location_name, address, days_of_operation, contact_person FROM food_locations",
            'insert_cols':('location_name','address','days_of_operation','contact_person'),
            'update_cols':('location_name','address','days_of_operation','contact_person')
        }
    }
    if table_name not in config:
        messagebox.showerror("Error", f"Unknown module: {table_name}")
        return

    cfg = config[table_name]
    win = tk.Toplevel(parent)
    win.title(cfg['title'])
    win.geometry("900x500")

    tree = ttk.Treeview(win, columns=cfg['cols'], show='headings')
    for col in cfg['cols']:
        tree.heading(col, text=col)
        tree.column(col, width=120)
    tree.pack(fill=tk.BOTH, expand=True)

    def refresh():
        for i in tree.get_children():
            tree.delete(i)
        rows = execute_query(cfg['select'], fetch=True)
        for r in rows:
            if 'consent_given' in r:
                r['consent_given'] = "Yes" if r['consent_given'] else "No"
            tree.insert('', 'end', values=tuple(r.values()))

    btn_frame = tk.Frame(win)
    btn_frame.pack(pady=10)

    def add_record():
        if not can_edit(table_name):
            messagebox.showerror("Permission Denied", "You do not have edit permission.")
            return
        dlg = tk.Toplevel(win)
        dlg.title(f"Add {cfg['title']}")
        entries = {}
        row_idx = 0
        for col in cfg['insert_cols']:
            label = col.replace('_',' ').title()
            tk.Label(dlg, text=label).grid(row=row_idx, column=0, padx=5, pady=5, sticky='e')
            if col == 'consent_given':
                var = tk.BooleanVar(value=False)
                chk = tk.Checkbutton(dlg, variable=var)
                chk.grid(row=row_idx, column=1, sticky='w')
                entries[col] = var
            else:
                e = tk.Entry(dlg, width=30)
                e.grid(row=row_idx, column=1, padx=5, pady=5)
                entries[col] = e
            row_idx += 1
        def save():
            values = []
            for col in cfg['insert_cols']:
                val = entries[col].get() if not isinstance(entries[col], tk.BooleanVar) else entries[col].get()
                if col == 'service_date' and not val:
                    val = datetime.today().strftime('%Y-%m-%d')
                values.append(val)
            placeholders = ','.join(['%s']*len(values))
            query = f"INSERT INTO {table_name} ({','.join(cfg['insert_cols'])}) VALUES ({placeholders})"
            execute_query(query, tuple(values), commit=True)
            dlg.destroy()
            refresh()
        tk.Button(dlg, text="Save", command=save).grid(row=row_idx, column=0, columnspan=2, pady=10)

    def edit_record():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a record first")
            return
        if not can_edit(table_name):
            messagebox.showerror("Permission Denied", "No edit permission")
            return
        rid = tree.item(sel[0])['values'][0]
        cur = execute_query(f"SELECT * FROM {table_name} WHERE id=%s", (rid,), fetch=True)[0]
        dlg = tk.Toplevel(win)
        dlg.title(f"Edit {cfg['title']}")
        entries = {}
        row_idx = 0
        for col in cfg['update_cols']:
            label = col.replace('_',' ').title()
            tk.Label(dlg, text=label).grid(row=row_idx, column=0, padx=5, pady=5, sticky='e')
            if col == 'consent_given':
                var = tk.BooleanVar(value=bool(cur[col]))
                chk = tk.Checkbutton(dlg, variable=var)
                chk.grid(row=row_idx, column=1, sticky='w')
                entries[col] = var
            else:
                e = tk.Entry(dlg, width=30)
                e.insert(0, str(cur[col]) if cur[col] is not None else '')
                e.grid(row=row_idx, column=1, padx=5, pady=5)
                entries[col] = e
            row_idx += 1
        def save():
            updates = []
            vals = []
            for col in cfg['update_cols']:
                val = entries[col].get() if not isinstance(entries[col], tk.BooleanVar) else entries[col].get()
                updates.append(f"{col}=%s")
                vals.append(val)
            vals.append(rid)
            query = f"UPDATE {table_name} SET {','.join(updates)} WHERE id=%s"
            execute_query(query, tuple(vals), commit=True)
            dlg.destroy()
            refresh()
        tk.Button(dlg, text="Update", command=save).grid(row=row_idx, column=0, columnspan=2, pady=10)

    def delete_record():
        if not can_edit(table_name):
            messagebox.showerror("Permission Denied", "No delete permission")
            return
        sel = tree.selection()
        if not sel: return
        rid = tree.item(sel[0])['values'][0]
        if messagebox.askyesno("Confirm", f"Delete record ID {rid}?"):
            execute_query(f"DELETE FROM {table_name} WHERE id=%s", (rid,), commit=True)
            refresh()

    tk.Button(btn_frame, text="Add", command=add_record).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="Edit", command=edit_record).pack(side=tk.LEFT, padx=5)
    if current_role == 'admin' or can_edit(table_name):
        tk.Button(btn_frame, text="Delete", command=delete_record).pack(side=tk.LEFT, padx=5)

    refresh()

# ========== APPOINTMENTS MODULE (with dropdowns) ==========
def appointments_editor(parent):
    if not can_view('appointments'):
        messagebox.showerror("Access Denied", "You cannot view appointments.")
        return
    win = tk.Toplevel(parent)
    win.title("Appointments")
    win.geometry("1000x500")

    columns = ('ID','Recipient','Date','Time','Location','Purpose')
    tree = ttk.Treeview(win, columns=columns, show='headings')
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=150)
    tree.pack(fill=tk.BOTH, expand=True)

    def refresh():
        for i in tree.get_children():
            tree.delete(i)
        query = """SELECT a.id, p.full_name, a.appointment_date, a.appointment_time, l.location_name, a.purpose
                   FROM appointments a
                   LEFT JOIN people_served p ON a.recipient_id = p.id
                   LEFT JOIN food_locations l ON a.location_id = l.id"""
        rows = execute_query(query, fetch=True)
        for r in rows:
            tree.insert('', 'end', values=(r['id'], r['full_name'], r['appointment_date'], r['appointment_time'], r['location_name'], r['purpose']))

    def get_recipient_choices():
        return execute_query("SELECT id, full_name FROM people_served ORDER BY full_name", fetch=True)
    def get_location_choices():
        return execute_query("SELECT id, location_name FROM food_locations ORDER BY location_name", fetch=True)

    def add_appointment():
        if not can_edit('appointments'):
            messagebox.showerror("Permission Denied", "No edit permission")
            return
        dlg = tk.Toplevel(win)
        dlg.title("Schedule New Appointment")
        # Recipient
        tk.Label(dlg, text="Recipient:").grid(row=0, column=0, padx=5, pady=5, sticky='e')
        recipients = get_recipient_choices()
        if not recipients:
            messagebox.showerror("Error", "No recipients available. Add a person first.")
            dlg.destroy()
            return
        recip_dict = {r['full_name']: r['id'] for r in recipients}
        recip_names = list(recip_dict.keys())
        rec_var = tk.StringVar()
        rec_combo = ttk.Combobox(dlg, textvariable=rec_var, values=recip_names, state='readonly', width=30)
        rec_combo.grid(row=0, column=1, padx=5, pady=5)
        # Date
        tk.Label(dlg, text="Date (YYYY-MM-DD):").grid(row=1, column=0, sticky='e')
        date_entry = tk.Entry(dlg, width=30)
        date_entry.insert(0, datetime.today().strftime('%Y-%m-%d'))
        date_entry.grid(row=1, column=1, padx=5, pady=5)
        # Time
        tk.Label(dlg, text="Time (HH:MM:SS):").grid(row=2, column=0, sticky='e')
        time_entry = tk.Entry(dlg, width=30)
        time_entry.insert(0, "10:00:00")
        time_entry.grid(row=2, column=1, padx=5, pady=5)
        # Location
        tk.Label(dlg, text="Location:").grid(row=3, column=0, sticky='e')
        locations = get_location_choices()
        loc_dict = {l['location_name']: l['id'] for l in locations} if locations else {}
        loc_names = list(loc_dict.keys())
        loc_var = tk.StringVar()
        loc_combo = ttk.Combobox(dlg, textvariable=loc_var, values=loc_names, state='readonly', width=30)
        loc_combo.grid(row=3, column=1, padx=5, pady=5)
        # Purpose
        tk.Label(dlg, text="Purpose:").grid(row=4, column=0, sticky='e')
        purpose_entry = tk.Entry(dlg, width=30)
        purpose_entry.grid(row=4, column=1, padx=5, pady=5)
        def save():
            if not rec_var.get():
                messagebox.showerror("Error", "Select a recipient")
                return
            rec_id = recip_dict[rec_var.get()]
            loc_id = loc_dict[loc_var.get()] if loc_var.get() else None
            execute_query("INSERT INTO appointments (recipient_id, appointment_date, appointment_time, location_id, purpose) VALUES (%s,%s,%s,%s,%s)",
                          (rec_id, date_entry.get(), time_entry.get(), loc_id, purpose_entry.get()), commit=True)
            dlg.destroy()
            refresh()
        tk.Button(dlg, text="Save Appointment", command=save).grid(row=5, column=0, columnspan=2, pady=10)

    def edit_appointment():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select an appointment first")
            return
        if not can_edit('appointments'):
            messagebox.showerror("Permission Denied", "No edit permission")
            return
        aid = tree.item(sel[0])['values'][0]
        cur = execute_query("SELECT * FROM appointments WHERE id=%s", (aid,), fetch=True)[0]
        cur_rec = execute_query("SELECT full_name FROM people_served WHERE id=%s", (cur['recipient_id'],), fetch=True)
        cur_loc = execute_query("SELECT location_name FROM food_locations WHERE id=%s", (cur['location_id'],), fetch=True) if cur['location_id'] else None
        dlg = tk.Toplevel(win)
        dlg.title("Edit Appointment")
        # Recipient
        tk.Label(dlg, text="Recipient:").grid(row=0, column=0, padx=5, pady=5, sticky='e')
        recipients = get_recipient_choices()
        recip_dict = {r['full_name']: r['id'] for r in recipients}
        rec_names = list(recip_dict.keys())
        rec_var = tk.StringVar(value=cur_rec[0]['full_name'] if cur_rec else '')
        rec_combo = ttk.Combobox(dlg, textvariable=rec_var, values=rec_names, state='readonly', width=30)
        rec_combo.grid(row=0, column=1, padx=5, pady=5)
        # Date
        tk.Label(dlg, text="Date (YYYY-MM-DD):").grid(row=1, column=0, sticky='e')
        date_entry = tk.Entry(dlg, width=30)
        date_entry.insert(0, cur['appointment_date'])
        date_entry.grid(row=1, column=1)
        # Time
        tk.Label(dlg, text="Time (HH:MM:SS):").grid(row=2, column=0, sticky='e')
        time_entry = tk.Entry(dlg, width=30)
        time_entry.insert(0, cur['appointment_time'] if cur['appointment_time'] else '')
        time_entry.grid(row=2, column=1)
        # Location
        tk.Label(dlg, text="Location:").grid(row=3, column=0, sticky='e')
        locations = get_location_choices()
        loc_dict = {l['location_name']: l['id'] for l in locations}
        loc_names = list(loc_dict.keys())
        loc_var = tk.StringVar(value=cur_loc[0]['location_name'] if cur_loc else '')
        loc_combo = ttk.Combobox(dlg, textvariable=loc_var, values=loc_names, state='readonly', width=30)
        loc_combo.grid(row=3, column=1)
        # Purpose
        tk.Label(dlg, text="Purpose:").grid(row=4, column=0, sticky='e')
        purpose_entry = tk.Entry(dlg, width=30)
        purpose_entry.insert(0, cur['purpose'] or '')
        purpose_entry.grid(row=4, column=1)
        def save():
            rec_id = recip_dict[rec_var.get()]
            loc_id = loc_dict[loc_var.get()] if loc_var.get() else None
            execute_query("UPDATE appointments SET recipient_id=%s, appointment_date=%s, appointment_time=%s, location_id=%s, purpose=%s WHERE id=%s",
                          (rec_id, date_entry.get(), time_entry.get(), loc_id, purpose_entry.get(), aid), commit=True)
            dlg.destroy()
            refresh()
        tk.Button(dlg, text="Update", command=save).grid(row=5, column=0, columnspan=2, pady=10)

    def delete_appointment():
        if not can_edit('appointments'):
            messagebox.showerror("Permission Denied", "No delete permission")
            return
        sel = tree.selection()
        if not sel: return
        aid = tree.item(sel[0])['values'][0]
        if messagebox.askyesno("Confirm", f"Delete appointment ID {aid}?"):
            execute_query("DELETE FROM appointments WHERE id=%s", (aid,), commit=True)
            refresh()

    btn_frame = tk.Frame(win)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="Add Appointment", command=add_appointment).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="Edit Appointment", command=edit_appointment).pack(side=tk.LEFT, padx=5)
    if current_role == 'admin' or can_edit('appointments'):
        tk.Button(btn_frame, text="Delete Appointment", command=delete_appointment).pack(side=tk.LEFT, padx=5)

    refresh()

# ========== REPORTS MODULE ==========
def reports_window(parent):
    if not can_view('reports'):
        messagebox.showerror("Access Denied", "You cannot view reports.")
        return
    win = tk.Toplevel(parent)
    win.title("Reports")
    win.geometry("400x450")

    def show_report(title, lines):
        rw = tk.Toplevel(win)
        rw.title(title)
        text = tk.Text(rw, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True)
        for line in lines:
            text.insert(tk.END, line + "\n")
        text.config(state=tk.DISABLED)

    def daily():
        d = simpledialog.askstring("Daily Report", "Enter date (YYYY-MM-DD):")
        if not d: return
        res = execute_query("SELECT COUNT(*) as cnt FROM people_served WHERE service_date=%s", (d,), fetch=True)
        show_report("Daily Service Report", [f"Date: {d}", f"People served: {res[0]['cnt']}"])
    def weekly():
        s = simpledialog.askstring("Weekly Report", "Start date (YYYY-MM-DD):")
        e = simpledialog.askstring("Weekly Report", "End date (YYYY-MM-DD):")
        if s and e:
            res = execute_query("SELECT COUNT(*) as cnt FROM people_served WHERE service_date BETWEEN %s AND %s", (s, e), fetch=True)
            show_report("Weekly Service Report", [f"Period: {s} to {e}", f"Total served: {res[0]['cnt']}"])
    def monthly():
        m = simpledialog.askstring("Monthly Report", "Month (1-12):")
        y = simpledialog.askstring("Monthly Report", "Year (YYYY):")
        if m and y:
            res = execute_query("SELECT COUNT(*) as cnt FROM people_served WHERE MONTH(service_date)=%s AND YEAR(service_date)=%s", (m, y), fetch=True)
            show_report("Monthly Service Report", [f"{m}/{y}: {res[0]['cnt']} people served"])
    def yearly():
        y = simpledialog.askstring("Yearly Report", "Year (YYYY):")
        if y:
            res = execute_query("SELECT COUNT(*) as cnt FROM people_served WHERE YEAR(service_date)=%s", (y,), fetch=True)
            show_report("Yearly Service Report", [f"Year {y}: {res[0]['cnt']} served"])
    def donor_list():
        data = execute_query("SELECT name, email, donation_amount FROM donors", fetch=True)
        lines = ["Donor List"] + [f"{d['name']} | {d['email']} | ${d['donation_amount']}" for d in data]
        show_report("Donor List", lines)
    def appt_list():
        data = execute_query("""SELECT p.full_name, a.appointment_date, a.appointment_time, l.location_name
                                FROM appointments a
                                JOIN people_served p ON a.recipient_id=p.id
                                LEFT JOIN food_locations l ON a.location_id=l.id""", fetch=True)
        lines = ["Appointment List"] + [f"{d['full_name']} on {d['appointment_date']} at {d['appointment_time']} @ {d['location_name']}" for d in data]
        show_report("Appointment List", lines)
    def irs():
        data = execute_query("SELECT name, SUM(donation_amount) as total FROM donors GROUP BY name", fetch=True)
        lines = ["IRS Donation Summary"] + [f"{d['name']}: ${d['total']}" for d in data]
        show_report("IRS Summary", lines)

    btns = [("Daily Service Report", daily), ("Weekly Service Report", weekly), ("Monthly Service Report", monthly),
            ("Yearly Service Report", yearly), ("Donor List", donor_list), ("Appointment List", appt_list),
            ("IRS Donation Summary", irs)]
    for txt, cmd in btns:
        tk.Button(win, text=txt, command=cmd, width=25).pack(pady=3)

# ========== MAIN WINDOW ==========
def main_window():
    win = tk.Tk()
    win.title("Nonprofit Food Assistance Database")
    win.geometry("800x600")
    tk.Label(win, text=f"Logged in as: {current_role}", font=('Arial',10,'bold')).pack(anchor='ne', padx=10, pady=5)
    if current_role == 'admin':
        tk.Button(win, text="User Management", bg="lightblue", command=lambda: user_management(win)).pack(pady=5)

    frame = tk.Frame(win)
    frame.pack(pady=20)

    modules = [
        ('people_served', "People Served", table_editor),
        ('donors', "Donors", table_editor),
        ('food_locations', "Food Locations", table_editor),
        ('appointments', "Appointments", lambda p, t: appointments_editor(p)),
        ('reports', "Reports", lambda p, t: reports_window(p))
    ]
    row, col = 0, 0
    for tbl, label, cmd in modules:
        if can_view(tbl) or tbl == 'reports':
            if tbl == 'appointments' or tbl == 'reports':
                btn = tk.Button(frame, text=label, width=20, command=lambda p=win, c=cmd: c(p, None))
            else:
                btn = tk.Button(frame, text=label, width=20, command=lambda p=win, t=tbl, c=cmd: c(p, t))
            btn.grid(row=row, column=col, padx=10, pady=5)
            col += 1
            if col > 2:
                col = 0
                row += 1
    tk.Button(frame, text="Exit", command=win.destroy, width=20).grid(row=row+1, column=0, columnspan=3, pady=20)
    win.mainloop()

if __name__ == "__main__":
    login_window()
