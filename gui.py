try:
    from tkcalendar import DateEntry
except ImportError:
    DateEntry = None  # Will show error if not installed

import tkinter as tk
from tkinter import ttk

# ...existing code...

# Place AddClassDialog after tkinter import

class AddClassDialog(tk.Toplevel):
    def __init__(self, parent, on_save=None):
        super().__init__(parent)
        self.title("Add Class / Session")
        self.resizable(False, False)
        self.on_save = on_save
        self.grab_set()

        fields = [
            ("Class Name", "class_name"),
            ("Date (YYYY-MM-DD)", "date"),
            ("Start Time (e.g. 09:00 AM)", "start_time"),
            ("End Time (e.g. 11:00 AM)", "end_time"),
            ("Room", "room"),
            ("Lecturer Name", "lecturer"),
        ]
        self.vars = {}
        for i, (label, key) in enumerate(fields):
            tk.Label(self, text=label+":").grid(row=i, column=0, sticky="e", padx=8, pady=4)
            sv = tk.StringVar()
            tk.Entry(self, textvariable=sv, width=32).grid(row=i, column=1, padx=8, pady=4)
            self.vars[key] = sv

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=10)
        tk.Button(btn_frame, text="Save", command=self.save).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=6)

    def save(self):
        data = {k: v.get().strip() for k, v in self.vars.items()}
        # Basic validation
        if not data["class_name"] or not data["date"] or not data["start_time"] or not data["end_time"] or not data["room"] or not data["lecturer"]:
            tk.messagebox.showerror("Validation", "All fields are required.")
            return
        if self.on_save:
            self.on_save(data)
        tk.messagebox.showinfo("Success", "Class details saved (DB integration needed).")
        self.destroy()
import tkinter as tk
from tkinter import ttk

