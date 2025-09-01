import tkinter as tk
from tkinter import ttk, messagebox
import os
from user_data_manager import UserDataManager

class LoginWindow:
    def __init__(self, on_success):
        self.on_success = on_success
        self.root = tk.Tk()
        self.root.title("Facial Recognition Attendance System - Login")
        self.root.geometry("900x600")
        self.root.configure(bg="#fff")
        tk.Label(self.root, text="Admin Login", font=("Arial", 18), bg="#fff").pack(pady=30)
        tk.Label(self.root, text="Email:", bg="#fff").pack(pady=10)
        self.email_var = tk.StringVar()
        email_entry = tk.Entry(self.root, textvariable=self.email_var, font=("Arial", 12))
        email_entry.pack(pady=5)
        tk.Label(self.root, text="Password:", bg="#fff").pack(pady=10)
        self.pwd_var = tk.StringVar()
        pwd_entry = tk.Entry(self.root, textvariable=self.pwd_var, show='*', font=("Arial", 12))
        pwd_entry.pack(pady=5)
        login_btn = tk.Button(self.root, text="Login", font=("Arial", 12), command=self.check_login)
        login_btn.pack(pady=20)
        pwd_entry.bind('<Return>', lambda e: self.check_login())
        email_entry.focus()
        reg_btn = tk.Button(self.root, text="Register Admin", font=("Arial", 12), command=self.open_admin_registration)
        reg_btn.pack(pady=10)
        self.root.mainloop()

    def open_admin_registration(self):
        reg_win = tk.Toplevel(self.root)
        reg_win.title("Register New Admin")
        reg_win.geometry("400x400")
        reg_win.grab_set()
        fields = ["Username", "First Name", "Last Name", "Email", "Phone", "Password"]
        vars = {f: tk.StringVar() for f in fields}
        for i, f in enumerate(fields):
            tk.Label(reg_win, text=f+":").grid(row=i, column=0, sticky=tk.W, pady=5, padx=10)
            show = '*' if f == "Password" else None
            ent = tk.Entry(reg_win, textvariable=vars[f], show=show) if show else tk.Entry(reg_win, textvariable=vars[f])
            ent.grid(row=i, column=1, pady=5, padx=10)
        def submit():
            from user_data_manager import DatabaseManager
            from admin_security_manager import AdminSecurityManager
            dbm = DatabaseManager()
            asm = AdminSecurityManager(dbm)
            username = vars["Username"].get().strip()
            first_name = vars["First Name"].get().strip()
            last_name = vars["Last Name"].get().strip()
            email = vars["Email"].get().strip()
            phone = vars["Phone"].get().strip()
            password = vars["Password"].get().strip()
            if not (username and first_name and last_name and email and password):
                messagebox.showerror("Error", "All fields except phone are required.")
                return
            # Hash password
            password_hash = asm.hash_password(password)
            try:
                with dbm.get_connection() as conn:
                    with conn.cursor() as cur:
                        # Insert user
                        cur.execute("""
                            INSERT INTO users (first_name, last_name, email, phone, password, role, registration_date, active, created_at, updated_at, created_by, is_active)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW(), 1, NOW(), NOW(), NULL, 1)
                        """, (first_name, last_name, email, phone, password_hash, "Admin"))
                        user_id = cur.lastrowid
                        # Insert admin
                        cur.execute("""
                            INSERT INTO admins (user_id, username, password_hash, email, active, email_verified)
                            VALUES (%s, %s, %s, %s, 1, 1)
                        """, (user_id, username, password_hash, email))
                    conn.commit()
                messagebox.showinfo("Success", f"Admin '{username}' registered successfully.")
                reg_win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to register admin: {e}")
        submit_btn = tk.Button(reg_win, text="Register", command=submit)
        submit_btn.grid(row=len(fields), column=0, columnspan=2, pady=20)
    def check_login(self):
        from admin_data_manager import AdminDataManager
        from datetime import datetime
        import re
        email = self.email_var.get().strip()
        password = self.pwd_var.get()
        admin_manager = AdminDataManager()
        try:
            success, msg = admin_manager.validate_admin_login(email, password, max_attempts=3, lock_minutes=2)
            if success:
                self.root.destroy()
                self.on_success()
            else:
                # If account is locked, show countdown
                lock_match = re.search(r"Account locked until ([\d\- :]+)", str(msg))
                if lock_match:
                    unlock_time_str = lock_match.group(1)
                    try:
                        unlock_time = datetime.strptime(unlock_time_str, "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        unlock_time = None
                    if unlock_time:
                        self.show_lock_countdown(unlock_time)
                        return
                messagebox.showerror("Login Failed", msg or "Incorrect email or password, or inactive account.")
        except Exception as e:
            messagebox.showerror("Login Error", f"Error during login: {e}")

    def show_lock_countdown(self, unlock_time):
        from datetime import datetime
        countdown_win = tk.Toplevel(self.root)
        countdown_win.title("Account Locked")
        countdown_win.geometry("350x150")
        countdown_win.grab_set()
        label = tk.Label(countdown_win, text="Account is locked.", font=("Arial", 14))
        label.pack(pady=10)
        timer_label = tk.Label(countdown_win, text="", font=("Arial", 12))
        timer_label.pack(pady=10)
        def update_timer():
            now = datetime.now()
            remaining = (unlock_time - now).total_seconds()
            if remaining > 0:
                mins, secs = divmod(int(remaining), 60)
                timer_label.config(text=f"Try again in {mins:02d}:{secs:02d}")
                countdown_win.after(1000, update_timer)
            else:
                timer_label.config(text="You can now try logging in again.")
                countdown_win.after(2000, countdown_win.destroy)
        update_timer()


class AddFacesGUI(tk.Tk):
    def __init__(self, data_manager=None):
        super().__init__()
        self.title("Facial Recognition Attendance System - Admin")
        self.geometry("900x600")
        self.configure(bg="#f0f0f0")
        self.current_frame = None
        self.search_var = tk.StringVar()
        self.main_area = None
        self.nav_frame = None
        self.data_manager = data_manager or UserDataManager()
        self.show_main()

    def show_main(self):
        if self.current_frame:
            self.current_frame.destroy()
            self.current_frame = None
        if self.main_area:
            self.main_area.destroy()
            self.main_area = None
        if self.nav_frame:
            self.nav_frame.destroy()
            self.nav_frame = None

        self.nav_frame = tk.Frame(self, bg="#2c3e50", width=180)
        self.nav_frame.pack(side=tk.LEFT, fill=tk.Y)
        btn_add = tk.Button(self.nav_frame, text="Add User", font=("Arial", 12), command=self.show_add_face, width=15, pady=10)
        btn_add.pack(pady=(40, 10), padx=10)
        btn_manage = tk.Button(self.nav_frame, text="Manage Users", font=("Arial", 12), command=self.show_manage_users, width=15, pady=10)
        btn_manage.pack(pady=10, padx=10)
        btn_logout = tk.Button(self.nav_frame, text="Log Out", font=("Arial", 12), command=self.logout, width=15, pady=10, fg="white", bg="#d9534f", activebackground="#c9302c")
        btn_logout.pack(pady=(40, 10), padx=10, side=tk.BOTTOM, anchor="s")

        self.main_area = tk.Frame(self, bg="#fff")
        self.main_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.show_add_face()

    def logout(self):
        self.destroy()
        LoginWindow(lambda: AddFacesGUI(self.data_manager).mainloop())

    def show_add_face(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = tk.Frame(self.main_area, bg="#fff")
        self.current_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(self.current_frame, text="Register New Student", font=("Arial", 16), bg="#fff").pack(pady=10)
        form_frame = tk.Frame(self.current_frame, bg="#fff")
        form_frame.pack(pady=10)
        # Collect all fields from users and students tables, but hide some from GUI
        user_fields = [
            "First Name", "Last Name", "Email", "Phone", "Password", "Role", "Created By"
        ]
        student_fields = [
            "Student ID", "School", "Cohort", "Course"
        ]
        gui_fields = user_fields + student_fields
        self.form_vars = {f: tk.StringVar() for f in gui_fields}
        # Hidden fields (auto-filled)
        hidden_fields = ["Registration Date", "Active", "Created At", "Updated At", "Is Active"]
        for f in hidden_fields:
            self.form_vars[f] = tk.StringVar()

        # Dropdown options for school and course
        school_options = [
            "Science", "Engineering", "Business", "Arts", "Education", "Law", "Medicine", "Agriculture", "Computing", "Other"
        ]
        course_options = [
            "Computer Science", "Mechanical Engineering", "Business Administration", "English", "Mathematics", "Physics", "Law", "Medicine", "Agriculture", "Other"
        ]

        for i, field in enumerate(gui_fields):
            tk.Label(form_frame, text=field+":", bg="#fff").grid(row=i, column=0, sticky=tk.W, pady=2)
            if field == "School":
                school_combo = ttk.Combobox(form_frame, textvariable=self.form_vars[field], values=school_options, state="readonly", width=28)
                school_combo.grid(row=i, column=1, pady=2)
            elif field == "Course":
                course_combo = ttk.Combobox(form_frame, textvariable=self.form_vars[field], values=course_options, state="readonly", width=28)
                course_combo.grid(row=i, column=1, pady=2)
            elif field == "Role":
                role_combo = ttk.Combobox(form_frame, textvariable=self.form_vars[field], values=["Student", "Admin", "Staff"], state="readonly", width=28)
                role_combo.grid(row=i, column=1, pady=2)
            else:
                tk.Entry(form_frame, textvariable=self.form_vars[field], width=30).grid(row=i, column=1, pady=2)
        tk.Button(self.current_frame, text="Register Student", command=self.register_student).pack(pady=10)
        self.capture_btn = tk.Button(self.current_frame, text="Capture Face", command=self.open_add_faces, state=tk.DISABLED)
        self.capture_btn.pack(pady=5)
        self.capture_note = tk.Label(self.current_frame, text="Please register first, then capture face.", font=("Arial", 10), bg="#fff", fg="gray")
        self.capture_note.pack(pady=5)

    def register_student(self):
        # Validate required fields
        if not self.form_vars["First Name"].get().strip() or not self.form_vars["Student ID"].get().strip():
            messagebox.showerror("Error", "First Name and Student ID are required.")
            return
        from datetime import datetime
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # Auto-fill hidden fields
        self.form_vars["Registration Date"].set(now_str)
        self.form_vars["Created At"].set(now_str)
        self.form_vars["Updated At"].set(now_str)
        self.form_vars["Active"].set("1")
        self.form_vars["Is Active"].set("1")
        user_dict = {
            "first_name": self.form_vars["First Name"].get().strip(),
            "last_name": self.form_vars["Last Name"].get().strip(),
            "email": self.form_vars["Email"].get().strip(),
            "phone": self.form_vars["Phone"].get().strip(),
            "password": self.form_vars["Password"].get().strip(),
            "role": self.form_vars["Role"].get().strip(),
            "registration_date": self.form_vars["Registration Date"].get().strip(),
            "active": int(self.form_vars["Active"].get().strip()),
            "created_at": self.form_vars["Created At"].get().strip(),
            "updated_at": self.form_vars["Updated At"].get().strip(),
            "created_by": self.form_vars["Created By"].get().strip() or None,
            "is_active": int(self.form_vars["Is Active"].get().strip())
        }
        student_dict = {
            "student_id": self.form_vars["Student ID"].get().strip(),
            "school": self.form_vars["School"].get().strip(),
            "cohort": self.form_vars["Cohort"].get().strip(),
            "course": self.form_vars["Course"].get().strip()
        }
        try:
            self.data_manager.add_user(user_dict, student_dict)
            self.last_registered_user = {**user_dict, **student_dict}
            messagebox.showinfo("Success", f"Student '{user_dict['first_name']} {user_dict['last_name']}' registered. Now capture face to complete registration.")
            for var in self.form_vars.values():
                var.set("")
            self.capture_btn.config(state=tk.NORMAL)
            self.capture_note.config(text="Now click 'Capture Face' to register the face.", fg="green")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to register student: {e}")

    def open_add_faces(self):
        import subprocess, sys, os
        try:
            python_exe = sys.executable
            if hasattr(self, 'last_registered_user'):
                user = self.last_registered_user
            else:
                messagebox.showerror("Error", "No user registered. Please register a student first.")
                return
            student_id = user['student_id']
            # Student is already in DB, so just proceed to face capture
            args = [
                python_exe,
                os.path.join(os.path.dirname(__file__), 'add_faces.py'),
                student_id
            ]
            # Run add_faces.py and wait for it to finish
            proc = subprocess.run(args)
            if proc.returncode == 0:
                messagebox.showinfo("Success", "Face captured and student registration complete.")
            else:
                messagebox.showerror("Error", "Face capture failed. Registration not saved.")
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
        self.active_filter_var = tk.StringVar(value="All")
        tk.Label(search_frame, text="  Status:", bg="#fff").pack(side=tk.LEFT)
        active_combo = ttk.Combobox(search_frame, textvariable=self.active_filter_var, values=["All", "Active", "Inactive"], state="readonly", width=8)
        active_combo.pack(side=tk.LEFT, padx=2)
        active_combo.bind("<<ComboboxSelected>>", lambda e: self.load_users())
        self.dept_filter_var = tk.StringVar(value="All")
        tk.Label(search_frame, text="  Department:", bg="#fff").pack(side=tk.LEFT)
        dept_options = ["All"]
        users = self.data_manager.get_users()
        depts = set(row['Department'] for row in users if row.get('Department'))
        dept_options += sorted(depts)
        dept_combo = ttk.Combobox(search_frame, textvariable=self.dept_filter_var, values=dept_options, state="readonly", width=12)
        dept_combo.pack(side=tk.LEFT, padx=2)
        dept_combo.bind("<<ComboboxSelected>>", lambda e: self.load_users())
        columns = ("first_name", "last_name", "student_id", "email", "phone", "school", "cohort", "course", "role", "registration_date", "active")
        self.users_tree = ttk.Treeview(self.current_frame, columns=columns, show="headings", height=15)
        for col in columns:
            self.users_tree.heading(col, text=col.replace('_', ' ').title())
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
        if hasattr(self, 'users_tree'):
            for item in self.users_tree.get_children():
                self.users_tree.delete(item)
        filter_text = self.search_var.get().strip().lower()
        active_filter = getattr(self, 'active_filter_var', tk.StringVar(value="All")).get()
        dept_filter = getattr(self, 'dept_filter_var', tk.StringVar(value="All")).get()
        users = self.data_manager.get_users()
        for row in users:
            student_id = str(row.get('student_id', '')).lower()
            if filter_text and filter_text not in student_id:
                continue
            if active_filter == "Active" and str(row.get('active','1')) != '1':
                continue
            if active_filter == "Inactive" and str(row.get('active','1')) == '1':
                continue
            if dept_filter != "All" and row.get('school','') != dept_filter:
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
        if not messagebox.askyesno("Confirm", f"Toggle active status for '{user_name}'?"):
            return
        self.data_manager.toggle_active(user_name)
        self.load_users()
        messagebox.showinfo("User Updated", f"User '{user_name}' active status toggled.")

    def edit_user(self):
        sel = self.users_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Please select a user to edit.")
            return
        user_item = sel[0]
        student_id = str(self.users_tree.item(user_item)['values'][2]).strip()  # student_id is the 3rd column
        users = self.data_manager.get_users()
        user = next((row for row in users if str(row.get('student_id', '')).strip() == student_id), None)
        if not user:
            messagebox.showerror("Error", f"User with student_id '{student_id}' not found. Please check the database and try again.")
            return
        edit_win = tk.Toplevel(self)
        edit_win.title(f"Edit User: {user['first_name']} {user['last_name']}")
        edit_win.geometry("420x420")
        edit_win.grab_set()
        # --- Field definitions ---
        user_fields = ["first_name", "last_name", "email", "phone", "role", "password"]
        student_fields = ["school", "cohort", "course"]
        readonly_fields = ["student_id", "registration_date", "created_at", "updated_at"]
        all_fields = [
            ("Student ID", "student_id", "readonly"),
            ("First Name", "first_name", "text"),
            ("Last Name", "last_name", "text"),
            ("Email", "email", "email"),
            ("Phone", "phone", "phone"),
            ("School", "school", "dropdown", [
                "Science", "Engineering", "Business", "Arts", "Education", "Law", "Medicine", "Agriculture", "Computing", "Other"
            ]),
            ("Cohort", "cohort", "text"),
            ("Course", "course", "dropdown", [
                "Computer Science", "Mechanical Engineering", "Business Administration", "English", "Mathematics", "Physics", "Law", "Medicine", "Agriculture", "Other"
            ]),
            ("Role", "role", "dropdown", ["Student", "Admin", "Staff"]),
            ("Password", "password", "password"),
            ("Registration Date", "registration_date", "readonly"),
            ("Created At", "created_at", "readonly"),
            ("Updated At", "updated_at", "readonly"),
        ]
        # --- Layout ---
        entries = {}
        changed_vars = {}
        row = 0
        for label, field, ftype, *opts in all_fields:
            tk.Label(edit_win, text=label+":").grid(row=row, column=0, sticky=tk.W, pady=2, padx=5)
            val = user.get(field, "")
            var = tk.StringVar(value=val)
            changed_vars[field] = var
            if ftype == "readonly":
                ent = tk.Entry(edit_win, textvariable=var, state="readonly", width=28)
            elif ftype == "dropdown":
                ent = ttk.Combobox(edit_win, textvariable=var, values=opts[0], state="readonly", width=26)
            elif ftype == "password":
                pw_frame = tk.Frame(edit_win)
                ent = tk.Entry(pw_frame, textvariable=var, show="*", width=22)
                ent.pack(side=tk.LEFT)
                show_var = tk.BooleanVar(value=False)
                def toggle_pw(e=None, ent=ent, show_var=show_var):
                    ent.config(show="" if show_var.get() else "*")
                show_btn = tk.Checkbutton(pw_frame, text="Show", variable=show_var, command=toggle_pw)
                show_btn.pack(side=tk.LEFT, padx=2)
                pw_frame.grid(row=row, column=1, pady=2, sticky=tk.W)
                entries[field] = ent
                row += 1
                continue
            elif ftype == "email":
                ent = tk.Entry(edit_win, textvariable=var, width=28)
            elif ftype == "phone":
                ent = tk.Entry(edit_win, textvariable=var, width=28)
            else:
                ent = tk.Entry(edit_win, textvariable=var, width=28)
            ent.grid(row=row, column=1, pady=2, sticky=tk.W)
            entries[field] = ent
            row += 1
        # --- Change tracking ---
        original_values = {field: user.get(field, "") for _, field, _, *rest in all_fields}
        def has_changes():
            for _, field, _, *rest in all_fields:
                if changed_vars[field].get() != str(original_values[field]):
                    return True
            return False
        # --- Validation ---
        import re
        def validate_fields():
            # Required: first_name, last_name, email, phone, school, course
            errors = []
            if not changed_vars["first_name"].get().strip():
                errors.append("First Name is required.")
            if not changed_vars["last_name"].get().strip():
                errors.append("Last Name is required.")
            email_val = changed_vars["email"].get().strip()
            if not email_val or not re.match(r"[^@]+@[^@]+\.[^@]+", email_val):
                errors.append("Valid Email is required.")
            phone_val = changed_vars["phone"].get().strip()
            if not phone_val or not re.match(r"^[0-9+\- ]{7,}$", phone_val):
                errors.append("Valid Phone is required.")
            if not changed_vars["school"].get().strip():
                errors.append("School is required.")
            if not changed_vars["course"].get().strip():
                errors.append("Course is required.")
            return errors
        # --- Save logic ---
        def save_edits():
            if not has_changes():
                messagebox.showinfo("No Changes", "No changes to save.")
                return
            errors = validate_fields()
            if errors:
                messagebox.showerror("Validation Error", "\n".join(errors))
                return
            if not messagebox.askyesno("Confirm Save", "Save changes to this user?"):
                return
            user_updates = {f: changed_vars[f].get().strip() for f in user_fields if f != "password"}
            student_updates = {f: changed_vars[f].get().strip() for f in student_fields}
            # Password reset logic
            pw_val = changed_vars["password"].get().strip()
            if pw_val and pw_val != original_values["password"]:
                user_updates["password"] = pw_val
            try:
                self.data_manager.update_user(student_id, user_updates, student_updates)
                messagebox.showinfo("User Updated", f"User '{changed_vars['first_name'].get()} {changed_vars['last_name'].get()}' info updated.")
                edit_win.destroy()
                self.load_users()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update user: {e}")
        # --- Buttons ---
        btn_frame = tk.Frame(edit_win)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=10)
        save_btn = tk.Button(btn_frame, text="Save", command=save_edits)
        save_btn.pack(side=tk.LEFT, padx=5)
        cancel_btn = tk.Button(btn_frame, text="Cancel", command=edit_win.destroy)
        cancel_btn.pack(side=tk.LEFT, padx=5)
        # --- Advanced: Reset password ---
        def reset_password():
            changed_vars["password"].set("")
            messagebox.showinfo("Reset Password", "Password field cleared. Enter new password and save.")
        reset_btn = tk.Button(btn_frame, text="Reset Password", command=reset_password)
        reset_btn.pack(side=tk.LEFT, padx=5)
        # --- Live change tracking: enable/disable save ---
        def on_change(*args):
            save_btn.config(state=tk.NORMAL if has_changes() else tk.DISABLED)
        for var in changed_vars.values():
            var.trace_add('write', on_change)
        save_btn.config(state=tk.DISABLED)

# Note: The methods for AddFacesGUI should be copied here as in the original script, but for brevity, they are omitted in this snippet.
