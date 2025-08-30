import tkinter as tk
from tkinter import ttk, messagebox
import os
import pickle  # Only if used elsewhere
import csv

DATA_DIR = "face_embeddings"
EMBEDDINGS_PATH = os.path.join(DATA_DIR, "embeddings.pkl")
CSV_PATH = os.path.join(DATA_DIR, "user_info.csv")

def ensure_active_column():
    if not os.path.exists(CSV_PATH):
        return
    with open(CSV_PATH, newline='') as csvfile:
        rows = list(csv.reader(csvfile))
    if rows and 'Active' not in rows[0]:
        rows[0].append('Active')
        for i in range(1, len(rows)):
            rows[i].append('1')
        with open(CSV_PATH, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(rows)

class AddFacesGUI(tk.Tk):
    def show_main(self):
        # Destroy any existing frames
        if self.current_frame:
            self.current_frame.destroy()
            self.current_frame = None
        if self.main_area:
            self.main_area.destroy()
            self.main_area = None
        if self.nav_frame:
            self.nav_frame.destroy()
            self.nav_frame = None

        # Navigation panel
        self.nav_frame = tk.Frame(self, bg="#2c3e50", width=180)
        self.nav_frame.pack(side=tk.LEFT, fill=tk.Y)
        # Add navigation buttons
        btn_add = tk.Button(self.nav_frame, text="Add User", font=("Arial", 12), command=self.show_add_face, width=15, pady=10)
        btn_add.pack(pady=(40, 10), padx=10)
        btn_manage = tk.Button(self.nav_frame, text="Manage Users", font=("Arial", 12), command=self.show_manage_users, width=15, pady=10)
        btn_manage.pack(pady=10, padx=10)
        btn_logout = tk.Button(self.nav_frame, text="Log Out", font=("Arial", 12), command=self.logout, width=15, pady=10, fg="white", bg="#d9534f", activebackground="#c9302c")
        btn_logout.pack(pady=(40, 10), padx=10, side=tk.BOTTOM, anchor="s")

        # Main area
        self.main_area = tk.Frame(self, bg="#fff")
        self.main_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Show registration form by default
        self.show_add_face()
    def __init__(self):
        super().__init__()
        self.title("Facial Recognition Attendance System - Admin")
        self.geometry("900x600")
        self.configure(bg="#f0f0f0")
        self.current_frame = None
        self.search_var = tk.StringVar()
        self.main_area = None
        self.nav_frame = None
        self.show_main()

    def logout(self):
        self.destroy()
        btn_add = tk.Button(self.nav_frame, text="Add User", font=("Arial", 12), command=self.show_add_face, width=15, pady=10)
        btn_add.pack(pady=(40, 10), padx=10)
        btn_manage = tk.Button(self.nav_frame, text="Manage Users", font=("Arial", 12), command=self.show_manage_users, width=15, pady=10)
        btn_manage.pack(pady=10, padx=10)
        btn_logout = tk.Button(self.nav_frame, text="Log Out", font=("Arial", 12), command=self.logout, width=15, pady=10, fg="white", bg="#d9534f", activebackground="#c9302c")
        btn_logout.pack(pady=(40, 10), padx=10, side=tk.BOTTOM, anchor="s")
        # Main area
        self.main_area = tk.Frame(self, bg="#fff")
        self.main_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Show registration form by default
        self.show_add_face()

    def logout(self):
        self.destroy()
        # Relaunch login window
        launch_login()
    def show_add_face(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = tk.Frame(self.main_area, bg="#fff")
        self.current_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(self.current_frame, text="Register New Student", font=("Arial", 16), bg="#fff").pack(pady=10)
        form_frame = tk.Frame(self.current_frame, bg="#fff")
        form_frame.pack(pady=10)
        fields = ["Name", "StudentID", "Email", "Phone", "Faculty", "Course", "Department", "Year"]
        self.form_vars = {f: tk.StringVar() for f in fields}
        # Dropdown options
        faculty_options = [
            "Science", "Engineering", "Business", "Arts", "Education", "Law", "Medicine", "Agriculture", "Computing", "Other"
        ]
        course_options = [
            "Computer Science", "Mechanical Engineering", "Business Administration", "English", "Mathematics", "Physics", "Law", "Medicine", "Agriculture", "Other"
        ]
        for i, field in enumerate(fields):
            tk.Label(form_frame, text=field+":", bg="#fff").grid(row=i, column=0, sticky=tk.W, pady=2)
            if field == "Faculty":
                faculty_combo = ttk.Combobox(form_frame, textvariable=self.form_vars[field], values=faculty_options, state="readonly", width=28)
                faculty_combo.grid(row=i, column=1, pady=2)
            elif field == "Course":
                course_combo = ttk.Combobox(form_frame, textvariable=self.form_vars[field], values=course_options, state="readonly", width=28)
                course_combo.grid(row=i, column=1, pady=2)
            else:
                tk.Entry(form_frame, textvariable=self.form_vars[field], width=30).grid(row=i, column=1, pady=2)
        tk.Button(self.current_frame, text="Register Student", command=self.register_student).pack(pady=10)
        self.capture_btn = tk.Button(self.current_frame, text="Capture Face", command=self.open_add_faces, state=tk.DISABLED)
        self.capture_btn.pack(pady=5)
        self.capture_note = tk.Label(self.current_frame, text="Please register first, then capture face.", font=("Arial", 10), bg="#fff", fg="gray")
        self.capture_note.pack(pady=5)
    # show_add_face is now defined below, and only one register_student method exists

    def register_student(self):
        # Validate required fields
        if not self.form_vars["Name"].get().strip() or not self.form_vars["StudentID"].get().strip():
            messagebox.showerror("Error", "Name and StudentID are required.")
            return
        from datetime import datetime
        registration_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        row = [self.form_vars[f].get().strip() for f in ["Name", "StudentID", "Email", "Phone", "Faculty", "Course", "Department", "Year"]]
        row.append("Student")
        row.append(registration_date)
        row.append('0')  # Active: 0 = inactive by default
        write_header = not os.path.exists(CSV_PATH)
        if not write_header:
            with open(CSV_PATH, newline='') as csvfile:
                reader = csv.reader(csvfile)
                header = next(reader, [])
                if 'Active' not in header:
                    write_header = True
        with open(CSV_PATH, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            if write_header:
                writer.writerow(["Name", "StudentID", "Email", "Phone", "Faculty", "Course", "Department", "Year", "Role", "RegistrationDate", "Active"])
            writer.writerow(row)
        # Store last registered user details for face capture
        self.last_registered_user = {
            'Name': self.form_vars['Name'].get().strip(),
            'StudentID': self.form_vars['StudentID'].get().strip(),
            'Email': self.form_vars['Email'].get().strip(),
            'Phone': self.form_vars['Phone'].get().strip(),
            'Faculty': self.form_vars['Faculty'].get().strip(),
            'Course': self.form_vars['Course'].get().strip(),
            'Department': self.form_vars['Department'].get().strip(),
            'Year': self.form_vars['Year'].get().strip(),
            'RegistrationDate': registration_date
        }
        messagebox.showinfo("Success", f"Student '{self.form_vars['Name'].get()}' registered.")
        for var in self.form_vars.values():
            var.set("")
        # Enable Capture Face button
        self.capture_btn.config(state=tk.NORMAL)
        self.capture_note.config(text="Now click 'Capture Face' to register the face.", fg="green")

    def open_add_faces(self):
        import subprocess, sys, os
        try:
            python_exe = sys.executable
            # Gather user details from last registration
            if hasattr(self, 'last_registered_user'):
                user = self.last_registered_user
            else:
                messagebox.showerror("Error", "No user registered. Please register a student first.")
                return
            args = [
                python_exe,
                os.path.join(os.path.dirname(__file__), 'add_faces.py'),
                user['Name'],
                user['StudentID'],
                user['Email'],
                user['Phone'],
                user['Department'],
                user['Year'],
                "Student",
                user['RegistrationDate']
            ]
            subprocess.Popen(args)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open face capture window: {e}")

    def show_manage_users(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = tk.Frame(self.main_area, bg="#fff")
        self.current_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(self.current_frame, text="Registered Users", font=("Arial", 16), bg="#fff").pack(pady=10)
        search_frame = tk.Frame(self.current_frame, bg="#fff")
        search_frame.pack(pady=5)
        tk.Label(search_frame, text="Search:", bg="#fff").pack(side=tk.LEFT)
        search_entry = tk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT)
        search_entry.bind('<KeyRelease>', lambda e: self.load_users())
        # Filter by Active status
        self.active_filter_var = tk.StringVar(value="All")
        tk.Label(search_frame, text="  Status:", bg="#fff").pack(side=tk.LEFT)
        active_combo = ttk.Combobox(search_frame, textvariable=self.active_filter_var, values=["All", "Active", "Inactive"], state="readonly", width=8)
        active_combo.pack(side=tk.LEFT, padx=2)
        active_combo.bind("<<ComboboxSelected>>", lambda e: self.load_users())
        # Filter by Department
        self.dept_filter_var = tk.StringVar(value="All")
        tk.Label(search_frame, text="  Department:", bg="#fff").pack(side=tk.LEFT)
        # Get unique departments from CSV
        dept_options = ["All"]
        if os.path.exists(CSV_PATH):
            with open(CSV_PATH, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                depts = set(row['Department'] for row in reader if row.get('Department'))
                dept_options += sorted(depts)
        dept_combo = ttk.Combobox(search_frame, textvariable=self.dept_filter_var, values=dept_options, state="readonly", width=12)
        dept_combo.pack(side=tk.LEFT, padx=2)
        dept_combo.bind("<<ComboboxSelected>>", lambda e: self.load_users())
        # Treeview for users
        columns = ("Name", "StudentID", "Email", "Phone", "Faculty", "Course", "Department", "Year", "Role", "RegistrationDate", "Active")
        self.users_tree = ttk.Treeview(self.current_frame, columns=columns, show="headings", height=15)
        for col in columns:
            self.users_tree.heading(col, text=col)
            self.users_tree.column(col, width=100, anchor='center')
        self.users_tree.pack(pady=10, fill=tk.X)
        self.load_users()
        btn_frame = tk.Frame(self.current_frame, bg="#fff")
        btn_frame.pack(pady=10)
        del_btn = tk.Button(btn_frame, text="Soft Delete/Restore", command=self.toggle_active, fg="red")
        del_btn.pack(side=tk.LEFT, padx=5)
        edit_btn = tk.Button(btn_frame, text="Edit User Info", command=self.edit_user)
        edit_btn.pack(side=tk.LEFT, padx=5)

    def load_users(self):
        # Clear treeview
        if hasattr(self, 'users_tree'):
            for item in self.users_tree.get_children():
                self.users_tree.delete(item)
        filter_text = self.search_var.get().lower()
        active_filter = getattr(self, 'active_filter_var', tk.StringVar(value="All")).get()
        dept_filter = getattr(self, 'dept_filter_var', tk.StringVar(value="All")).get()
        if os.path.exists(CSV_PATH):
            with open(CSV_PATH, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    display = f"{row['Name']} {row['StudentID']} {row['Email']} {row.get('Active','1')} {row.get('Department','')}"
                    # Apply filters
                    if filter_text and filter_text not in display.lower():
                        continue
                    if active_filter == "Active" and row.get('Active','1') != '1':
                        continue
                    if active_filter == "Inactive" and row.get('Active','1') == '1':
                        continue
                    if dept_filter != "All" and row.get('Department','') != dept_filter:
                        continue
                    values = [row.get(col, '') for col in self.users_tree['columns']]
                    self.users_tree.insert('', tk.END, values=values)

    def toggle_active(self):
        sel = self.users_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Please select a user to soft delete/restore.")
            return
        user_item = sel[0]
        user_name = self.users_tree.item(user_item)['values'][0]
        # Confirmation dialog
        if not messagebox.askyesno("Confirm", f"Toggle active status for '{user_name}'?"):
            return
        # Update CSV
        users = []
        with open(CSV_PATH, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['Name'] == user_name:
                    row['Active'] = '0' if row.get('Active','1')=='1' else '1'
                users.append(row)
        with open(CSV_PATH, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=["Name", "StudentID", "Email", "Phone", "Department", "Year", "Role", "RegistrationDate", "Active"])
            writer.writeheader()
            writer.writerows(users)
        self.load_users()
        messagebox.showinfo("User Updated", f"User '{user_name}' active status toggled.")

    def edit_user(self):
        sel = self.users_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Please select a user to edit.")
            return
        user_item = sel[0]
        user_name = self.users_tree.item(user_item)['values'][0]
        # Load user info
        with open(CSV_PATH, newline='') as csvfile:
            reader = list(csv.DictReader(csvfile))
        user = next((row for row in reader if row['Name'] == user_name), None)
        if not user:
            messagebox.showerror("Error", "User not found.")
            return
        edit_win = tk.Toplevel(self)
        edit_win.title(f"Edit User: {user_name}")
        entries = {}
        for i, field in enumerate(["Name", "StudentID", "Email", "Phone", "Faculty", "Course", "Department", "Year", "Role"]):
            tk.Label(edit_win, text=field).grid(row=i, column=0)
            ent = tk.Entry(edit_win)
            ent.insert(0, user.get(field, ""))
            ent.grid(row=i, column=1)
            entries[field] = ent
        def save_edits():
            new_name = entries["Name"].get().strip()
            name_changed = (new_name != user_name)
            for row in reader:
                if row['Name'] == user_name:
                    for field in entries:
                        row[field] = entries[field].get()
            with open(CSV_PATH, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=["Name", "StudentID", "Email", "Phone", "Faculty", "Course", "Department", "Year", "Role", "RegistrationDate", "Active"])
                writer.writeheader()
                writer.writerows(reader)
            # Update embeddings.pkl if name changed
            if name_changed:
                embeddings_path = os.path.join(DATA_DIR, "embeddings.pkl")
                if os.path.exists(embeddings_path):
                    with open(embeddings_path, "rb") as f:
                        embeddings = pickle.load(f)
                    if user_name in embeddings:
                        embeddings[new_name] = embeddings.pop(user_name)
                        with open(embeddings_path, "wb") as f:
                            pickle.dump(embeddings, f)
            edit_win.destroy()
            self.load_users()
            messagebox.showinfo("User Updated", f"User '{user_name}' info updated.")
        tk.Button(edit_win, text="Save", command=save_edits).grid(row=10, column=0, columnspan=2)

# --- Simple Admin Login ---
ADMIN_PASSWORD = "admin"  # Change this to a secure password in production

def admin_login():
    login_win = tk.Tk()
    login_win.title("Admin Login")
    login_win.geometry("300x150")
    tk.Label(login_win, text="Admin Password:").pack(pady=10)
    pwd_var = tk.StringVar()
    pwd_entry = tk.Entry(login_win, textvariable=pwd_var, show='*')
    pwd_entry.pack(pady=5)
    result = {'ok': False}
    def check():
        if pwd_var.get() == ADMIN_PASSWORD:
            result['ok'] = True
            login_win.destroy()
        else:
            messagebox.showerror("Login Failed", "Incorrect password.")
    tk.Button(login_win, text="Login", command=check).pack(pady=10)
    pwd_entry.bind('<Return>', lambda e: check())
    pwd_entry.focus()
    login_win.mainloop()
    return result['ok']

def launch_login():
    root = tk.Tk()
    root.title("Facial Recognition Attendance System - Login")
    root.geometry("400x250")
    root.configure(bg="#fff")
    tk.Label(root, text="Admin Login", font=("Arial", 18), bg="#fff").pack(pady=30)
    tk.Label(root, text="Admin Password:", bg="#fff").pack(pady=10)
    pwd_var = tk.StringVar()
    pwd_entry = tk.Entry(root, textvariable=pwd_var, show='*', font=("Arial", 12))
    pwd_entry.pack(pady=5)
    def check_login():
        ADMIN_PASSWORD = "admin"
        if pwd_var.get() == ADMIN_PASSWORD:
            root.destroy()
            app = AddFacesGUI()
            app.mainloop()
        else:
            messagebox.showerror("Login Failed", "Incorrect password.")
    login_btn = tk.Button(root, text="Login", font=("Arial", 12), command=check_login)
    login_btn.pack(pady=20)
    pwd_entry.bind('<Return>', lambda e: check_login())
    pwd_entry.focus()
    root.mainloop()

if __name__ == "__main__":
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    ensure_active_column()
    launch_login()
