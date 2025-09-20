# gui.py
"""
Tkinter-based GUI for Facial Recognition Attendance System (MVP)

This file is based on your existing admin GUI and extends it with a
"Manage Lecturers" panel. It intentionally does not modify existing
user flows or SQL. The GUI will attempt to call lecturer-related
methods on your UserDataManager — if those methods are missing it
will show friendly errors so you can implement the DB layer next.
"""

import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
import traceback

# Import DB manager provided in user_data_manager.py
from user_data_manager import DatabaseManager, UserDataManager


# -------------------------
# Utility functions
# -------------------------
def resource_path(filename):
    """Return absolute path for filename located next to this script."""
    return os.path.join(os.path.dirname(__file__), filename)


def safe_call(obj, method_name, *args, **kwargs):
    """
    Helper: call method_name on obj if present, otherwise raise AttributeError
    with a clear message for the admin/maintainer.
    """
    if not hasattr(obj, method_name):
        raise AttributeError(f"Required method '{method_name}' not found on {obj.__class__.__name__}. "
                             "Please implement it in user_data_manager.py")
    return getattr(obj, method_name)(*args, **kwargs)


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
                stored = row.get("password") or row.get("pwd") or ""
                if stored == password:
                    return row
                return None
    except Exception as e:
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

        # Show splash, then login
        self.splash_frame = tk.Frame(self, bg="#2c3e50")
        self.splash_frame.pack(fill="both", expand=True)
        splash_label = tk.Label(self.splash_frame, text="Getting things ready for you, please wait...", font=("Arial", 18), fg="white", bg="#2c3e50")
        splash_label.pack(expand=True, fill="both")
        self.after(800, self._remove_splash_and_show_login)

    def _remove_splash_and_show_login(self):
        self.splash_frame.destroy()
        self.container = tk.Frame(self)
        self.container.pack(fill="both", expand=True)
        self.show_login()

    def show_login(self):
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

        tk.Label(form, text="Admin Panel", font=("Arial", 16), bg="#ffffff").grid(row=0, column=0, columnspan=2, pady=(0, 12))

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
            self.app.show_dashboard()
        else:
            messagebox.showerror("Login Failed", "Invalid email or password.")

    def open_admin_registration(self):
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
        tk.Button(self.nav_frame, text="Manage Lecturers", width=20, command=self.show_manage_lecturers).pack(pady=8)

        # Admission number input for targeted recognition
        admission_frame = tk.Frame(self.nav_frame, bg="#2b3a42")
        admission_frame.pack(pady=(12, 0))
        tk.Label(admission_frame, text="Admission No.:", bg="#2b3a42", fg="white").pack(side="left", padx=(0, 4))
        self.admission_var = tk.StringVar()
        tk.Entry(admission_frame, textvariable=self.admission_var, width=12).pack(side="left")

        tk.Button(self.nav_frame, text="Simulate Attendance", width=20, command=self.start_attendance).pack(pady=8)
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
        print("[DEBUG] register_student called")
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
            "password": (email + "_pass"),
            "role": "Student",
            "registration_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "active": 1,
            "is_active": 1
        }
        student_dict = {
            "student_id": None,
            "school": None,
            "cohort": None,
            "course": self.add_vars["course"].get().strip(),
            "year_of_study": self.add_vars["year_of_study"].get().strip()
        }

        try:
            student_id = self.user_manager.add_user(user_dict, student_dict)
            print(f"[DEBUG] add_user returned student_id: {student_id}")
            if not student_id or str(student_id).lower() == 'none':
                messagebox.showerror("Registration Error", "Registration failed: No student ID returned. Please check the database and try again.")
                self.last_registered_student = None
                self.capture_btn.config(state="disabled")
                return
            self.last_registered_student = {**user_dict, **student_dict, "student_id": student_id}
            messagebox.showinfo("Registered", f"Student {first} {last} registered. Student ID: {student_id}")
            for sv in self.add_vars.values():
                sv.set("")
            self.capture_btn.config(state="normal")
            # Automatically launch face capture after registration
            self.launch_face_capture()
        except Exception as e:
            print(f"[ERROR] Exception in register_student: {e}")
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to register student: {e}")
            self.last_registered_student = None
            self.capture_btn.config(state="disabled")

    def launch_face_capture(self):
        print(f"[DEBUG] launch_face_capture called. last_registered_student: {self.last_registered_student}")
        if not self.last_registered_student or not self.last_registered_student.get("student_id") or str(self.last_registered_student.get("student_id")).lower() == 'none':
            messagebox.showerror("Error", "No valid student ID found for face capture. Please register a student first.")
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
        col_widths = {
            "student_id": 90,
            "first_name": 110,
            "last_name": 110,
            "email": 180,
            "phone": 120,
            "course": 160,
            "year_of_study": 100,
            "active": 80
        }
        for col in columns:
            tree.heading(col, text=col.replace("_", " ").title())
            tree.column(col, width=col_widths.get(col, 120), anchor="center")
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
            SELECT s.student_id, u.first_name, u.last_name, u.email, u.phone, s.course, s.year_of_study, u.active
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

            # Insert rows into Treeview with correct formatting and value order
            for row in rows:
                formatted = [
                    row["student_id"],
                    row["first_name"],
                    row["last_name"],
                    row["email"],
                    row["phone"],
                    row["course"],
                    row["year_of_study"] if row["year_of_study"] is not None else "",
                    "Active" if row["active"] == 1 else "Inactive"
                ]
                self.users_tree.insert("", "end", values=formatted)

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
        try:
            user = self.user_manager.get_student(student_id)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch user: {e}")
            return
        if not user:
            messagebox.showerror("Error", "Selected user not found in DB.")
            return
        EditUserDialog(self, user, self.user_manager, on_saved=self.load_users)

    # ---------------- Manage Lecturers ----------------
    def show_manage_lecturers(self):
        """
        Show a panel similar to Manage Users, but for lecturers.
        The GUI will call user_manager.get_lecturers(), create_lecturer(...) etc.
        If any method is missing in the user_manager, a friendly error is displayed.
        """
        self.clear_main()
        frame = tk.Frame(self.main_area, bg="#ffffff", padx=12, pady=12)
        frame.pack(fill="both", expand=True)
        self.current_content = frame

        tk.Label(frame, text="Manage Lecturers", font=("Arial", 16), bg="#ffffff").pack(pady=(0, 8))

        control_frame = tk.Frame(frame, bg="#ffffff")
        control_frame.pack(fill="x", pady=(0, 8))

        tk.Label(control_frame, text="Search:", bg="#ffffff").pack(side="left", padx=(6, 4))
        self.lect_search_var = tk.StringVar()
        lect_se = tk.Entry(control_frame, textvariable=self.lect_search_var, width=28)
        lect_se.pack(side="left", padx=4)
        lect_se.bind("<KeyRelease>", lambda e: self.load_lecturers(limit=20))

        self.lect_active_filter_var = tk.StringVar(value="All")
        tk.Label(control_frame, text="Status:", bg="#ffffff").pack(side="left", padx=(12, 4))
        lect_status_combo = ttk.Combobox(control_frame, textvariable=self.lect_active_filter_var, values=["All", "Active", "Inactive"], state="readonly", width=10)
        lect_status_combo.pack(side="left", padx=4)
        lect_status_combo.bind("<<ComboboxSelected>>", lambda e: self.load_lecturers(limit=20))

        # Buttons for lecturer actions
        btn_frame_top = tk.Frame(frame, bg="#ffffff")
        btn_frame_top.pack(fill="x", pady=(6, 6))
        tk.Button(btn_frame_top, text="Create Lecturer", command=self.create_lecturer_dialog).pack(side="left", padx=6)
        tk.Button(btn_frame_top, text="Create Class", command=self.create_class_dialog).pack(side="left", padx=6)
        tk.Button(btn_frame_top, text="Edit Selected", command=self.edit_lecturer).pack(side="left", padx=6)
        tk.Button(btn_frame_top, text="Toggle Active", command=self.toggle_lecturer_active).pack(side="left", padx=6)
        tk.Button(btn_frame_top, text="Assign Classes", command=self.assign_classes_dialog).pack(side="left", padx=6)
        tk.Button(btn_frame_top, text="Reset Password", command=self.reset_lecturer_password).pack(side="left", padx=6)
        tk.Button(btn_frame_top, text="Refresh", command=lambda: self.load_lecturers(limit=20)).pack(side="left", padx=6)


        # Treeview for lecturers (move here from create_class_dialog)
        columns = ("user_id", "lecturer_id", "name", "email", "department", "academic_rank", "hire_date", "status", "office_location", "specialization", "classes", "active")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=16)
        col_widths = {
            "user_id": 90,
            "lecturer_id": 100,
            "name": 140,
            "email": 200,
            "department": 120,
            "academic_rank": 120,
            "hire_date": 110,
            "status": 90,
            "office_location": 120,
            "specialization": 140,
            "classes": 200,
            "active": 80
        }
        for col in columns:
            tree.heading(col, text=col.replace("_", " ").title())
            tree.column(col, width=col_widths.get(col, 120), anchor="w" if col == "classes" else "center")
        tree.pack(fill="both", expand=True, pady=(8, 8))
        self.lecturers_tree = tree

        # Load
        self.load_lecturers(limit=20)

    def create_class_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("Create New Class")
        dlg.geometry("400x420")
        dlg.transient(self)
        dlg.grab_set()

        fields = [
            ("Cohort ID", "cohort_id"),
            ("Lecturer ID", "lecturer_id"),
            ("Class Name", "class_name"),
            ("Code", "code"),
            ("Description", "description"),
            ("Schedule", "schedule"),
        ]
        vars = {}
        form = tk.Frame(dlg)
        form.pack(pady=16, padx=16)
        for i, (label, key) in enumerate(fields):
            tk.Label(form, text=label+":").grid(row=i, column=0, sticky="e", pady=6, padx=6)
            sv = tk.StringVar()
            tk.Entry(form, textvariable=sv, width=28).grid(row=i, column=1, pady=6, padx=6)
            vars[key] = sv

        def on_save():
            class_data = {k: v.get().strip() for k, v in vars.items()}
            if not class_data["class_name"] or not class_data["code"]:
                messagebox.showerror("Validation", "Class Name and Code are required.")
                return
            try:
                class_id = safe_call(self.user_manager, "create_class", class_data)
                messagebox.showinfo("Created", f"Class created with ID: {class_id}")
                dlg.destroy()
                # Optionally refresh class assignment lists if needed
            except AttributeError as e:
                messagebox.showerror("Missing DB Method", str(e))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create class: {e}")

        btns = tk.Frame(dlg)
        btns.pack(pady=12)
        tk.Button(btns, text="Save", command=on_save, width=12).pack(side="left", padx=6)
        tk.Button(btns, text="Cancel", command=dlg.destroy, width=12).pack(side="left", padx=6)

    def load_lecturers(self, limit=20):
        # Clear tree
        try:
            for it in self.lecturers_tree.get_children():
                self.lecturers_tree.delete(it)
        except Exception:
            pass

        search_q = (self.lect_search_var.get() or "").strip().lower() if hasattr(self, "lect_search_var") else ""
        status_filter = self.lect_active_filter_var.get() if hasattr(self, "lect_active_filter_var") else "All"

        try:
            # Use user_manager.get_lecturers() if available
            lecturers = safe_call(self.user_manager, "get_lecturers")
        except AttributeError as e:
            messagebox.showerror("Missing DB Method", str(e))
            return
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to fetch lecturers: {e}")
            return

        count = 0
        for l in lecturers:
            if limit and count >= limit:
                break
            user_id = l.get("user_id") or l.get("id") or l.get("userId") or ""
            lecturer_id = l.get("lecturer_id") or ""
            name = l.get("name") or f"{l.get('first_name','')} {l.get('last_name','')}"
            email = l.get("email") or l.get("lecturer_email") or ""
            department = l.get("department") or ""
            academic_rank = l.get("academic_rank") or ""
            hire_date = l.get("hire_date") or ""
            status_val = l.get("status") or ""
            office_location = l.get("office_location") or ""
            specialization = l.get("specialization") or ""
            active_flag = l.get("active") if "active" in l else l.get("is_active", 1)
            active_text = "Active" if str(active_flag) == "1" else "Inactive"

            # classes: try to obtain via user_manager.get_lecturer_classes(user_id)
            classes_text = ""
            try:
                classes = safe_call(self.user_manager, "get_lecturer_classes", user_id)
                if classes:
                    if isinstance(classes, (list, tuple)):
                        classes_text = ", ".join([str(c.get("class_name") if isinstance(c, dict) else (c.get("name") if isinstance(c, dict) else str(c))) for c in classes])
            except Exception:
                classes_text = ""

            join_text = f"{user_id} {lecturer_id} {name} {email} {department} {academic_rank} {hire_date} {status_val} {office_location} {specialization} {classes_text}".lower()
            if search_q and search_q not in join_text:
                continue
            if status_filter == "Active" and active_text != "Active":
                continue
            if status_filter == "Inactive" and active_text != "Inactive":
                continue

            self.lecturers_tree.insert("", "end", values=(user_id, lecturer_id, name, email, department, academic_rank, hire_date, status_val, office_location, specialization, classes_text, active_text))
            count += 1

    def create_lecturer_dialog(self):
        dlg = LecturerDialog(self, None, self.user_manager, on_saved=lambda: self.load_lecturers(limit=20))
        dlg.grab_set()

    def edit_lecturer(self):
        sel = self.lecturers_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Please select a lecturer to edit.")
            return
        item = sel[0]
        vals = self.lecturers_tree.item(item, "values")
        user_id = vals[0]
        try:
            lecturer = safe_call(self.user_manager, "get_user_by_id") if hasattr(self.user_manager, "get_user_by_id") else None
            if lecturer:
                user = safe_call(self.user_manager, "get_user_by_id", user_id)
            else:
                # fallback to get_lecturers -> find the one we need
                lecturers = safe_call(self.user_manager, "get_lecturers")
                user = next((x for x in lecturers if str(x.get("user_id") or x.get("id") or "") == str(user_id)), None)
        except AttributeError as e:
            messagebox.showerror("Missing DB Method", str(e))
            return
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to fetch lecturer details: {e}")
            return

        if not user:
            messagebox.showerror("Error", "Lecturer not found.")
            return

        dlg = LecturerDialog(self, user, self.user_manager, on_saved=lambda: self.load_lecturers(limit=20))
        dlg.grab_set()

    def toggle_lecturer_active(self):
        sel = self.lecturers_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Please select a lecturer row.")
            return
        item = sel[0]
        vals = self.lecturers_tree.item(item, "values")
        user_id = vals[0]
        try:
            # Preferred method name: toggle_lecturer_active
            safe_call(self.user_manager, "toggle_lecturer_active", user_id)
            messagebox.showinfo("Updated", "Lecturer active status toggled.")
            self.load_lecturers(limit=20)
        except AttributeError:
            # try fallback: toggle_active on UserDataManager
            try:
                self.user_manager.toggle_active(user_id)
                messagebox.showinfo("Updated", "Lecturer active status toggled (fallback).")
                self.load_lecturers(limit=20)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to toggle active for lecturer: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to toggle active for lecturer: {e}")

    def assign_classes_dialog(self):
        sel = self.lecturers_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Please select a lecturer to assign classes to.")
            return
        item = sel[0]
        vals = self.lecturers_tree.item(item, "values")
        user_id = vals[0]
        try:
            # Fetch available classes via user_manager.get_classes()
            classes = safe_call(self.user_manager, "get_classes")
        except AttributeError as e:
            messagebox.showerror("Missing DB Method", str(e))
            return
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to fetch classes: {e}")
            return

        # classes expected to be list of dicts {id, class_name} or similar
        class_map = {}
        items = []
        for c in classes:
            if isinstance(c, dict):
                cid = c.get("id") or c.get("class_id") or c.get("id")
                name = c.get("class_name") or c.get("name") or str(cid)
            else:
                cid = c
                name = str(c)
            class_map[str(cid)] = name
            items.append((str(cid), name))

        # fetch currently assigned classes
        try:
            assigned = safe_call(self.user_manager, "get_lecturer_classes", user_id) or []
            # normalize to list of ids as strings
            assigned_ids = [str(x.get("class_id") if isinstance(x, dict) and x.get("class_id") is not None else (x.get("id") if isinstance(x, dict) and x.get("id") is not None else x)) for x in assigned]
            assigned_ids = [str(i) for i in assigned_ids]
        except Exception:
            assigned_ids = []

        # Create dialog
        dlg = tk.Toplevel(self)
        dlg.title("Assign Classes")
        dlg.geometry("500x420")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text=f"Assign classes to Lecturer: {user_id}", font=("Arial", 12)).pack(pady=(10, 6))

        list_frame = tk.Frame(dlg)
        list_frame.pack(fill="both", expand=True, padx=12, pady=6)

        lb = tk.Listbox(list_frame, selectmode="multiple", width=60, height=15)
        lb.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=lb.yview)
        scrollbar.pack(side="right", fill="y")
        lb.config(yscrollcommand=scrollbar.set)

        # populate listbox
        for idx, (cid, name) in enumerate(items):
            lb.insert("end", f"{cid} - {name}")
            if cid in assigned_ids:
                lb.selection_set(idx)

        def on_save():
            sel_idx = lb.curselection()
            sel_ids = []
            for i in sel_idx:
                raw = lb.get(i)
                cid = raw.split(" - ", 1)[0].strip()
                sel_ids.append(cid)
            try:
                safe_call(self.user_manager, "assign_lecturer_to_classes", user_id, sel_ids)
                messagebox.showinfo("Saved", "Lecturer class assignments updated.")
                dlg.destroy()
                self.load_lecturers(limit=20)
            except AttributeError as e:
                messagebox.showerror("Missing DB Method", str(e))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save assignments: {e}")

        btns = tk.Frame(dlg)
        btns.pack(pady=8)
        tk.Button(btns, text="Save", command=on_save).pack(side="left", padx=6)
        tk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="left", padx=6)

    def reset_lecturer_password(self):
        sel = self.lecturers_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Please select a lecturer to reset password.")
            return
        item = sel[0]
        vals = self.lecturers_tree.item(item, "values")
        user_id = vals[0]
        new_pw = simpledialog.askstring("Reset Password", "Enter new password for lecturer (will be saved hashed by backend):", show="*")
        if new_pw is None:
            return
        try:
            safe_call(self.user_manager, "reset_lecturer_password", user_id, new_pw)
            messagebox.showinfo("Reset", "Password reset successfully.")
        except AttributeError as e:
            messagebox.showerror("Missing DB Method", str(e))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to reset password: {e}")

    # ---------------- Start Attendance ----------------
    def start_attendance(self):
        script_path = resource_path("rec_faces_test.py")
        if not os.path.exists(script_path):
            messagebox.showerror("Error", f"rec_faces_test.py not found at {script_path}")
            return
        python_exe = sys.executable
        admission_no = self.admission_var.get().strip()
        cmd = [python_exe, script_path]
        if admission_no:
            cmd.append(admission_no)
        try:
            subprocess.Popen(cmd)
            if admission_no:
                messagebox.showinfo("Test Mode Started", f"Face recognition test window launched for Admission No: {admission_no}.")
            else:
                messagebox.showinfo("Test Mode Started", "Face recognition test window launched. No attendance will be marked.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch recognition test: {e}")

    # ---------------- Reports (CSV) ----------------
    def export_reports(self):
        messagebox.showinfo("Export", "This will export attendance reports to CSV (To be released).")

    def logout(self):
        if not messagebox.askyesno("Logout", "Are you sure you want to log out?"):
            return
        self.app.current_user = None
        self.app.show_login()


