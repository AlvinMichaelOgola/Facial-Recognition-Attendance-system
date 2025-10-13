# lec_main.py
import os
import sys
import csv
import datetime
import threading
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as tb
from PIL import Image, ImageTk
import cv2

from user_data_manager import UserDataManager
import rec_faces

# ---------------- Helpers ----------------
def datetime_now():
    return datetime.datetime.now().strftime('%H:%M:%S')

# ---------------- Lecturer App ----------------
class LecturerApp(tb.Window):
    def __init__(self):
        # initialize with a theme name (do not set .style attribute directly)
        super().__init__(themename="cosmo")
        # keep a reference to the style object under a non-conflicting name
        try:
            self._style = tb.Style()
        except Exception:
            self._style = None

        self.title("Lecturer Module")
        self.geometry("1000x720")
        self.minsize(900, 600)

        # DB & session
        self.db = UserDataManager()
        self.lecturer = None
        self.session_id = None

        # Camera & preview
        self.cap = None
        self.preview_running = False
        self.preview_label = None

        # UI elements we'll assign later
        self.class_tree = None
        self.log_box = None
        self.preview_container = None
        self.logged_names = set()  # GUI-level record of who was logged in the GUI

        # Build UI
        self.show_login()

    # ---------------- Login ----------------
    def show_login(self):
        self.clear_window()
        frame = tb.Frame(self, padding=20)
        frame.pack(expand=True)

        tb.Label(frame, text="Lecturer Login", font=("Segoe UI", 18, "bold")).pack(pady=20)

        tb.Label(frame, text="Email").pack(anchor="w", pady=(10, 0))
        self.email_entry = tb.Entry(frame, width=40)
        self.email_entry.pack()

        tb.Label(frame, text="Password").pack(anchor="w", pady=(10, 0))
        self.password_entry = tb.Entry(frame, show="*", width=40)
        self.password_entry.pack()

        # Show/Hide password toggle
        self.show_pass = tk.BooleanVar()
        tb.Checkbutton(
            frame, text="Show Password", variable=self.show_pass,
            command=lambda: self.password_entry.config(show="" if self.show_pass.get() else "*")
        ).pack(anchor="w", pady=5)

        tb.Button(frame, text="Login", bootstyle="success", command=self.login).pack(pady=20)

    def login(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        if not email or not password:
            messagebox.showerror("Login Failed", "Please enter email and password.")
            return
        try:
            lecturer = self.db.authenticate_lecturer(email, password)
        except Exception as e:
            messagebox.showerror("Login Failed", f"Auth error: {e}")
            return
        if lecturer:
            self.lecturer = lecturer
            self.show_dashboard()
        else:
            messagebox.showerror("Login Failed", "Invalid credentials or not a lecturer.")

    # ---------------- Dashboard ----------------
    def show_dashboard(self):
        self.clear_window()

        top_frame = tb.Frame(self, padding=10)
        top_frame.pack(fill="x")

        tb.Label(
            top_frame,
            text=f"Welcome, {self.lecturer['first_name']} {self.lecturer['last_name']}",
            font=("Segoe UI", 16, "bold")
        ).pack(side="left", padx=10)

        # Controls on top-right
        ctrl_frame = tb.Frame(top_frame)
        ctrl_frame.pack(side="right", padx=10)
        tb.Button(ctrl_frame, text="Toggle Theme", bootstyle="secondary", command=self.toggle_theme).pack(side="left", padx=5)
        tb.Button(ctrl_frame, text="Logout", bootstyle="danger", command=self.logout).pack(side="left", padx=5)

        main_frame = tb.Frame(self, padding=15)
        main_frame.pack(fill="both", expand=True)

        # Classes list / Treeview
        tb.Label(main_frame, text="Assigned Classes", font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0,6))
        lecturer_id = self.lecturer.get('id') or self.lecturer.get('lecturer_id')
        try:
            classes = self.db.get_lecturer_classes(lecturer_id) or []
        except Exception:
            classes = []

        tree_frame = tb.Frame(main_frame)
        tree_frame.pack(fill="x")

        self.class_tree = ttk.Treeview(tree_frame, columns=("ID", "Name", "Code"), show="headings", height=8)
        self.class_tree.heading("ID", text="Class ID")
        self.class_tree.heading("Name", text="Class Name")
        self.class_tree.heading("Code", text="Code")
        self.class_tree.column("ID", width=100, anchor="center")
        self.class_tree.column("Name", width=450, anchor="w")
        self.class_tree.column("Code", width=150, anchor="center")
        self.class_tree.pack(side="left", fill="x", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.class_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.class_tree.configure(yscrollcommand=scrollbar.set)

        for c in classes:
            try:
                self.class_tree.insert("", "end", values=(c["id"], c["class_name"], c.get("code", "")))
            except Exception:
                continue

        # Buttons below classes
        btn_frame = tb.Frame(main_frame, padding=(0,10))
        btn_frame.pack(fill="x")

        tb.Button(btn_frame, text="Start Attendance Session", bootstyle="success", command=self.start_session).pack(side="left", padx=5)
        tb.Button(btn_frame, text="Export Attendance Records", bootstyle="info", command=self.export_attendance).pack(side="left", padx=5)

        # Placeholder for preview area when not running
        self.preview_container = tb.Frame(self, padding=10)
        self.preview_container.pack(fill="both", expand=True, pady=(10,0))

        info = tb.Label(self.preview_container, text="Start a session to open live preview and recognition log.", font=("Segoe UI", 11))
        info.pack(pady=20)

    # ---------------- Start Attendance ----------------
    def start_session(self):
        selected = self.class_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a class.")
            return

        class_id = self.class_tree.item(selected[0])["values"][0]
        session_name = f"Session for Class {class_id}"
        try:
            self.session_id = self.db.create_attendance_session(class_id, self.lecturer['lecturer_id'], name=session_name)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create session: {e}")
            return

        if not self.session_id:
            messagebox.showerror("Error", "Failed to start session (DB returned no id).")
            return

        # Get only eligible students (assigned to class and active)
        try:
            embeddings = self.db.get_face_embeddings_for_class(class_id)
            student_ids = [row['student_id'] for row in embeddings]
            if not student_ids:
                messagebox.showwarning("No Students", "No eligible students (assigned and active) are in this class. Attendance cannot be started.")
                return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch eligible students for class: {e}")
            return

        # Start rec_faces session with filtered student IDs
        try:
            rec_faces.start_session(session_id=self.session_id, student_ids=student_ids)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start recognition: {e}")

        # Replace preview_container with live session UI
        for widget in self.preview_container.winfo_children():
            widget.destroy()

        tb.Label(self.preview_container, text=f"Attendance Session Active - Session ID: {self.session_id}", font=("Segoe UI", 14, "bold")).pack(pady=(0,8))

        session_pane = tb.Frame(self.preview_container)
        session_pane.pack(fill="both", expand=True)

        # Left - preview
        preview_left = tb.Frame(session_pane)
        preview_left.pack(side="left", fill="both", expand=True, padx=(0,8))

        self.preview_label = tk.Label(preview_left)
        self.preview_label.pack(fill="both", expand=True)

        preview_ctrl = tb.Frame(preview_left)
        preview_ctrl.pack(fill="x", pady=6)
        tb.Button(preview_ctrl, text="End Attendance Session", bootstyle="danger", command=self.end_session).pack(side="left", padx=5)
        tb.Button(preview_ctrl, text="Reset Session (allow re-capture)", bootstyle="secondary", command=self.reset_session).pack(side="left", padx=5)

        # Right - log area
        log_right = tb.Frame(session_pane, width=320)
        log_right.pack(side="right", fill="y")

        tb.Label(log_right, text="Recognition Log", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0,6))
        self.log_box = tk.Listbox(log_right, height=20)
        self.log_box.pack(fill="both", expand=True)

        # Start camera
        self.logged_names = set()
        try:
            if os.name == 'nt':
                self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            else:
                self.cap = cv2.VideoCapture(0)
        except Exception:
            self.cap = None

        if not self.cap or not self.cap.isOpened():
            messagebox.showerror("Camera Error", "Could not open webcam.")
            self.cap = None
            self.preview_running = False
            return

        self.preview_running = True
        # Launch preview loop
        self.after(30, self.update_preview_loop)

    # ---------------- Preview Loop ----------------
    def update_preview_loop(self):
        if not self.preview_running:
            return

        ret = False
        frame = None
        try:
            if not self.cap:
                self.after(200, self.update_preview_loop)
                return
            ret, frame = self.cap.read()
        except Exception:
            ret = False

        if not ret or frame is None:
            self.after(100, self.update_preview_loop)
            return

        # Process frame through rec_faces module
        try:
            processed_frame, names = rec_faces.process_frame(frame)
        except Exception as e:
            processed_frame = frame
            names = []
            logging.error(f"Error while processing frame: {e}")

        # Add recognized names to GUI log (only once per session)
        for name in names:
            if name not in self.logged_names and name != "Unknown":
                self.logged_names.add(name)
                try:
                    self.log_box.insert(tk.END, f"[{datetime_now()}] Recognized: {name}")
                    self.log_box.see(tk.END)
                except Exception:
                    pass

        # Convert processed_frame to Tkinter image
        try:
            cv2image = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(cv2image)
            imgtk = ImageTk.PhotoImage(image=pil_img)
            self.preview_label.imgtk = imgtk
            self.preview_label.configure(image=imgtk)
        except Exception:
            # If conversion fails, skip this frame
            pass

        # schedule next frame
        self.after(30, self.update_preview_loop)

    # ---------------- End Session ----------------
    def end_session(self):
        if not messagebox.askyesno("Confirm", "Are you sure you want to end this session?"):
            return

        # Stop preview
        self.preview_running = False
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        # End rec_faces session and flush buffer
        try:
            rec_faces.end_session()
        except Exception:
            pass

        # Clear UI back to placeholder
        for widget in self.preview_container.winfo_children():
            widget.destroy()
        tb.Label(self.preview_container, text="Session ended. You may start another session.", font=("Segoe UI", 11)).pack(pady=20)

        messagebox.showinfo("Session Ended", "Attendance session ended and attendance flushed.")

    # ---------------- Reset Session ----------------
    def reset_session(self):
        self.logged_names.clear()
        try:
            if self.log_box:
                self.log_box.delete(0, tk.END)
        except Exception:
            pass
        try:
            rec_faces.marked_names.clear()
        except Exception:
            pass

    # ---------------- Export Attendance ----------------
    def export_attendance(self):
        # Only allow export if a session is active and a per-session CSV exists
        if not self.session_id:
            messagebox.showinfo("Export Attendance", "No session active. Please start and end a session to export attendance records.")
            return

        # Try to find the per-session CSV file generated by rec_faces.flush_attendance
        db = self.db

        try:
            session_info = db.get_session_by_id(self.session_id)
            class_info = db.get_class_by_id(session_info['class_id']) if session_info else None
            lecturer_name = "lecturer"
            if session_info and session_info.get('lecturer_id'):
                try:
                    lec = db.get_lecturer_by_id(session_info['lecturer_id'])
                    if lec:
                        first = lec.get('first_name') or ''
                        last = lec.get('last_name') or ''
                        lecturer_name = f"{first}_{last}".strip('_')
                except Exception:
                    pass
            class_name = class_info['class_name'] if class_info and class_info.get('class_name') else 'unknown_class'
            date_str = session_info['started_at'].strftime('%Y-%m-%d') if session_info and session_info.get('started_at') else datetime.datetime.now().strftime('%Y-%m-%d')
            def sanitize(s):
                return ''.join(c for c in str(s) if c.isalnum() or c in ('-_')).rstrip()
            class_name_safe = sanitize(class_name).replace(' ', '_')
            lecturer_name_safe = sanitize(lecturer_name).replace(' ', '_')
            session_csv = os.path.join('data', f'attendance_{date_str}_{lecturer_name_safe}_{class_name_safe}_{self.session_id}.csv')
        except Exception:
            session_csv = None

        if session_csv and os.path.exists(session_csv):
            file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files","*.csv")])
            if not file_path:
                return
            try:
                with open(session_csv, 'r', encoding='utf-8') as src, open(file_path, 'w', encoding='utf-8', newline='') as dst:
                    dst.write(src.read())
                messagebox.showinfo("Export", f"Attendance exported to {file_path}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Export failed: {e}")
            return
        else:
            messagebox.showinfo("Export", "No attendance file found for this session. Please end the session to generate the file.")

    # ---------------- Utils ----------------
    def clear_window(self):
        for widget in self.winfo_children():
            widget.destroy()

    def logout(self):
        if not messagebox.askyesno("Confirm", "Are you sure you want to logout?"):
            return
        # Ensure cleanup
        try:
            self.preview_running = False
            if self.cap:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
        except Exception as e:
            try:
                import logging as _log
                _log.error(f"Error during logout cleanup: {e}")
            except Exception:
                pass
        finally:
            self.cap = None

        self.session_id = None
        self.logged_names.clear()
        try:
            rec_faces.end_session()
        except Exception:
            pass

        self.show_login()

    def toggle_theme(self):
        current = self.get_themename()
        new = "flatly" if current == "cosmo" else "cosmo"
        try:
            if self._style:
                self._style.theme_use(new)
            else:
                self.set_themename(new)
        except Exception:
            try:
                self.set_themename(new)
            except Exception:
                pass

# ---------------- Entry point ----------------
if __name__ == "__main__":
    # Start recognizer internal thread already started by rec_faces at import
    # Launch GUI
    app = LecturerApp()
    try:
        app.mainloop()
    finally:
        # ensure cleanup on exit
        try:
            rec_faces.cleanup()
        except Exception:
            pass
