import tkinter as tk
from tkinter import messagebox, ttk
import datetime
import subprocess
import os
from user_data_manager import UserDataManager


class LecturerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Lecturer Module")
        self.geometry("900x600")

        self.db = UserDataManager()
        self.lecturer = None
        self.session_id = None

        # self.show_login()
        # Bypass login for demo/testing: auto-login as first lecturer
        lecturers = self.db.get_lecturers()
        if lecturers:
            self.lecturer = lecturers[0]
            self.show_dashboard()
        else:
            self.show_login()

    # ---------------- Login ---------------- #
    def show_login(self):
        self.clear_window()

        tk.Label(self, text="Lecturer Login", font=("Arial", 16, "bold")).pack(pady=20)

        tk.Label(self, text="Email").pack()
        self.email_entry = tk.Entry(self, width=30)
        self.email_entry.pack()

        tk.Label(self, text="Password").pack()
        self.password_entry = tk.Entry(self, show="*", width=30)
        self.password_entry.pack()

        tk.Button(self, text="Login", command=self.login, bg="green", fg="white").pack(pady=10)

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

        tk.Label(self, text=f"Welcome, {self.lecturer['first_name']} {self.lecturer['last_name']}", font=("Arial", 14, "bold")).pack(pady=20)

        tk.Label(self, text="Assigned Classes", font=("Arial", 12)).pack(pady=5)

        # Use the correct key for lecturer ID (id or lecturer_id)
        lecturer_id = self.lecturer.get('id') or self.lecturer.get('lecturer_id')
        self.classes = self.db.get_lecturer_classes(lecturer_id)

        self.class_tree = ttk.Treeview(self, columns=("ID", "Name", "Code"), show="headings", height=10)
        self.class_tree.heading("ID", text="Class ID")
        self.class_tree.heading("Name", text="Class Name")
        self.class_tree.heading("Code", text="Code")
        self.class_tree.pack(pady=10, fill="x")

        for c in self.classes:
            self.class_tree.insert("", "end", values=(c["id"], c["class_name"], c["code"]))

        tk.Button(self, text="Start Attendance Session", command=self.start_session, bg="blue", fg="white").pack(pady=5)
        tk.Button(self, text="End Attendance Session", command=self.end_session, bg="red", fg="white").pack(pady=5)

        tk.Button(self, text="View Attendance Records", command=self.view_attendance, bg="gray", fg="white").pack(pady=5)
        tk.Button(self, text="Logout", command=self.show_login).pack(pady=20)

    # ---------------- Session Handling ---------------- #
    def start_session(self):
        selected = self.class_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a class.")
            return

        class_id = self.class_tree.item(selected[0])["values"][0]
        self.session_id = self.db.create_attendance_session(class_id, self.lecturer['id'])

        if self.session_id:
            messagebox.showinfo("Session Started", f"Attendance session started for Class ID {class_id}")
            # Run recognition script in "lecturer mode"
            subprocess.Popen(["python", "rec_faces.py", "--session_id", str(self.session_id), "--class_id", str(class_id)])
        else:
            messagebox.showerror("Error", "Failed to start session.")

    def end_session(self):
        if not self.session_id:
            messagebox.showerror("Error", "No active session.")
            return

        self.db.end_attendance_session(self.session_id)
        messagebox.showinfo("Session Ended", "Attendance session ended.")
        self.session_id = None

    # ---------------- Attendance Records ---------------- #
    def view_attendance(self):
        if not self.session_id:
            messagebox.showerror("Error", "No active session.")
            return

        records = self.db.get_attendance_for_session(self.session_id)
        if not records:
            messagebox.showinfo("No Records", "No attendance records found.")
            return

        top = tk.Toplevel(self)
        top.title("Attendance Records")
        top.geometry("600x400")

        tree = ttk.Treeview(top, columns=("Student ID", "Time", "Confidence"), show="headings", height=15)
        tree.heading("Student ID", text="Student ID")
        tree.heading("Time", text="Marked At")
        tree.heading("Confidence", text="Confidence")
        tree.pack(fill="both", expand=True)

        for r in records:
            tree.insert("", "end", values=(r["student_id"], r["present_at"], f"{r['confidence']:.2f}"))

    # ---------------- Utils ---------------- #
    def clear_window(self):
        for widget in self.winfo_children():
            widget.destroy()


if __name__ == "__main__":
    app = LecturerApp()
    app.mainloop()