class EditUserDialog(tk.Toplevel):
    def __init__(self, parent, user, user_manager, on_saved=None):
        super().__init__(parent)
        self.title("Edit User")
        self.user_manager = user_manager
        self.on_saved = on_saved
        self.user = user
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Fields to edit
        fields = [
            ("First Name", "first_name"),
            ("Last Name", "last_name"),
            ("Email", "email"),
            ("Phone", "phone"),
            ("School", "school"),
            ("Cohort", "cohort"),
            ("Course", "course"),
            ("Year of Study", "year_of_study"),
        ]
        self.vars = {}
        for i, (label, key) in enumerate(fields):
            tk.Label(self, text=label+":").grid(row=i, column=0, sticky="e", padx=8, pady=4)
            sv = tk.StringVar(value=user.get(key, ""))
            tk.Entry(self, textvariable=sv, width=32).grid(row=i, column=1, padx=8, pady=4)
            self.vars[key] = sv

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=10)
        tk.Button(btn_frame, text="Save", command=self.save).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=6)

    def save(self):
        # Prepare update dicts
        user_updates = {
            "first_name": self.vars["first_name"].get().strip(),
            "last_name": self.vars["last_name"].get().strip(),
            "email": self.vars["email"].get().strip(),
            "phone": self.vars["phone"].get().strip(),
        }
        student_updates = {
            "school": self.vars["school"].get().strip(),
            "cohort": self.vars["cohort"].get().strip(),
            "course": self.vars["course"].get().strip(),
            "year_of_study": self.vars["year_of_study"].get().strip(),
        }
        student_id = self.user.get("student_id")
        try:
            self.user_manager.update_user(student_id, user_updates, student_updates)
            if self.on_saved:
                self.on_saved()
            tk.messagebox.showinfo("Success", "User updated successfully.")
            self.destroy()
        except Exception as e:
            tk.messagebox.showerror("Error", f"Failed to update user: {e}")
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
        dash.show_add_student()


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
        # Basic validation
        if not email or not password:
            messagebox.showwarning("Missing", "Please enter both email and password.")
            return
        if "@" not in email or "." not in email.split("@")[-1]:
            messagebox.showwarning("Invalid Email", "Please enter a valid email address.")
            return
        if len(password) < 5:
            messagebox.showwarning("Weak Password", "Password must be at least 5 characters long.")
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
    def show_manage_classes(self):
        self.clear_main()
        frame = tk.Frame(self.main_area, bg="#ffffff", padx=16, pady=16)
        frame.pack(fill="both", expand=True)
        self.current_content = frame

        tk.Label(frame, text="Manage Classes / Sessions", font=("Arial", 16), bg="#ffffff").pack(pady=(0, 12))
        tk.Button(frame, text="Add Class / Session", command=self.open_add_class_dialog).pack(pady=8)
        # Placeholder for class/session list
        tk.Label(frame, text="(Class/session list will appear here)", bg="#ffffff", fg="#888").pack(pady=12)

    def open_add_class_dialog(self):
        def on_save(data):
            # TODO: Save to DB via user_manager/db_manager
            print("Class details:", data)
        AddClassDialog(self, on_save=on_save)
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
            "course": self.add_vars["course"].get(),  # Dropdown selection, no .strip() needed
            "year_of_study": self.add_vars["year_of_study"].get().strip()
        }

        try:
            student_id = self.user_manager.add_user(user_dict, student_dict)
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
            messagebox.showerror("Error", f"Failed to register student: {e}")

    def launch_face_capture(self):
        # Launch face capture for the last registered student
        if not self.last_registered_student or not self.last_registered_student.get("student_id"):
            messagebox.showerror("Error", "No student registered to capture face for.")
            return
        student_id = self.last_registered_student["student_id"]
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

        # Nav content (now inside __init__)
        tk.Label(self.nav_frame, text="Admin Panel", bg="#2b3a42", fg="white", font=("Arial", 14)).pack(pady=(18, 8))
        tk.Button(self.nav_frame, text="Add Student", width=20, command=self.show_add_student).pack(pady=8)
        tk.Button(self.nav_frame, text="Manage Students", width=20, command=self.show_manage_users).pack(pady=8)
        tk.Button(self.nav_frame, text="Manage Lecturers", width=20, command=self.show_manage_lecturers).pack(pady=8)
        tk.Button(self.nav_frame, text="Manage Classes", width=20, command=self.show_manage_classes).pack(pady=8)
        tk.Button(self.nav_frame, text="Attendance Sessions", width=20, command=lambda: messagebox.showinfo("Info", "Feature coming soon!")).pack(pady=8)
        tk.Button(self.nav_frame, text="Attendance Reports", width=20, command=self.export_reports).pack(pady=8)
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
        course_options = [
            "Bachelor of Science in Tourism Management (BTM)",
            "Bachelor of Science in Hospitality Management (BHM)",
            "Bachelor of Business Science: Financial Engineering (BBSFENG)",
            "Bachelor of Business Science: Financial Economics (BBSFE)",
            "Bachelor of Business Science: Actuarial Science (BBSACT)",
            "Bachelor Of Science In Informatics And Computer Science (BICS)",
            "Bachelor Of Business Information Technology (BBIT)",
            "BSc. Computer Networks and Cyber Security (BCNS)",
            "Bachelor of Laws (LLB)",
            "Bachelor of Arts in Communication (BAC)",
            "Bachelor of Arts in International Studies",
            "Bachelor of Arts in Development Studies and Philosophy (BDP)",
            "Bachelor of Science in Supply Chain and Operations Management (BSCM)",
            "Bachelor of Financial Services (BFS)",
            "Bachelor Of Science In Electrical and Electronics Engineering (BSEEE)",
            "BSc in Statistics and Data Science (BScSDS)",
            "Bachelor of Commerce (BCOM)"
        ]
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
            ("Other Names (optional)", "other_names"),
            ("Email", "email"),
            ("Phone (optional)", "phone"),
            ("Course", "course"),
            ("Year", "year_of_study"),
        ]
        self.add_vars = {}
        # Tooltip helper
        def add_tooltip(widget, text):
            tooltip = tk.Toplevel(widget, bg="#ffffe0", padx=6, pady=2)
            tooltip.withdraw()
            tooltip.overrideredirect(True)
            label = tk.Label(tooltip, text=text, bg="#ffffe0", relief="solid", borderwidth=1, font=("Arial", 9))
            label.pack()
            def enter(event):
                x = widget.winfo_rootx() + widget.winfo_width() + 8
                y = widget.winfo_rooty()
                tooltip.geometry(f"+{x}+{y}")
                tooltip.deiconify()
            def leave(event):
                tooltip.withdraw()
            widget.bind("<Enter>", enter)
            widget.bind("<Leave>", leave)

        tooltips = {
            "first_name": "Required. Student's first name.",
            "last_name": "Required. Student's last name.",
            "other_names": "Optional. Any other names.",
            "email": "Required. Must be a valid email address.",
            "phone": "Optional. Student's phone number.",
            "course": "Required. Student's course of study.",
            "year_of_study": "Required. Year of study (e.g., 1, 2, 3, 4)."
        }
        country_codes = ['+254', '+1', '+44', '+91', '+61', '+81', '+49', '+33', '+86', '+27']
        country_code_var = tk.StringVar(value='+254')
        for i, (label, key) in enumerate(fields):
            required = key in ["first_name", "last_name", "email", "course", "year_of_study"]
            label_widget = tk.Label(form, text=label + ("*" if required else "") + ":", bg="#ffffff")
            label_widget.grid(row=i, column=0, sticky="e", pady=6, padx=6)
            add_tooltip(label_widget, tooltips.get(key, ""))
            sv = tk.StringVar()
            if key == "course":
                from tkinter import ttk
                course_combo = ttk.Combobox(form, textvariable=sv, values=course_options, state="readonly", width=36)
                course_combo.grid(row=i, column=1, pady=6, padx=6)
            elif key == "phone":
                from tkinter import ttk
                phone_frame = tk.Frame(form, bg="#ffffff")
                phone_frame.grid(row=i, column=1, pady=6, padx=6, sticky="w")
                code_combo = ttk.Combobox(phone_frame, textvariable=country_code_var, values=country_codes, state="readonly", width=6)
                code_combo.pack(side="left", padx=(0, 4))
                tk.Entry(phone_frame, textvariable=sv, width=28).pack(side="left")
            else:
                tk.Entry(form, textvariable=sv, width=38).grid(row=i, column=1, pady=6, padx=6)
            self.add_vars[key] = sv
        self.add_vars['country_code'] = country_code_var

        btn_frame = tk.Frame(frame, bg="#ffffff")
        btn_frame.pack(pady=12)
        tk.Button(btn_frame, text="Register Student", command=self.register_student, width=16).pack(side="left", padx=6)
        self.capture_btn = tk.Button(btn_frame, text="Capture Face", command=self.launch_face_capture, width=16, state="disabled")
        self.capture_btn.pack(side="left", padx=6)
        self.last_registered_student = None

    def assign_students_to_class_dialog(self):
        def unassign_selected():
            selected_class = class_var.get()
            if not selected_class:
                messagebox.showerror("Validation", "Please select a class.")
                return
            class_id = selected_class.split(" - ", 1)[0]
            sel = list(selected_lb.curselection())
            if not sel:
                messagebox.showerror("Validation", "Please select student(s) to unassign.")
                return
            student_ids = []
            for i in sel:
                val = selected_lb.get(i)
                sid = val.split(" - ", 1)[0]
                student_ids.append(sid)
            try:
                self.user_manager.unassign_students_from_class(class_id, student_ids)
                # Remove from UI
                for i in reversed(sel):
                    val = selected_lb.get(i)
                    sid = val.split(" - ", 1)[0]
                    if sid in selected_students:
                        del selected_students[sid]
                    selected_lb.delete(i)
                messagebox.showinfo("Success", f"Unassigned {len(student_ids)} student(s) from class.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to unassign students: {e}")
        def load_assigned_students(event=None):
            # Clear selected list and dict
            selected_lb.delete(0, tk.END)
            selected_students.clear()
            selected = class_var.get()
            if not selected:
                return
            class_id = selected.split(" - ", 1)[0]
            try:
                assigned = self.user_manager.get_student_ids_for_class(class_id)
                # Fetch user info for display
                all_students = self.user_manager.get_users()
                student_map = {str(s.get("student_id")): s for s in all_students}
                for sid in assigned:
                    s = student_map.get(str(sid))
                    if s:
                        name = f"{sid} - {s.get('first_name','')} {s.get('last_name','')} ({s.get('email','')})"
                        selected_students[str(sid)] = name
                        selected_lb.insert(tk.END, name)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load assigned students: {e}")

        # Dialog to assign students to a class (modern flow)

        # Dialog to assign students to a class (modern flow)
        dlg = tk.Toplevel(self)
        dlg.title("Assign Students to Class")
        dlg.geometry("520x420")
        dlg.transient(self)
        dlg.grab_set()

        # Fetch classes
        try:
            classes = self.user_manager.get_classes()
        except Exception:
            classes = []
        class_choices = [(str(c.get("id")), c.get("class_name", str(c.get("id")))) for c in classes]
        tk.Label(dlg, text="Select Class:").pack(pady=(10, 2))
        class_var = tk.StringVar()
        class_combo = ttk.Combobox(dlg, textvariable=class_var, values=[f"{cid} - {name}" for cid, name in class_choices], state="readonly", width=40)
        class_combo.pack(pady=(0, 10))
        if not class_choices:
            messagebox.showwarning("No Classes", "No classes found. Please add a class first.")

        # Search bar
        search_frame = tk.Frame(dlg)
        search_frame.pack(pady=(4, 2))
        tk.Label(search_frame, text="Search Students:").pack(side="left", padx=(0, 4))
        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=search_var, width=32)
        search_entry.pack(side="left")

        # Listbox for search results
        results_lb = tk.Listbox(dlg, selectmode="browse", width=54, height=10)
        results_lb.pack(padx=12, pady=(6, 2))

        # Listbox for selected students
        tk.Label(dlg, text="Selected Students:").pack(pady=(4, 0))
        selected_lb = tk.Listbox(dlg, selectmode="extended", width=54, height=5)
        selected_lb.pack(padx=12, pady=(2, 6))

        # Store selected students as a dict: sid -> display name
        selected_students = {}

        def search_students(event=None):
            # If class changes, reload assigned students
            if event and event.type == '34':  # <<ComboboxSelected>>
                load_assigned_students()
            query = search_var.get().strip().lower()
            results_lb.delete(0, tk.END)
            if not query:
                return
            try:
                all_students = self.user_manager.get_users()
            except Exception:
                all_students = []
            for s in all_students:
                # Only show active accounts
                if not s.get('active', 1):
                    continue
                sid = str(s.get("student_id"))
                name = f"{sid} - {s.get('first_name','')} {s.get('last_name','')} ({s.get('email','')})"
                if query in sid.lower() or query in s.get('first_name','').lower() or query in s.get('last_name','').lower() or query in s.get('email','').lower():
                    results_lb.insert(tk.END, name)

        def add_to_selected(event=None):
            sel = results_lb.curselection()
            if not sel:
                return
            val = results_lb.get(sel[0])
            sid = val.split(" - ", 1)[0]
            if sid not in selected_students:
                selected_students[sid] = val
                selected_lb.insert(tk.END, val)

        def remove_from_selected(event=None):
            sel = list(selected_lb.curselection())
            for i in reversed(sel):
                val = selected_lb.get(i)
                sid = val.split(" - ", 1)[0]
                if sid in selected_students:
                    del selected_students[sid]
                selected_lb.delete(i)

        results_lb.bind("<Double-Button-1>", add_to_selected)
        selected_lb.bind("<Delete>", remove_from_selected)
        search_entry.bind("<KeyRelease>", search_students)
        class_combo.bind("<<ComboboxSelected>>", load_assigned_students)

        def confirm_assignment():
            selected_class = class_var.get()
            if not selected_class:
                messagebox.showerror("Validation", "Please select a class.")
                return
            class_id = selected_class.split(" - ", 1)[0]
            if not selected_students:
                messagebox.showerror("Validation", "Please add at least one student to assign.")
                return
            student_ids = list(selected_students.keys())
            try:
                self.user_manager.assign_students_to_class(class_id, student_ids)
                messagebox.showinfo("Success", f"Assigned {len(student_ids)} student(s) to class.")
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to assign students: {e}")

        btn_frame = tk.Frame(dlg)
        btn_frame.pack(pady=12)
        confirm_btn = tk.Button(btn_frame, text="Confirm Assignment", command=confirm_assignment, width=20)
        confirm_btn.pack(side="left", padx=6)
        unassign_btn = tk.Button(btn_frame, text="Unassign from Class", command=unassign_selected, width=20)
        unassign_btn.pack(side="left", padx=6)

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
        tk.Button(btn_frame, text="Toggle Active", command=self.toggle_active).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Edit Selected", command=self.edit_user).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Capture Face", command=self.capture_face_for_selected).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Refresh", command=lambda: self.load_users(limit=20)).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Assign to Class", command=self.assign_students_to_class_dialog, width=16).pack(side="left", padx=6)
        btn_frame.pack(pady=12)

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
            # Delete existing embeddings before recapturing
            self.user_manager.delete_face_embeddings(student_id)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete existing embeddings: {e}")
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
            query += " AND (u.first_name LIKE %s OR u.last_name LIKE %s OR u.email LIKE %s)"
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


        # Treeview for lecturers (updated columns)
        columns = ("lecturer_id", "first_name", "last_name", "email", "phone", "department", "academic_rank", "office_location", "specialization", "active")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=16)
        col_widths = {
            "lecturer_id": 100,
            "first_name": 110,
            "last_name": 110,
            "email": 200,
            "phone": 120,
            "department": 120,
            "academic_rank": 120,
            "office_location": 120,
            "specialization": 140,
            "active": 80
        }
        for col in columns:
            anchor = "center"
            if col in ("first_name", "last_name", "email", "department", "academic_rank", "office_location", "specialization"):
                anchor = "w"
            tree.heading(col, text=col.replace("_", " ").title())
            tree.column(col, width=col_widths.get(col, 120), anchor=anchor)
        tree.pack(fill="both", expand=True, pady=(8, 8))
        self.lecturers_tree = tree

        # Load
        self.load_lecturers(limit=20)

    def create_class_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("Add New Class")
        dlg.geometry("400x420")
        dlg.transient(self)
        dlg.grab_set()

        # Fetch real cohorts from cohorts_two for dropdown
        try:
            cohorts = safe_call(self.user_manager, "get_cohorts_two")
        except Exception:
            cohorts = []
        cohort_choices = [(str(c.get("id")), f"{c.get('id')} (Course: {c.get('course_id')}, Year: {c.get('year')}, Sem: {c.get('semester')})") for c in cohorts]

        fields = [
            ("Lecturer", "lecturer_id"),
            ("Class Name", "class_name"),
            ("Code", "code"),
            ("Description", "description"),
            ("Date (YYYY-MM-DD)", "date"),
            ("Start Time", "start_time"),
            ("End Time", "end_time"),
            ("Room", "room"),
        ]
        # Fetch real lecturers from lecturers_table_two for dropdown
        try:
            lecturers = safe_call(self.user_manager, "get_lecturers_table_two")
        except Exception:
            lecturers = []
        # Use integer lecturer_id as value, display name or email for clarity
        lecturer_choices = []
        for l in lecturers:
            lid = l.get("lecturer_id")
            # Try to show full name or fallback to email/username
            name = l.get("first_name", "") + " " + l.get("last_name", "")
            if not name.strip():
                name = l.get("name", "")
            if not name.strip():
                name = l.get("email", "")
            lecturer_choices.append((lid, f"{lid} - {name.strip()}"))

        vars = {}
        form = tk.Frame(dlg)
        form.pack(pady=16, padx=16)
        time_options = [f"{h:02d}:{m:02d}" for h in range(7, 22) for m in (0, 30)]  # 07:00 to 21:30
        for i, (label, key) in enumerate(fields):
            tk.Label(form, text=label+":").grid(row=i, column=0, sticky="e", pady=6, padx=6)
            if key == "lecturer_id":
                sv = tk.StringVar()
                cb = ttk.Combobox(form, textvariable=sv, width=26, state="readonly")
                cb['values'] = [desc for lid, desc in lecturer_choices]
                cb.grid(row=i, column=1, pady=6, padx=6)
                vars[key] = (sv, lecturer_choices)
            elif key == "date":
                if DateEntry is None:
                    tk.Label(form, text="Install tkcalendar for date picker").grid(row=i, column=1, pady=6, padx=6)
                    sv = tk.StringVar()
                    vars[key] = sv
                else:
                    sv = tk.StringVar()
                    date_entry = DateEntry(form, textvariable=sv, width=25, date_pattern="yyyy-mm-dd")
                    date_entry.grid(row=i, column=1, pady=6, padx=6)
                    vars[key] = sv
            elif key in ("start_time", "end_time"):
                sv = tk.StringVar()
                cb = ttk.Combobox(form, textvariable=sv, width=26, state="readonly")
                cb['values'] = time_options
                cb.grid(row=i, column=1, pady=6, padx=6)
                vars[key] = sv
            else:
                sv = tk.StringVar()
                tk.Entry(form, textvariable=sv, width=28).grid(row=i, column=1, pady=6, padx=6)
                vars[key] = sv
