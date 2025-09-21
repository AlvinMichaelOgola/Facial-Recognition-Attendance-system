import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
import subprocess
import os
from user_data_manager import UserDataManager

class LecturerApp(tb.Window):
    def __init__(self):
        super().__init__(themename="darkly")
        self.title("Lecturer Module")
        self.geometry("900x600")

        # DB & session
        self.db = UserDataManager()
        self.lecturer = None
        self.session_id = None
        self.recog_process = None

        self.show_login()

    # ---------------- Login ---------------- #
    def show_login(self):
        self.clear_window()
        frame = tb.Frame(self, padding=20)
        frame.pack(expand=True)

        tb.Label(frame, text="Lecturer Login", font=("Segoe UI", 18, "bold")).pack(pady=20)

        tb.Label(frame, text="Email").pack(anchor="w", pady=(10, 0))
        self.email_entry = tb.Entry(frame, width=30)
        self.email_entry.pack()

        tb.Label(frame, text="Password").pack(anchor="w", pady=(10, 0))
        self.password_entry = tb.Entry(frame, show="*", width=30)
        self.password_entry.pack()

        tb.Button(frame, text="Login", bootstyle="success", command=self.login).pack(pady=20)

    def login(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        lecturer = self.db.authenticate_lecturer(email, password)
        if lecturer:
            self.lecturer = lecturer
            self.show_dashboard()
        else:
            messagebox.showerror("Login Failed", "Invalid credentials or not a lecturer.")

    # ---------------- Dashboard ---------------- #
    def show_dashboard(self):
        self.clear_window()
        frame = tb.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        tb.Label(frame, text=f"Welcome, {self.lecturer['first_name']} {self.lecturer['last_name']}",
                 font=("Segoe UI", 16, "bold")).pack(pady=10)
        tb.Label(frame, text="Assigned Classes", font=("Segoe UI", 13, "bold")).pack(pady=5)

        lecturer_id = self.lecturer.get('id') or self.lecturer.get('lecturer_id')
        self.classes = self.db.get_lecturer_classes(lecturer_id)

        self.class_tree = ttk.Treeview(frame, columns=("ID", "Name", "Code"), show="headings", height=8)
        self.class_tree.heading("ID", text="Class ID")
        self.class_tree.heading("Name", text="Class Name")
        self.class_tree.heading("Code", text="Code")
        self.class_tree.pack(fill="x", pady=10)

        for c in self.classes:
            self.class_tree.insert("", "end", values=(c["id"], c["class_name"], c["code"]))

        tb.Button(frame, text="Start Attendance Session", bootstyle="success", command=self.start_session).pack(pady=10)

        tb.Button(frame, text="Logout", bootstyle="secondary", command=self.show_login).pack(pady=10)

    # ---------------- Attendance Session ---------------- #
    def start_session(self):
        selected = self.class_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a class.")
            return

        class_id = self.class_tree.item(selected[0])["values"][0]
        self.session_id = self.db.create_attendance_session(class_id, self.lecturer['lecturer_id'])
        if not self.session_id:
            messagebox.showerror("Error", "Failed to start session.")
            return

        # Launch rec_faces.py in a subprocess
        python_exe = os.sys.executable
        rec_faces_path = os.path.join(os.getcwd(), "rec_faces.py")
        self.recog_process = subprocess.Popen([python_exe, rec_faces_path, str(self.session_id)])

        self.show_live_session()

    def show_live_session(self):
        self.clear_window()
        frame = tb.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        tb.Label(frame, text=f"Attendance Session Active - Session ID: {self.session_id}",
                 font=("Segoe UI", 16, "bold"), bootstyle="info").pack(pady=10)

        tb.Button(frame, text="End Attendance Session", bootstyle="danger", command=self.end_session).pack(pady=20)
        tb.Button(frame, text="Export Attendance Records", bootstyle="info", command=self.export_attendance).pack(pady=10)

    def end_session(self):
        if self.recog_process:
            self.recog_process.terminate()
            self.recog_process = None
        self.session_id = None
        messagebox.showinfo("Session Ended", "Attendance session ended.")
        self.show_dashboard()

    def export_attendance(self):
        # You can implement reading from your attendance CSV or DB
        messagebox.showinfo("Export", "Attendance exported successfully.")

    # ---------------- Utils ---------------- #
    def clear_window(self):
        for widget in self.winfo_children():
            widget.destroy()


if __name__ == "__main__":
    app = LecturerApp()
    app.mainloop()
