import tkinter as tk
from tkinter import ttk, messagebox
import threading
import cv2
from PIL import Image, ImageTk
import datetime
import sqlite3
import os
import getpass
import csv

# --- CONFIG ---
DB_PATH = 'attendance.db'
# --- AUDIT LOG ---
AUDIT_LOG = 'audit.log'

def log_audit(action, user):
    with open(AUDIT_LOG, 'a') as f:
        f.write(f"{datetime.datetime.now().isoformat()} | {user} | {action}\n")

# --- LECTURER LOGIN ---
def lecturer_login():
    # Simple username prompt (no password for prototype)
    return getpass.getuser()

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        student_name TEXT,
        timestamp TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        course TEXT,
        started_at TEXT,
        ended_at TEXT
    )''')
    conn.commit()
    conn.close()

# --- APP CLASS ---
class AttendanceApp:
    def __init__(self, root):
        self.lecturer = lecturer_login()
        self.root = root
        self.root.title(f'Classroom Attendance - {self.lecturer}')
        self.session_active = False
        self.session_id = None
        self.cap = None
        self.video_label = tk.Label(root)
        self.video_label.pack()
        self.course_var = tk.StringVar()
        ttk.Label(root, text='Course:').pack()
        self.course_entry = ttk.Entry(root, textvariable=self.course_var)
        self.course_entry.pack()
        self.start_btn = ttk.Button(root, text='Start Session', command=self.start_session)
        self.start_btn.pack()
        self.end_btn = ttk.Button(root, text='End Session', command=self.end_session, state='disabled')
        self.end_btn.pack()
        self.attendance_list = tk.Listbox(root, width=50)
        self.attendance_list.pack()
        self.update_video = False
        self.marked_ids = set()

    def start_session(self):
        course = self.course_var.get().strip()
        if not course:
            messagebox.showerror('Error', 'Please enter a course name.')
            return
        self.session_id = f"{course}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_active = True
        self.start_btn.config(state='disabled')
        self.end_btn.config(state='normal')
        self.attendance_list.delete(0, tk.END)
        self.cap = cv2.VideoCapture(0)
        self.update_video = True
        threading.Thread(target=self.video_loop, daemon=True).start()
        # Save session start
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT INTO sessions (session_id, course, started_at) VALUES (?, ?, ?)',
                  (self.session_id, self.course_var.get().strip(), datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        log_audit(f"Started session {self.session_id}", self.lecturer)

    def end_session(self):
        self.session_active = False
        self.update_video = False
        if self.cap:
            self.cap.release()
        self.start_btn.config(state='normal')
        self.end_btn.config(state='disabled')
        # Save session end
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE sessions SET ended_at=? WHERE session_id=?',
                  (datetime.datetime.now().isoformat(), self.session_id))
        conn.commit()
        conn.close()
        log_audit(f"Ended session {self.session_id}", self.lecturer)
        messagebox.showinfo('Session Ended', 'Attendance session ended.')

    def mark_attendance(self, user_id, user_name):
        if user_id in self.marked_ids:
            return  # Prevent duplicate
        self.marked_ids.add(user_id)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT INTO attendance (session_id, student_name, timestamp) VALUES (?, ?, ?)',
                  (self.session_id, user_name, datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        self.attendance_list.insert(tk.END, f"{user_name} ({user_id})")
        log_audit(f"Marked attendance: {user_id} {user_name} in {self.session_id}", self.lecturer)

    def video_loop(self):
        while self.update_video and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                break
            # --- PLACEHOLDER: Here you would add face recognition and attendance marking ---
            # For prototype, simulate recognition with a keypress
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(img)
            imgtk = ImageTk.PhotoImage(image=img)
            self.video_label.imgtk = imgtk
            self.video_label.config(image=imgtk)
            self.root.update_idletasks()
            self.root.after(30)
            # Simulate marking attendance for demo
            if self.session_active and self.root.focus_get() == self.video_label:
                # Press 'a' to simulate recognizing a user
                if self.root.winfo_exists() and self.root.tk.call('tk::GetKeyState', 'A'):
                    # Replace with real recognition/user lookup
                    self.mark_attendance('demo_id', 'Demo User')
        if self.cap:
            self.cap.release()

    def export_attendance(self):
        # Export attendance for current session to CSV
        if not self.session_id:
            messagebox.showerror('Error', 'No session to export.')
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT student_name, timestamp FROM attendance WHERE session_id=?', (self.session_id,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            messagebox.showinfo('No Data', 'No attendance data to export.')
            return
        export_path = f"attendance_export_{self.session_id}.csv"
        with open(export_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Student Name', 'Timestamp'])
            writer.writerows(rows)
        messagebox.showinfo('Exported', f'Attendance exported to {export_path}')
        log_audit(f"Exported attendance for {self.session_id}", self.lecturer)

if __name__ == '__main__':
    init_db()
    root = tk.Tk()
    app = AttendanceApp(root)
    # Add export button
    export_btn = ttk.Button(root, text='Export Attendance', command=app.export_attendance)
    export_btn.pack()
    root.mainloop()
