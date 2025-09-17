"""
gui.py

Tkinter-based GUI for Facial Recognition Attendance System (MVP)
This file expects `user_data_manager.py` (with DatabaseManager and UserDataManager)
to be present in the same folder and pointed at your MySQL/MariaDB instance.

Features:
- Login screen (basic email+password check against users table)
- Dashboard with left side panel (Add User, Manage Users, Start Attendance, Logout)
- Add User (student) form (calls UserDataManager.add_user)
- Manage Users table (list, search, toggle active, edit)
- Edit user dialog (update user and student tables via user_data_manager.update_user)
- Launch external face-capture script (add_faces.py) via subprocess with student_id arg
- Minimal inline comments for extensibility

Notes / Assumptions:
- The DB schema must include `users` and `students` tables as per your earlier spec.
- Passwords in DB are assumed to be stored in plain text for MVP (replace with hashes in prod).
- `UserDataManager` is used for CRUD operations. If method names differ, adapt calls.
- Recognition module (camera & matching) is external: GUI launches it via subprocess.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
import os
import re
from datetime import datetime

# Import the DB-backed manager you posted earlier (DatabaseManager, UserDataManager)
from user_data_manager import DatabaseManager, UserDataManager


# -------------------------
# Utility functions
# -------------------------
def resource_path(filename):
    """Return absolute path for filename located next to this script."""
    return os.path.join(os.path.dirname(__file__), filename)


# -------------------------
# Authentication helpers
# -------------------------
def authenticate_admin(email: str, password: str, db_manager: DatabaseManager) -> dict:
    """
    Very small authentication helper:
    - Looks up user by email in users table and checks password (MVP: plaintext).
    - Returns user dict if authenticated, else None.

    NOTE: In production replace with proper password hashing (bcrypt) and secure checks.
    """
    if not email or not password:
        return None

    query = "SELECT * FROM users WHERE email=%s LIMIT 1"
    try:
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (email,))
                row = cur.fetchone()
                if not row:
                    return None
                # NOTE: row['password'] is expected to be stored in DB (plaintext for MVP)
                stored = row.get("password") or row.get("pwd") or ""
                if stored == password:
                    return row
                # if stored is hashed, adapt this function to verify via admin_security_manager
                return None
    except Exception as e:
        # bubble up or return None
        print(f"[auth] DB error: {e}")
        return None


# -------------------------
# Main Application manager
# -------------------------
class Application(tk.Tk):
    def __init__(self, db_manager=None):
        super().__init__()
        self.title("Facial Recognition Attendance System")
        self.geometry("1100x700")
        self.configure(bg="#f0f2f5")

        # Database manager and user manager (DB-backed)
        self.db_manager = db_manager or DatabaseManager()
        self.user_manager = UserDataManager(self.db_manager)

        # Currently logged-in admin info (dict)
        self.current_user = None

        # Frame holder
        self.container = tk.Frame(self)
        self.container.pack(fill="both", expand=True)

        # Start with Login
        self.show_login()

    def show_login(self):
        # Destroy any existing frames in container
        for widget in self.container.winfo_children():
            widget.destroy()
        login = LoginFrame(self.container, app=self)
        login.pack(fill="both", expand=True)

    def show_dashboard(self):
        for widget in self.container.winfo_children():
            widget.destroy()
        dash = DashboardFrame(self.container, app=self)
        dash.pack(fill="both", expand=True)


# -------------------------
# Login Frame
# -------------------------
class LoginFrame(tk.Frame):
    def __init__(self, parent, app: Application):
        super().__init__(parent, bg="#ffffff")
        self.app = app
        self.db_manager = app.db_manager

        # UI layout
        left = tk.Frame(self, bg="#2c3e50", width=340)
        left.pack(side="left", fill="y")

        right = tk.Frame(self, bg="#ffffff")
        right.pack(side="right", fill="both", expand=True)

        # Left branding panel
        tk.Label(left, text="FRS", font=("Helvetica", 36, "bold"), fg="white", bg="#2c3e50").pack(pady=(60, 6))
        tk.Label(left, text="Facial Recognition\nAttendance", font=("Helvetica", 12), fg="white", bg="#2c3e50").pack()
        tk.Label(left, text="Alpha 2", fg="white", bg="#2c3e50").pack(side="bottom", pady=20)

        # Right login form
        form = tk.Frame(right, bg="#ffffff", padx=40, pady=40)
        form.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(form, text="Admin / Lecturer Login", font=("Arial", 16), bg="#ffffff").grid(row=0, column=0, columnspan=2, pady=(0, 12))

        tk.Label(form, text="Email:", bg="#ffffff").grid(row=1, column=0, sticky="e", pady=6)
        self.email_var = tk.StringVar()
        tk.Entry(form, textvariable=self.email_var, width=36).grid(row=1, column=1, pady=6)

        tk.Label(form, text="Password:", bg="#ffffff").grid(row=2, column=0, sticky="e", pady=6)
        self.pwd_var = tk.StringVar()
        pw_entry = tk.Entry(form, textvariable=self.pwd_var, show="*", width=36)
        pw_entry.grid(row=2, column=1, pady=6)
        pw_entry.bind("<Return>", lambda e: self.attempt_login())

        btn_frame = tk.Frame(form, bg="#ffffff")
        btn_frame.grid(row=3, column=0, columnspan=2, pady=12)

        tk.Button(btn_frame, text="Login", width=12, command=self.attempt_login).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Register Admin", width=14, command=self.open_admin_registration).pack(side="left", padx=6)

    def attempt_login(self):
        email = self.email_var.get().strip()
        password = self.pwd_var.get()
        if not email or not password:
            messagebox.showwarning("Missing", "Please enter email and password.")
            return
        user = authenticate_admin(email, password, self.app.db_manager)
        if user:
            self.app.current_user = user
            # move to dashboard
            self.app.show_dashboard()
        else:
            messagebox.showerror("Login Failed", "Invalid email or password.")

    def open_admin_registration(self):
        # Admin registration modal; uses raw SQL for MVP (replace with manager method if available)
        reg = tk.Toplevel(self)
        reg.title("Register Admin")
        reg.geometry("460x380")
        reg.grab_set()

        frame = tk.Frame(reg, padx=12, pady=12)
        frame.pack(fill="both", expand=True)

        fields = [("Username", "username"), ("First Name", "first_name"), ("Last Name", "last_name"),
                  ("Email", "email"), ("Phone", "phone"), ("Password", "password")]
        vars_map = {}
        for i, (label, key) in enumerate(fields):
            tk.Label(frame, text=label + ":").grid(row=i, column=0, sticky="w", pady=6)
            sv = tk.StringVar()
            tk.Entry(frame, textvariable=sv, width=36, show="*" if key == "password" else None).grid(row=i, column=1, pady=6)
            vars_map[key] = sv

        def submit():
            username = vars_map["username"].get().strip()
            first_name = vars_map["first_name"].get().strip()
            last_name = vars_map["last_name"].get().strip()
            email = vars_map["email"].get().strip()
            phone = vars_map["phone"].get().strip()
            password = vars_map["password"].get().strip()

            if not (username and first_name and last_name and email and password):
                messagebox.showerror("Error", "All fields except phone are required.")
                return

            # Insert into DB (simple approach). In prod use AdminDataManager with hashed passwords.
            insert_user_q = """
                INSERT INTO users (first_name, last_name, email, phone, password, role, registration_date, active, created_at, updated_at, created_by, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), 1, NOW(), NOW(), NULL, 1)
            """
            insert_admin_q = """
                INSERT INTO admins (user_id, username, password_hash, email, active, email_verified)
                VALUES (%s, %s, %s, %s, 1, 1)
            """
            try:
                with self.app.db_manager.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(insert_user_q, (first_name, last_name, email, phone, password, "Admin"))
                        user_id = cur.lastrowid
                        cur.execute(insert_admin_q, (user_id, username, password, email))
                    conn.commit()
                messagebox.showinfo("Success", "Admin registered successfully.")
                reg.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to register admin: {e}")

        tk.Button(frame, text="Register Admin", command=submit, width=18).grid(row=len(fields), column=0, columnspan=2, pady=14)


# -------------------------
# Dashboard Frame (full)
# -------------------------
class DashboardFrame(tk.Frame):
    def __init__(self, parent, app: Application):
        super().__init__(parent, bg="#f4f6f8")
        self.app = app
        self.user_manager = app.user_manager
        self.db_manager = app.db_manager
        self.current_content = None

        # Layout: left nav + main
        self.nav_frame = tk.Frame(self, bg="#2b3a42", width=220)
        self.nav_frame.pack(side="left", fill="y")

        self.main_area = tk.Frame(self, bg="#ffffff")
        self.main_area.pack(side="left", fill="both", expand=True)

        # Nav content
        tk.Label(self.nav_frame, text="Admin Panel", bg="#2b3a42", fg="white", font=("Arial", 14)).pack(pady=(18, 8))
        tk.Button(self.nav_frame, text="Add Student", width=20, command=self.show_add_student).pack(pady=8)
        tk.Button(self.nav_frame, text="Manage Users", width=20, command=self.show_manage_users).pack(pady=8)
        tk.Button(self.nav_frame, text="Start Attendance", width=20, command=self.start_attendance_session).pack(pady=8)
        tk.Button(self.nav_frame, text="Reports (CSV)", width=20, command=self.export_reports).pack(pady=8)
        # spacer
        tk.Label(self.nav_frame, text="", bg="#2b3a42").pack(expand=True, fill="y")
        tk.Button(self.nav_frame, text="Logout", fg="white", bg="#d9534f", width=20, command=self.logout).pack(pady=14)

        # Show default view
        self.show_add_student()

    def clear_main(self):
        for w in self.main_area.winfo_children():
            w.destroy()
        self.current_content = None

    # ---------------- Add Student ----------------
    def show_add_student(self):
        self.clear_main()
        frame = tk.Frame(self.main_area, bg="#ffffff", padx=16, pady=16)
        frame.pack(fill="both", expand=True)
        self.current_content = frame

        tk.Label(frame, text="Register New Student", font=("Arial", 16), bg="#ffffff").pack(pady=(0, 12))

        form = tk.Frame(frame, bg="#ffffff")
        form.pack(pady=8, anchor="n")

        fields = [
            ("First Name", "first_name"),
            ("Last Name", "last_name"),
            ("Other Names", "other_names"),
            ("Email", "email"),
            ("Phone", "phone"),
            ("Course", "course"),
            ("Year", "year_of_study"),
        ]
        self.add_vars = {}
        for i, (label, key) in enumerate(fields):
            tk.Label(form, text=label + ":", bg="#ffffff").grid(row=i, column=0, sticky="e", pady=6, padx=6)
            sv = tk.StringVar()
            tk.Entry(form, textvariable=sv, width=38).grid(row=i, column=1, pady=6, padx=6)
            self.add_vars[key] = sv

        btn_frame = tk.Frame(frame, bg="#ffffff")
        btn_frame.pack(pady=12)
        tk.Button(btn_frame, text="Register Student", command=self.register_student, width=16).pack(side="left", padx=6)
        self.capture_btn = tk.Button(btn_frame, text="Capture Face", command=self.launch_face_capture, width=16, state="disabled")
        self.capture_btn.pack(side="left", padx=6)
        self.last_registered_student = None

    def register_student(self):
        # Validate
        first = self.add_vars["first_name"].get().strip()
        last = self.add_vars["last_name"].get().strip()
        email = self.add_vars["email"].get().strip()
        if not first or not last or not email:
            messagebox.showerror("Validation", "First name, last name, and email are required.")
            return

        user_dict = {
            "first_name": first,
            "last_name": last,
            "other_names": self.add_vars["other_names"].get().strip(),
            "email": email,
            "phone": self.add_vars["phone"].get().strip(),
            # For MVP store plaintext password = email reversed (not secure). In prod, set proper password.
            "password": (email + "_pass"),  
            "role": "Student",
            "registration_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "active": 1,
            "is_active": 1
        }
        # For students table, student_id can be auto-assigned or derived. Here we let the DB auto-assign a unique student_id.
        student_dict = {
            "student_id": None,  # if you want external id, set here
            "school": None,
            "cohort": None,
            "course": self.add_vars["course"].get().strip(),
            "year_of_study": self.add_vars["year_of_study"].get().strip()
        }

        try:
            student_id = self.user_manager.add_user(user_dict, student_dict)
            if not student_id or str(student_id).lower() == 'none':
                messagebox.showerror("Registration Error", "Registration failed: No student ID returned. Please check the database and try again.")
                self.last_registered_student = None
                self.capture_btn.config(state="disabled")
                return
            self.last_registered_student = {"student_id": student_id, **user_dict, **student_dict}
            messagebox.showinfo("Registered", f"Student {first} {last} registered. Student ID: {student_id}")
            print(f"[DEBUG] Registered student_id: {student_id}")
            # Clear form
            for sv in self.add_vars.values():
                sv.set("")
            self.capture_btn.config(state="normal")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to register student: {e}")
            self.last_registered_student = None
            self.capture_btn.config(state="disabled")

    def launch_face_capture(self):
        """
        Launch external face-capture script (assumes add_faces.py exists)
        Usage: add_faces.py <student_id>
        """
        if not self.last_registered_student or not self.last_registered_student.get("student_id") or str(self.last_registered_student.get("student_id")).lower() == 'none':
            messagebox.showerror("Error", "No valid student ID found for face capture. Please register a student first.")
            print("[DEBUG] launch_face_capture: last_registered_student:", self.last_registered_student)
            return
        student_id = str(self.last_registered_student["student_id"])
        try:
            python_exe = sys.executable
            script_path = resource_path("add_faces.py")
            if not os.path.exists(script_path):
                messagebox.showerror("Error", f"add_faces.py not found at {script_path}")
                return
            proc = subprocess.run([python_exe, script_path, student_id])
            if proc.returncode == 0:
                messagebox.showinfo("Success", "Face capture completed.")
            else:
                messagebox.showerror("Error", "Face capture failed (see terminal).")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run face capture: {e}")

    # ---------------- Manage Users ----------------
    def show_manage_users(self):
        self.clear_main()
        frame = tk.Frame(self.main_area, bg="#ffffff", padx=12, pady=12)
        frame.pack(fill="both", expand=True)
        self.current_content = frame

        tk.Label(frame, text="Registered Students", font=("Arial", 16), bg="#ffffff").pack(pady=(0, 8))

        control_frame = tk.Frame(frame, bg="#ffffff")
        control_frame.pack(fill="x", pady=(0, 8))

        tk.Label(control_frame, text="Search:", bg="#ffffff").pack(side="left", padx=(6, 4))
        self.search_var = tk.StringVar()
        se = tk.Entry(control_frame, textvariable=self.search_var, width=36)
        se.pack(side="left", padx=4)
        se.bind("<KeyRelease>", lambda e: self.load_users(limit=20))

        self.active_filter_var = tk.StringVar(value="All")
        tk.Label(control_frame, text="Status:", bg="#ffffff").pack(side="left", padx=(12, 4))
        status_combo = ttk.Combobox(control_frame, textvariable=self.active_filter_var, values=["All", "Active", "Inactive"], state="readonly", width=10)
        status_combo.pack(side="left", padx=4)
        status_combo.bind("<<ComboboxSelected>>", lambda e: self.load_users(limit=20))

        # Reset filters to show all users by default
        self.search_var.set("")
        self.active_filter_var.set("All")

        # Treeview
        columns = ("student_id", "first_name", "last_name", "email", "phone", "course", "year_of_study", "active")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=18)
        for col in columns:
            tree.heading(col, text=col.replace("_", " ").title())
            tree.column(col, width=120, anchor="center")
        tree.pack(fill="both", expand=True, pady=(8, 8))
        self.users_tree = tree

        btn_frame = tk.Frame(frame, bg="#ffffff")
        btn_frame.pack(pady=6)
        tk.Button(btn_frame, text="Toggle Active", command=self.toggle_active).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Edit Selected", command=self.edit_user).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Capture Face", command=self.capture_face_for_selected).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Refresh", command=lambda: self.load_users(limit=20)).pack(side="left", padx=6)

        # 🔑 Load first 20 users at startup
        self.load_users(limit=20)


    def capture_face_for_selected(self):
        sel = self.users_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Please select a user to capture face.")
            return
        item = sel[0]
        vals = self.users_tree.item(item, "values")
        student_id = vals[0]
        if not student_id or str(student_id).lower() == 'none':
            messagebox.showerror("Error", "Selected user does not have a valid student ID.")
            return
        try:
            python_exe = sys.executable
            script_path = resource_path("add_faces.py")
            if not os.path.exists(script_path):
                messagebox.showerror("Error", f"add_faces.py not found at {script_path}")
                return
            proc = subprocess.run([python_exe, script_path, str(student_id)])
            if proc.returncode == 0:
                messagebox.showinfo("Success", "Face capture completed.")
            else:
                messagebox.showerror("Error", "Face capture failed (see terminal).")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run face capture: {e}")

        self.load_users()

        def load_users(self, limit=20):
            # Clear table
            for row in self.users_tree.get_children():
                self.users_tree.delete(row)

            search = self.search_var.get().strip()
            status_filter = self.active_filter_var.get()

            query = """
                SELECT s.student_id, s.first_name, s.last_name, u.email, u.phone, s.course, s.year_of_study, u.active
                FROM students s
                JOIN users u ON s.user_id = u.id
                WHERE 1=1
            """
            params = []

            if search:
                query += " AND (s.first_name LIKE %s OR s.last_name LIKE %s OR u.email LIKE %s)"
                params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

            if status_filter != "All":
                query += " AND u.active = %s"
                params.append(1 if status_filter == "Active" else 0)

            query += " ORDER BY s.student_id DESC"
            if limit:
                query += f" LIMIT {limit}"

            try:
                with self.db_manager.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(query, params)
                        rows = cur.fetchall()

                # Insert rows into Treeview
                for row in rows:
                    self.users_tree.insert("", "end", values=row)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load users: {e}")

    def toggle_active(self):
        sel = self.users_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Please select a user row.")
            return
        item = sel[0]
        vals = self.users_tree.item(item, "values")
        student_id = vals[0]
        try:
            self.user_manager.toggle_active(student_id)
            messagebox.showinfo("Updated", "User active status toggled.")
            self.load_users()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to toggle active status: {e}")

    def edit_user(self):
        sel = self.users_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Please select a user to edit.")
            return
        item = sel[0]
        vals = self.users_tree.item(item, "values")
        student_id = vals[0]
        # Fetch full user via user_manager
        try:
            user = self.user_manager.get_student(student_id)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch user: {e}")
            return
        if not user:
            messagebox.showerror("Error", "Selected user not found in DB.")
            return

        # Open edit dialog
        EditUserDialog(self, user, self.user_manager, on_saved=self.load_users)

    # ---------------- Start Attendance ----------------
    def start_attendance_session(self):
        """
        Simple placeholder: in a real system you'd show a dialog to select course/class,
        create a Classes row, then launch recognition module to mark attendance.
        For MVP we just show an instructional message and optionally launch recognition script.
        """
        if not messagebox.askyesno("Start Attendance", "This will launch the recognition module to mark attendance. Continue?"):
            return
        # Launch recognition script (assumes recognition.py or recognition_module exists)
        try:
            python_exe = sys.executable
            rec_script = resource_path("recognition.py")
            if not os.path.exists(rec_script):
                messagebox.showerror("Error", f"recognition.py not found at {rec_script}")
                return
            # You may want to pass additional args (class_id, lecturer_id, etc.)
            proc = subprocess.run([python_exe, rec_script])
            if proc.returncode == 0:
                messagebox.showinfo("Attendance", "Recognition module finished.")
            else:
                messagebox.showerror("Attendance", "Recognition module returned an error. See terminal.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch recognition: {e}")

    # ---------------- Reports (CSV) ----------------
    def export_reports(self):
        # Minimal placeholder for CSV export
        messagebox.showinfo("Export", "This will export attendance reports to CSV (not implemented in MVP).")

    def logout(self):
        if not messagebox.askyesno("Logout", "Are you sure you want to log out?"):
            return
        self.app.current_user = None
        self.app.show_login()


# -------------------------
# Edit User Dialog
# -------------------------
class EditUserDialog(tk.Toplevel):
    def __init__(self, parent: DashboardFrame, user: dict, user_manager: UserDataManager, on_saved=None):
        super().__init__(parent)
        self.title("Edit User")
        self.geometry("480x420")
        self.grab_set()
        self.parent = parent
        self.user = user
        self.user_manager = user_manager
        self.on_saved = on_saved

        frame = tk.Frame(self, padx=12, pady=12)
        frame.pack(fill="both", expand=True)

        fields = [
            ("First Name", "first_name"),
            ("Last Name", "last_name"),
            ("Email", "email"),
            ("Phone", "phone"),
            ("Course", "course"),
            ("Year", "year_of_study"),
            ("Role", "role")
        ]
        self.vars = {}
        for i, (label, key) in enumerate(fields):
            tk.Label(frame, text=label + ":", anchor="w").grid(row=i, column=0, sticky="w", pady=6)
            sv = tk.StringVar(value=str(user.get(key, "")))
            tk.Entry(frame, textvariable=sv, width=36).grid(row=i, column=1, pady=6)
            self.vars[key] = sv

        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=12)
        tk.Button(btn_frame, text="Save", command=self.save, width=12).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="left", padx=6)

    def save(self):
        # Basic validation
        if not self.vars["first_name"].get().strip() or not self.vars["last_name"].get().strip():
            messagebox.showerror("Validation", "First and last names are required.")
            return

        user_updates = {
            "first_name": self.vars["first_name"].get().strip(),
            "last_name": self.vars["last_name"].get().strip(),
            "email": self.vars["email"].get().strip(),
            "phone": self.vars["phone"].get().strip(),
            "role": self.vars["role"].get().strip()
        }
        student_updates = {
            "course": self.vars["course"].get().strip(),
            "year_of_study": self.vars["year_of_study"].get().strip()
        }

        student_id = self.user.get("student_id") or self.user.get("student_id") or ""
        try:
            self.user_manager.update_user(student_id, user_updates, student_updates)
            messagebox.showinfo("Saved", "User updated successfully.")
            if callable(self.on_saved):
                self.on_saved()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update user: {e}")


# -------------------------
# Run if module executed
# -------------------------
if __name__ == "__main__":
    app = Application()
    app.mainloop()