# -------------------------
# Lecturer Create/Edit Dialog
# -------------------------
class LecturerDialog(tk.Toplevel):
    def __init__(self, parent: DashboardFrame, lecturer: dict, user_manager: UserDataManager, on_saved=None):
        super().__init__(parent)
        self.title("Lecturer" + (" - Edit" if lecturer else " - Create"))
        self.geometry("520x560")
        self.transient(parent)
        self.grab_set()
        self.parent = parent
        self.lecturer = lecturer
        self.user_manager = user_manager
        self.on_saved = on_saved

        frame = tk.Frame(self, padx=12, pady=12)
        frame.pack(fill="both", expand=True)

        fields = [
            ("First Name", "first_name"),
            ("Last Name", "last_name"),
            ("Other Name", "other_name"),
            ("Email", "email"),
            ("Phone", "phone"),
            ("Password", "password"),
            ("Department", "department"),
            ("Academic Rank", "academic_rank"),
            ("Hire Date (YYYY-MM-DD)", "hire_date"),
            ("Office Location", "office_location"),
            ("Specialization", "specialization")
        ]
        self.vars = {}
        for i, (label, key) in enumerate(fields):
            tk.Label(frame, text=label + ":", anchor="w").grid(row=i, column=0, sticky="w", pady=6)
            initial = ""
            if lecturer:
                initial = str(lecturer.get(key, lecturer.get(key.lower(), "")))

            # Choose widget type based on field
            if key == "academic_rank":
                sv = tk.StringVar(value=initial)
                cb = ttk.Combobox(frame, textvariable=sv, width=34, state="readonly")
                cb['values'] = ("Lecturer", "Graduate Assistant")
                cb.grid(row=i, column=1, pady=6)
                self.vars[key] = sv
            elif key == "password":
                sv = tk.StringVar(value=initial)
                tk.Entry(frame, textvariable=sv, width=36, show="*").grid(row=i, column=1, pady=6)
                self.vars[key] = sv
            elif key == "active":
                sv = tk.StringVar(value=initial if initial else "1")
                spin = tk.Spinbox(frame, from_=0, to=1, textvariable=sv, width=34)
                spin.grid(row=i, column=1, pady=6)
                self.vars[key] = sv
            elif key in ("created_by", "updated_by", "failed_login_attempts"):
                sv = tk.StringVar(value=initial)
                tk.Entry(frame, textvariable=sv, width=36).grid(row=i, column=1, pady=6)
                self.vars[key] = sv
            elif key == "locked_until":
                sv = tk.StringVar(value=initial)
                tk.Entry(frame, textvariable=sv, width=36).grid(row=i, column=1, pady=6)
                self.vars[key] = sv
            else:
                sv = tk.StringVar(value=initial)
                tk.Entry(frame, textvariable=sv, width=36).grid(row=i, column=1, pady=6)
                self.vars[key] = sv


        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=12)
        tk.Button(btn_frame, text="Save", command=self.save, width=12).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="left", padx=6)

    def save(self):
        # Collect all fields
        lecturer_data = {k: self.vars[k].get().strip() for k in [
            "first_name", "last_name", "other_name", "email", "phone", "password", "department", "academic_rank", "hire_date", "office_location", "specialization"]}

        # Validation: require first_name, last_name, email, password, phone
        if not lecturer_data["first_name"] or not lecturer_data["last_name"] or not lecturer_data["email"] or not lecturer_data["password"] or not lecturer_data["phone"]:
            messagebox.showerror("Validation", "First name, last name, email, phone, and password are required.")
            return

        try:
            if self.lecturer:
                lecturer_table_id = self.lecturer.get("lecturer_table_id") or self.lecturer.get("id")
                safe_call(self.user_manager, "update_lecturer", lecturer_table_id, lecturer_data)
                messagebox.showinfo("Saved", "Lecturer updated.")
            else:
                new_id = safe_call(self.user_manager, "create_lecturer", lecturer_data)
                messagebox.showinfo("Created", f"Lecturer created (id={new_id}).")
            if callable(self.on_saved):
                self.on_saved()
            self.destroy()
        except AttributeError as e:
            messagebox.showerror("Missing DB Method", str(e))
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to save lecturer: {e}")


# -------------------------
# Edit User Dialog (students)
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

        student_id = self.user.get("student_id") or ""
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
