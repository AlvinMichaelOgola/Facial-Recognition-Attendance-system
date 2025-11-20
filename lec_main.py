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
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# Import your custom modules
try:
    from user_data_manager import UserDataManager
    import rec_faces
except ImportError as e:
    messagebox.showerror("Critical Error", f"Missing required modules: {e}")
    sys.exit(1)

# ---------------- Helpers ----------------
def datetime_now():
    return datetime.datetime.now().strftime('%H:%M:%S')

# ---------------- Lecturer App ----------------
class LecturerApp(tb.Window):
    def __init__(self):
        # Initialize with a modern theme
        super().__init__(themename="cosmo")
        
        # Style handling
        try:
            self._style = tb.Style()
        except Exception:
            self._style = None

        self.title("Lecturer Module - RollCall FRS")
        self.geometry("1150x800")
        self.minsize(1000, 720)

        # DB & session
        self.db = UserDataManager()
        self.lecturer = None
        self.session_id = None
        self.current_class_total_students = 0 

        # Camera & preview
        self.cap = None
        self.preview_running = False
        self.preview_label = None

        # UI State
        self.logged_names = set() 
        self.class_options = []
        self.selected_class = tk.StringVar()
        
        # Widget References (Initialize to None for safety)
        self.export_btn = None
        self.attendance_meter = None
        self.session_btn = None
        self.class_dropdown = None

        # Build UI
        self.show_login()

    # ---------------- Login with "Remember Me" ----------------
    def show_login(self):
        self.clear_window()
        
        # Main centered container
        container = tb.Frame(self)
        container.pack(expand=True, fill="both")
        
        # Login Card
        card = tb.Frame(container, padding=40, bootstyle="light")
        card.place(relx=0.5, rely=0.5, anchor="center")

        tb.Label(card, text="Lecturer Login", font=("Segoe UI", 22, "bold"), bootstyle="primary").pack(pady=(0, 25))

        # Email
        tb.Label(card, text="Email Address", font=("Segoe UI", 11)).pack(anchor="w", pady=(5, 0))
        self.email_entry = tb.Entry(card, width=40)
        self.email_entry.pack(pady=(0, 15))

        # Password
        tb.Label(card, text="Password", font=("Segoe UI", 11)).pack(anchor="w", pady=(5, 0))
        self.password_entry = tb.Entry(card, show="*", width=40)
        self.password_entry.pack(pady=(0, 10))

        # Checkboxes Frame
        check_frame = tb.Frame(card)
        check_frame.pack(fill="x", pady=(0, 20))

        # Show Password
        self.show_pass = tk.BooleanVar()
        tb.Checkbutton(
            check_frame, text="Show Password", variable=self.show_pass, bootstyle="round-toggle",
            command=lambda: self.password_entry.config(show="" if self.show_pass.get() else "*")
        ).pack(side="left")

        # Remember Email
        self.remember_me = tk.BooleanVar()
        tb.Checkbutton(
            check_frame, text="Remember Email", variable=self.remember_me, bootstyle="square-toggle"
        ).pack(side="right")

        # Load saved email if exists
        if os.path.exists("last_login.txt"):
            try:
                with open("last_login.txt", "r") as f:
                    saved_email = f.read().strip()
                    if saved_email:
                        self.email_entry.insert(0, saved_email)
                        self.remember_me.set(True)
            except Exception:
                pass

        # Login Button
        tb.Button(card, text="Login", bootstyle="success", width=20, command=self.login).pack()

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
            # Handle Remember Me Logic
            if self.remember_me.get():
                try:
                    with open("last_login.txt", "w") as f:
                        f.write(email)
                except Exception:
                    pass
            else:
                if os.path.exists("last_login.txt"):
                    try:
                        os.remove("last_login.txt")
                    except Exception:
                        pass

            self.lecturer = lecturer
            self.show_dashboard()
        else:
            messagebox.showerror("Login Failed", "Invalid credentials or not a lecturer.")

    # ---------------- Dashboard ----------------
    def show_dashboard(self):
        self.clear_window()

        # 1. Top Header Bar
        header = tb.Frame(self, padding=15, bootstyle="primary")
        header.pack(fill="x")
        
        tb.Label(header, text="RollCall FRS", font=("Segoe UI", 18, "bold"), bootstyle="inverse-primary").pack(side="left")
        
        ctrl_frame = tb.Frame(header, bootstyle="primary")
        ctrl_frame.pack(side="right")
        
        user_name = f"{self.lecturer.get('first_name', '')} {self.lecturer.get('last_name', '')}"
        tb.Label(ctrl_frame, text=user_name, font=("Segoe UI", 12), bootstyle="inverse-primary").pack(side="left", padx=15)
        tb.Button(ctrl_frame, text="Theme", bootstyle="light-outline", command=self.toggle_theme).pack(side="left", padx=5)
        tb.Button(ctrl_frame, text="Logout", bootstyle="danger", command=self.logout).pack(side="left", padx=5)

        # 2. Main Content Grid
        main_frame = tb.Frame(self, padding=20)
        main_frame.pack(expand=True, fill="both")
        
        main_frame.columnconfigure(0, weight=4, uniform="group1") # Left Panel (40%)
        main_frame.columnconfigure(1, weight=6, uniform="group1") # Right Panel (60%)
        main_frame.rowconfigure(0, weight=1)

        # === LEFT COLUMN: Controls & Logs ===
        left_panel = tb.Labelframe(main_frame, text=" Session Management ", padding=15, bootstyle="default")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        # Class Selection
        tb.Label(left_panel, text="Select Class:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(5, 0))
        
        # Robust ID fetch
        lecturer_id = self.lecturer.get('id') or self.lecturer.get('lecturer_id')
        
        try:
            classes = self.db.get_lecturer_classes(lecturer_id) or []
        except Exception:
            classes = []
        self.class_options = [(c["id"], c["class_name"]) for c in classes]
        class_names = [name for (_id, name) in self.class_options]
        
        self.class_dropdown = tb.Combobox(left_panel, textvariable=self.selected_class, values=class_names, state="readonly")
        self.class_dropdown.pack(fill="x", pady=(5, 15))
        if class_names: self.selected_class.set(class_names[0])

        # Session Status & Start Button
        self.session_state_label = tb.Label(left_panel, text="Ready to Start", font=("Segoe UI", 10), bootstyle="secondary")
        self.session_state_label.pack(pady=(0, 5))
        
        self.session_btn = tb.Button(left_panel, text="Start Attendance Session", bootstyle="success", width=100, command=self.start_session)
        self.session_btn.pack(pady=(0, 20))

        # Attendance Meter (Fixed: Removed text_right)
        self.attendance_meter = tb.Meter(
            left_panel,
            bootstyle="info",
            subtext="Attendance Rate",
            interactive=False,
            metertype="semi",
            amountused=0,
            metersize=160,
            stripethickness=10
        )
        self.attendance_meter.pack(pady=(0, 20))

        # Log Area
        tb.Label(left_panel, text="Activity Log", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.log_box = ScrolledText(left_panel, height=10, font=("Consolas", 9))
        self.log_box.pack(fill="both", expand=True, pady=(5, 10))

        # Email Progress (Hidden Initially)
        self.email_progress_frame = tb.Frame(left_panel)
        self.email_status_lbl = tb.Label(self.email_progress_frame, text="Sending emails...", font=("Segoe UI", 9))
        self.email_status_lbl.pack(anchor="w")
        self.email_bar = tb.Progressbar(self.email_progress_frame, mode='determinate', bootstyle="success")
        self.email_bar.pack(fill="x", pady=5)

        # Export Button (Safe Initialization)
        self.export_btn = tb.Button(left_panel, text="Export Attendance PDF", bootstyle="warning-outline", command=self.export_attendance)
        # We DO NOT pack it yet. It stays hidden.
        
        # === RIGHT COLUMN: Camera & Preview ===
        right_panel = tb.Frame(main_frame, padding=5)
        right_panel.grid(row=0, column=1, sticky="nsew")
        
        # Camera Frame
        self.preview_container = tb.Frame(right_panel, bootstyle="dark")
        self.preview_container.pack(fill="both", expand=True)
        
        self.preview_label = tk.Label(self.preview_container, bg="#2b2b2b", text="Camera Inactive", fg="white")
        self.preview_label.pack(fill="both", expand=True)

        self.face_count_label = tb.Label(right_panel, text="Faces Detected: 0", font=("Segoe UI", 12, "bold"), bootstyle="info")
        self.face_count_label.pack(pady=15)

    # ---------------- Start Session ----------------
    def start_session(self):
        class_name = self.selected_class.get()
        class_id = None
        for _id, name in self.class_options:
            if name == class_name:
                class_id = _id
                break
        if not class_id:
            messagebox.showerror("Error", "Please select a class.")
            return

        # Robust ID usage for session creation
        lec_id = self.lecturer.get('id') or self.lecturer.get('lecturer_id')
        session_name = f"Session for Class {class_id}"
        
        try:
            self.session_id = self.db.create_attendance_session(class_id, lec_id, name=session_name)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create session: {e}")
            return

        if not self.session_id:
            messagebox.showerror("Error", "Failed to start session (DB returned no id).")
            return

        # Get eligible students
        try:
            embeddings = self.db.get_face_embeddings_for_class(class_id)
            student_ids = [row['student_id'] for row in embeddings]
            self.current_class_total_students = len(student_ids) 
            
            if not student_ids:
                messagebox.showwarning("No Students", "No eligible students in this class.")
                return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch eligible students: {e}")
            return

        # Start rec_faces session
        try:
            rec_faces.start_session(session_id=self.session_id, student_ids=student_ids)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start recognition: {e}")
            return

        # Update UI
        self.session_state_label.config(text=f"Session Running (ID: {self.session_id})", bootstyle="success")
        self.session_btn.config(text="End Session", bootstyle="danger", command=self.end_session)
        self.class_dropdown.config(state="disabled")
        
        # Safely hide export button if it was showing
        if self.export_btn:
            self.export_btn.pack_forget()
            
        self.attendance_meter.configure(amountused=0)

        # Setup Log
        self.log_box.config(state="normal")
        self.log_box.delete('1.0', tk.END)
        self.logged_names = set()
        self.log_box.config(state="disabled")

        # Start Camera
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

        # Process frame
        try:
            processed_frame, names = rec_faces.process_frame(frame)
        except Exception as e:
            processed_frame = frame
            names = []
            logging.error(f"Error while processing frame: {e}")

        # Log recognized names
        for name in names:
            if name not in self.logged_names and name != "Unknown":
                self.logged_names.add(name)
                # GUI Log
                self.log_box.config(state="normal")
                self.log_box.insert(tk.END, f"[{datetime_now()}] Recognized: {name}\n")
                self.log_box.see(tk.END)
                self.log_box.config(state="disabled")

        # Update Stats (Meter & Label)
        count = len(self.logged_names)
        self.face_count_label.config(text=f"Faces detected: {count}")
        
        if self.current_class_total_students > 0:
            perc = int((count / self.current_class_total_students) * 100)
            self.attendance_meter.configure(amountused=perc)

        # Display Image
        try:
            # Simple resize logic to fit frame height
            l_height = self.preview_label.winfo_height()
            if l_height > 100:
                h, w, _ = processed_frame.shape
                scale = l_height / h
                new_w = int(w * scale)
                processed_frame = cv2.resize(processed_frame, (new_w, l_height))
            
            cv2image = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(cv2image)
            imgtk = ImageTk.PhotoImage(image=pil_img)
            self.preview_label.imgtk = imgtk
            self.preview_label.configure(image=imgtk, text="")
        except Exception:
            pass

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
        
        self.preview_label.configure(image='', text="Camera Inactive")

        # End rec_faces
        try:
            rec_faces.end_session()
        except Exception:
            pass

        # Mark absent
        try:
            present_student_ids = []
            if hasattr(rec_faces, 'marked_student_ids'):
                present_student_ids = list(rec_faces.marked_student_ids)
            elif hasattr(rec_faces, 'marked_names'):
                present_student_ids = list(rec_faces.marked_names)
            else:
                present_student_ids = list(self.logged_names)
            self.db.mark_absent_students_for_session(self.session_id, present_student_ids)
        except Exception as e:
            logging.error(f"Failed to mark absent students: {e}")

        # UI Updates
        self.session_state_label.config(text="Session Ended", bootstyle="secondary")
        self.session_btn.config(text="Start Attendance Session", bootstyle="success", command=self.start_session)
        self.class_dropdown.config(state="readonly")
        
        # Show export button safely
        if self.export_btn:
            self.export_btn.pack(pady=(10, 0), fill="x")

        # Threaded Email Sending
        self.email_progress_frame.pack(pady=10, fill="x")
        self.email_bar.configure(value=0)
        
        def send_emails_bg():
            errors = []
            
            # Safe GUI update helper
            def progress_callback(cur, tot):
                self.after(0, lambda: self.email_bar.configure(maximum=tot, value=cur))
                self.after(0, lambda: self.email_status_lbl.config(text=f"Sending emails... {cur}/{tot}"))

            try:
                self.db.send_present_attendance_emails(self.session_id, progress_callback=progress_callback)
            except Exception as e:
                errors.append(f"Failed to send present emails: {e}")
                logging.error(errors[-1])
            try:
                self.db.send_absent_attendance_emails(self.session_id, progress_callback=progress_callback)
            except Exception as e:
                errors.append(f"Failed to send absent emails: {e}")
                logging.error(errors[-1])
            
            # Final GUI update on main thread
            def update_done():
                self.email_progress_frame.pack_forget()
                msg = "Attendance session ended and emails sent."
                if errors:
                    msg += f"\nErrors: {errors}"
                messagebox.showinfo("Session Ended", msg)
                
            self.after(0, update_done)

        threading.Thread(target=send_emails_bg, daemon=True).start()

    # ---------------- Export Attendance ----------------
    def export_attendance(self):
        # Only allow export if a session is active (or was just active)
        if not self.session_id:
            messagebox.showinfo("Export Attendance", "No session ID found.")
            return

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
                        full_name = f"{first} {last}".strip()
                        if full_name:
                            lecturer_name = full_name
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
            file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files","*.pdf")])
            if not file_path:
                return
            try:
                # Read CSV data
                with open(session_csv, 'r', encoding='utf-8') as src:
                    reader = csv.reader(src)
                    rows = list(reader)
                
                if rows:
                    header = rows[0]
                    data_rows = rows[1:]
                else:
                    header = []
                    data_rows = []

                # Calculate summary statistics
                total_students = len(data_rows)
                # present_at is column 6 (index 5)
                present_rows = [r for r in data_rows if len(r) > 5 and r[5].strip() != '']
                absent_rows = [r for r in data_rows if len(r) > 5 and r[5].strip() == '']
                total_present = len(present_rows)
                total_absent = len(absent_rows)
                attendance_rate = (total_present / total_students * 100) if total_students else 0
                session_time = session_info['started_at'].strftime('%Y-%m-%d %H:%M') if session_info and session_info.get('started_at') else date_str
                absent_list = ', '.join([f"{r[1]} {r[2]}" for r in absent_rows]) if absent_rows else 'None'
                
                # Average confidence
                try:
                    confidences = []
                    for r in present_rows:
                        if len(r) > 5:
                            val = r[5].strip() if len(r) > 5 else ''
                            if val:
                                try:
                                    confidences.append(float(val))
                                except Exception:
                                    pass
                    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                except Exception:
                    avg_confidence = 0

                # Generate PDF
                doc = SimpleDocTemplate(file_path, pagesize=letter)
                elements = []
                styles = getSampleStyleSheet()
                
                title = f"Attendance Report: {class_name} ({date_str})"
                elements.append(Paragraph(title, styles['Title']))
                elements.append(Paragraph(f"Lecturer: {lecturer_name}", styles['Normal']))
                elements.append(Paragraph(f"Session Date & Time: {session_time}", styles['Normal']))
                elements.append(Spacer(1, 12))
                
                summary = f"""
<b>Summary Statistics</b><br/>
Total Students Assigned: {total_students}<br/>
Total Present: {total_present}<br/>
Total Absent: {total_absent}<br/>
Attendance Rate: {attendance_rate:.2f}%<br/>
Average Confidence Score: {avg_confidence:.2f}<br/>
List of Absent Students: {absent_list}
"""
                elements.append(Paragraph(summary, styles['Normal']))
                elements.append(Spacer(1, 12))
                
                if rows:
                    table = Table(rows)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ]))
                    elements.append(table)
                else:
                    elements.append(Paragraph("No attendance data found.", styles['Normal']))
                
                doc.build(elements)
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
        except Exception:
            pass

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
            pass

# ---------------- Entry point ----------------
if __name__ == "__main__":
    app = LecturerApp()
    try:
        app.mainloop()
    finally:
        try:
            rec_faces.cleanup()
        except Exception:
            pass