# NOTE: For date picker support, install tkcalendar:
#   pip install tkcalendar

        def on_save():
            class_data = {}
            for k, v in vars.items():
                if k == "cohort_id":
                    sv, choices = v
                    selected = sv.get()
                    cohort_id = None
                    for cid, desc in choices:
                        if desc == selected:
                            cohort_id = cid
                            break
                    class_data[k] = cohort_id
                elif k == "lecturer_id":
                    sv, choices = v
                    selected = sv.get()
                    lecturer_id = None
                    for lid, desc in choices:
                        if desc == selected:
                            lecturer_id = str(lid)  # Always use string
                            break
                    print(f"[DEBUG] Selected lecturer_id for assignment: {lecturer_id}")
                    class_data[k] = lecturer_id
                else:
                    class_data[k] = v.get().strip()
            # Validation for new fields
            if not class_data["class_name"] or not class_data["code"]:
                messagebox.showerror("Validation", "Class Name and Code are required.")
                return
            if not class_data["lecturer_id"]:
                messagebox.showerror("Validation", "Lecturer selection is required.")
                return
            if not class_data["date"] or not class_data["start_time"] or not class_data["end_time"] or not class_data["room"]:
                messagebox.showerror("Validation", "Date, Start Time, End Time, and Room are required.")
                return
            try:
                class_id = safe_call(self.user_manager, "create_class", class_data)
                # Assign lecturer to class in mapping table
                safe_call(self.user_manager, "assign_lecturer_to_class", class_data["lecturer_id"], class_id)
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

        if not lecturers:
            self.lecturers_tree.insert("", "end", values=("", "", "", "", "", "", "", "", "", ""))
            self.lecturers_tree.set(self.lecturers_tree.get_children()[0], column="first_name", value="No lecturers to display.")
            return

        count = 0
        for idx, l in enumerate(lecturers):
            if limit and count >= limit:
                break
            lecturer_id = l.get("lecturer_id") or ""
            first_name = l.get("first_name", "")
            last_name = l.get("last_name", "")
            email = l.get("email") or l.get("lecturer_email") or ""
            phone = l.get("phone", "")
            department = l.get("department", "")
            academic_rank = l.get("academic_rank", "")
            office_location = l.get("office_location", "")
            specialization = l.get("specialization", "")
            active_flag = l.get("active") if "active" in l else l.get("is_active", 1)
            active_text = "Active" if str(active_flag) == "1" else "Inactive"

            join_text = f"{lecturer_id} {first_name} {last_name} {email} {phone} {department} {academic_rank} {office_location} {specialization}".lower()
            if search_q and search_q not in join_text:
                continue
            if status_filter == "Active" and active_text != "Active":
                continue
            if status_filter == "Inactive" and active_text != "Inactive":
                continue

            row_tags = ("evenrow",) if idx % 2 == 0 else ("oddrow",)
            # Insert row with tag for striping
            self.lecturers_tree.insert("", "end", values=(lecturer_id, first_name, last_name, email, phone, department, academic_rank, office_location, specialization, active_text), tags=row_tags)
            count += 1

        # Apply tag styles for striping
        self.lecturers_tree.tag_configure('evenrow', background='#f7fafd')
        self.lecturers_tree.tag_configure('oddrow', background='#e9f0f7')

        # Color code active status
        for item in self.lecturers_tree.get_children():
            vals = self.lecturers_tree.item(item, "values")
            if vals and vals[-1] == "Active":
                self.lecturers_tree.item(item, tags=self.lecturers_tree.item(item, "tags") + ("active",))
            elif vals and vals[-1] == "Inactive":
                self.lecturers_tree.item(item, tags=self.lecturers_tree.item(item, "tags") + ("inactive",))
        self.lecturers_tree.tag_configure('active', foreground='#228B22')
        self.lecturers_tree.tag_configure('inactive', foreground='#B22222')

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
        lecturer_id = vals[0]  # Now the first column is lecturer_id (L001, etc.)
        try:
            lecturer = self.user_manager.get_lecturer_by_lecturer_id(lecturer_id)
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to fetch lecturer details: {e}")
            return
        if not lecturer:
            messagebox.showerror("Error", "Lecturer not found.")
            return
        dlg = LecturerDialog(self, lecturer, self.user_manager, on_saved=lambda: self.load_lecturers(limit=20))
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

    # ---------------- Manage Classes ----------------
    def show_manage_classes(self):
        self.clear_main()
        frame = tk.Frame(self.main_area, bg="#ffffff", padx=12, pady=12)
        frame.pack(fill="both", expand=True)
        self.current_content = frame

        tk.Label(frame, text="Manage Classes", font=("Arial", 16), bg="#ffffff").pack(pady=(0, 8))

        control_frame = tk.Frame(frame, bg="#ffffff")
        control_frame.pack(fill="x", pady=(0, 8))

        tk.Button(control_frame, text="Add Class", command=self.create_class_dialog).pack(side="left", padx=6)
        tk.Button(control_frame, text="Edit Selected", command=self.edit_class_dialog).pack(side="left", padx=6)
        tk.Button(control_frame, text="Assign Students", command=self.assign_students_to_class_dialog).pack(side="left", padx=6)
        tk.Button(control_frame, text="Refresh", command=self.load_classes).pack(side="left", padx=6)

        columns = ("class_id", "cohort_id", "class_name", "code")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=16)
        col_widths = {
            "class_id": 90,
            "cohort_id": 120,
            "class_name": 160,
            "code": 100
        }
        for col in columns:
            tree.heading(col, text=col.replace("_", " ").title())
            tree.column(col, width=col_widths.get(col, 100), anchor="center")
        tree.pack(fill="both", expand=True, pady=(8, 8))
        self.classes_tree = tree

        self.load_classes()

    def load_classes(self):
        try:
            for row in self.classes_tree.get_children():
                self.classes_tree.delete(row)
        except Exception:
            pass

        try:
            classes = safe_call(self.user_manager, "get_classes")
        except AttributeError as e:
            messagebox.showerror("Missing DB Method", str(e))
            return
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to fetch classes: {e}")
            return

        for c in classes:
            class_id = c.get("class_id") or c.get("id")
            cohort_id = c.get("cohort_id")
            class_name = c.get("class_name")
            code = c.get("code")
            self.classes_tree.insert("", "end", values=(class_id, cohort_id, class_name, code))


    def edit_class_dialog(self):
        sel = self.classes_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Please select a class to edit.")
            return
        item = sel[0]
        vals = self.classes_tree.item(item, "values")
        class_id = vals[0]
        course_id = vals[1]
        year = vals[2]
        semester = vals[3]

        dlg = tk.Toplevel(self)
        dlg.title("Edit Class")
        dlg.geometry("340x260")
        dlg.transient(self)
        dlg.grab_set()

        form = tk.Frame(dlg, padx=12, pady=12)
        form.pack(fill="both", expand=True)

        fields = [
            ("Course ID", "course_id", course_id),
            ("Year", "year", year),
            ("Semester", "semester", semester)
        ]
        vars = {}
        for i, (label, key, initial) in enumerate(fields):
            tk.Label(form, text=label+":").grid(row=i, column=0, sticky="e", pady=6, padx=6)
            sv = tk.StringVar(value=initial)
            tk.Entry(form, textvariable=sv, width=24).grid(row=i, column=1, pady=6, padx=6)
            vars[key] = sv

        def on_save():
            class_data = {k: v.get().strip() for k, v in vars.items()}
            if not class_data["course_id"] or not class_data["year"] or not class_data["semester"]:
                messagebox.showerror("Validation", "All fields are required.")
                return
            try:
                safe_call(self.user_manager, "update_class", class_id, class_data)
                messagebox.showinfo("Saved", "Class updated.")
                dlg.destroy()
                self.load_classes()
            except AttributeError as e:
                messagebox.showerror("Missing DB Method", str(e))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update class: {e}")

        btns = tk.Frame(form)
        btns.grid(row=len(fields), column=0, columnspan=2, pady=12)
        tk.Button(btns, text="Save", command=on_save, width=12).pack(side="left", padx=6)
        tk.Button(btns, text="Cancel", command=dlg.destroy, width=12).pack(side="left", padx=6)

    # ---------------- Start Attendance ----------------

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

        department_options = [
            "Bachelor of Science in Tourism Management (BTM)",
            "Bachelor of Science in Hospitality Management (BHM)",
            "Bachelor of Business Science: Financial Engineering (BBSFENG)",
            "Bachelor of Business Science: Financial Economics (BBSFE)",
            "Bachelor of Business Science: Actuarial Science (BBSACT)",
            "Bachelor Of Science In Informatics And Computer Science (BICS)",
            "Bachelor Of Business Information Technology (BBIT)",
            "BSc. Computer Networks and Cyber Security (BCNS)",
            "Bachelor of Laws (LLB)",
            "Bachelor of Arts in Communication (BAC)",
            "Bachelor of Arts in International Studies",
            "Bachelor of Arts in Development Studies and Philosophy (BDP)",
            "Bachelor of Science in Supply Chain and Operations Management (BSCM)",
            "Bachelor of Financial Services (BFS)",
            "Bachelor Of Science In Electrical and Electronics Engineering (BSEEE)",
            "BSc in Statistics and Data Science (BScSDS)",
            "Bachelor of Commerce (BCOM)"
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
            elif key == "department":
                sv = tk.StringVar(value=initial)
                cb = ttk.Combobox(frame, textvariable=sv, width=34, state="readonly")
                cb['values'] = department_options
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
        import re
        from tkinter import messagebox
        lecturer_data = {k: self.vars[k].get().strip() for k in [
            "first_name", "last_name", "other_name", "email", "phone", "password", "department", "academic_rank", "hire_date", "office_location", "specialization"]}

        # Required fields
        required_fields = ["first_name", "last_name", "email", "phone", "password", "department", "academic_rank", "office_location", "specialization"]
        missing = [f.replace('_', ' ').title() for f in required_fields if not lecturer_data[f]]
        if missing:
            messagebox.showerror("Validation", f"Missing required fields: {', '.join(missing)}")
            return

        # Email format
        email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(email_regex, lecturer_data["email"]):
            messagebox.showerror("Validation", "Invalid email format.")
            return

        # Phone format (allow +, digits, spaces, dashes, min 7 digits)
        phone_clean = re.sub(r"[^\d]", "", lecturer_data["phone"])
        if len(phone_clean) < 7:
            messagebox.showerror("Validation", "Phone number must have at least 7 digits.")
            return

        # Password length
        if len(lecturer_data["password"]) < 6:
            messagebox.showerror("Validation", "Password must be at least 6 characters.")
            return

        # Hire date format (if provided)
        hire_date = lecturer_data["hire_date"]
        if hire_date:
            date_regex = r"^\d{4}-\d{2}-\d{2}$"
            if not re.match(date_regex, hire_date):
                messagebox.showerror("Validation", "Hire date must be in YYYY-MM-DD format.")
                return

        # Optionally: check for duplicate email (only on create)
        if not self.lecturer:
            try:
                existing = self.user_manager.get_lecturer_by_lecturer_id(lecturer_data["email"])
                if existing:
                    messagebox.showerror("Validation", "A lecturer with this email already exists.")
                    return
            except Exception:
                pass

        try:
            if self.lecturer:
                lecturer_id = self.lecturer.get("lecturer_id")
                if not lecturer_id:
                    messagebox.showerror("Error", "Lecturer ID not found. Cannot update record.")
                    return
                safe_call(self.user_manager, "update_lecturer", lecturer_id, lecturer_data)
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
        # Dialog to assign students to a class (modern flow)
        dlg = tk.Toplevel(self)
        dlg.title("Assign Students to Class")
        dlg.geometry("520x420")
        dlg.transient(self)
        dlg.grab_set()

        # Fetch classes
        try:
            classes = self.user_manager.get_classes()
        except Exception:
            classes = []
        class_choices = [(str(c.get("id")), c.get("class_name", str(c.get("id")))) for c in classes]

        tk.Label(dlg, text="Select Class:").pack(pady=(10, 2))
        class_var = tk.StringVar()
        class_combo = ttk.Combobox(dlg, textvariable=class_var, values=[f"{cid} - {name}" for cid, name in class_choices], state="readonly", width=40)
        class_combo.pack(pady=(0, 10))

        # Search bar
        search_frame = tk.Frame(dlg)
        search_frame.pack(pady=(4, 2))
        tk.Label(search_frame, text="Search Students:").pack(side="left", padx=(0, 4))
        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=search_var, width=32)
        search_entry.pack(side="left")

        # Listbox for search results
        results_lb = tk.Listbox(dlg, selectmode="extended", width=54, height=13)
        results_lb.pack(padx=12, pady=(6, 2))

        def search_students(event=None):
            query = search_var.get().strip().lower()
            results_lb.delete(0, tk.END)
            if not query:
                return
            try:
                all_students = self.user_manager.get_users()
            except Exception:
                all_students = []
            for s in all_students:
                sid = str(s.get("student_id"))
                name = f"{sid} - {s.get('first_name','')} {s.get('last_name','')} ({s.get('email','')})"
                if query in sid.lower() or query in s.get('first_name','').lower() or query in s.get('last_name','').lower() or query in s.get('email','').lower():
                    results_lb.insert(tk.END, name)

        search_entry.bind("<KeyRelease>", search_students)

        def confirm_assignment():
            selected_class = class_var.get()
            if not selected_class:
                messagebox.showerror("Validation", "Please select a class.")
                return
            class_id = selected_class.split(" - ", 1)[0]
            sel_indices = results_lb.curselection()
            if not sel_indices:
                messagebox.showerror("Validation", "Please select at least one student to assign.")
                return
            student_ids = []
            for i in sel_indices:
                val = results_lb.get(i)
                sid = val.split(" - ", 1)[0]
                student_ids.append(sid)
            try:
                self.user_manager.assign_students_to_class(class_id, student_ids)
                messagebox.showinfo("Success", f"Assigned {len(student_ids)} student(s) to class.")
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to assign students: {e}")

        confirm_btn = tk.Button(dlg, text="Confirm Assignment", command=confirm_assignment, width=20)
        confirm_btn.pack(pady=12)
