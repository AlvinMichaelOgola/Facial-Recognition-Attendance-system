
import os
import pickle
import hashlib
from typing import Optional, List, Dict, Any, Iterable

import pymysql
import pymysql.cursors
from email_utils import send_email


# ----------------------
# Database connection
# ----------------------
class DatabaseManager:
    def get_attendance_records_for_student(self, student_id: str) -> list:
        """
        Return all attendance records for a student as a list of dicts.
        Each dict contains: date, class, session, status, confidence, lecturer, etc.
        """
        q = (
            """
            SELECT ar.session_id, ar.present_at, ar.confidence, c.class_name, ats.name AS session_name, ats.started_at, ats.ended_at, l.first_name AS lecturer_first_name, l.last_name AS lecturer_last_name
            FROM attendance_records_two ar
            LEFT JOIN attendance_sessions_two ats ON ar.session_id = ats.id
            LEFT JOIN classes_two c ON ats.class_id = c.id
            LEFT JOIN lecturers_table_two l ON ats.lecturer_id = l.lecturer_id
            WHERE ar.student_id = %s
            ORDER BY ar.present_at DESC
            """
        )
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (student_id,))
                    return cur.fetchall()
        except Exception as e:
            print(f"[ERROR] Failed to fetch attendance records for student {student_id}: {e}")
            return []
    def __init__(
        self,
        host: str = "localhost",
        user: str = "root",
        password: str = "",
        db: str = "frs_v3.1",
        port: int = 3306,
    ):
        self.host = host
        self.user = user
        self.password = password
        self.db = db
        self.port = port

    def get_connection(self):
        """
        Returns a pymysql connection using DictCursor.
        Use with `with dbm.get_connection() as conn:` so connections are closed automatically.
        """
        return pymysql.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            db=self.db,
            port=self.port,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
            charset="utf8mb4",
        )


# ----------------------
# Password helpers (MVP)
# ----------------------
# Simple salted SHA-256 hashing for MVP. Replace with bcrypt in production.
PWD_SALT = os.environ.get("FRS_PWD_SALT", "change_this_default_salt")


def hash_password(password: str) -> str:
    if password is None:
        return ""
    # Use salt + SHA256 (hex)
    h = hashlib.sha256()
    h.update((password + PWD_SALT).encode("utf-8"))
    return h.hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == (password_hash or "")


# ----------------------
# UserDataManager
# ----------------------
class UserDataManager:
    def update_class_name_and_room(self, class_id: int, new_name: str, new_room: str) -> None:
        """
        Update class_name and room for a class in classes_two table.
        """
        q = "UPDATE classes_two SET class_name=%s, room=%s WHERE id=%s"
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(q, (new_name, new_room, class_id))
                conn.commit()
    def update_class_name(self, class_id: int, new_name: str) -> None:
        """
        Update only the class_name for a class in classes_two table.
        """
        q = "UPDATE classes_two SET class_name=%s WHERE id=%s"
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(q, (new_name, class_id))
                conn.commit()
    def get_user_by_student_id(self, student_id: int) -> Optional[Dict[str, Any]]:
        """
        Return user row by joining students and users tables using student_id.
        """
        q = "SELECT u.* FROM users u JOIN students s ON u.id = s.user_id WHERE s.student_id = %s LIMIT 1"
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (student_id,))
                    return cur.fetchone()
        except Exception as e:
            print(f"[ERROR] Failed to fetch user for student_id {student_id}: {e}")
            return None
    def delete_face_embeddings(self, student_id) -> None:
        """
        Delete all face embeddings for the given student_id from the face_embeddings table.
        """
        q = "DELETE FROM face_embeddings WHERE student_id = %s"
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (student_id,))
                conn.commit()
        except Exception:
            raise
    def send_absent_attendance_emails(self, session_id: int, progress_callback=None):
        """
        Send an email to each student marked absent in the given session, with class and lecturer name.
        """
        try:
            from email_utils import ABSENT_TEMPLATE, send_emails_batch
            absent_records = self.get_attendance_for_session(session_id)
            session = self.get_session_by_id(session_id)
            class_name = ""
            lecturer_name = ""
            if session:
                class_info = self.get_class_by_id(session.get('class_id'))
                class_name = class_info.get('class_name', '') if class_info else ''
                lecturer_id = session.get('lecturer_id') if 'lecturer_id' in session else None
                if lecturer_id:
                    lec = self.get_lecturer_by_lecturer_id(lecturer_id)
                    if lec:
                        lecturer_name = f"{lec.get('first_name', '')} {lec.get('last_name', '')}".strip()
            print("[Absent Attendance Emails] Fetched emails:")
            email_messages = {}
            for rec in absent_records:
                if not rec.get('present_at'):
                    email = rec.get('email') if 'email' in rec else None
                    if not email:
                        user = self.get_user_by_student_id(rec['student_id'])
                        print(f"    Lookup user for student_id={rec['student_id']}: {user}")
                        email = user.get('email') if user else None
                    print(f"  {email}")
                    if email and '@' in email and email not in email_messages:
                        subject = "Attendance Not Marked"
                        body = ABSENT_TEMPLATE.format(
                            first_name=rec.get('first_name', ''),
                            class_name=class_name,
                            lecturer_name=lecturer_name
                        )
                        email_messages[email] = {
                            'recipient_email': email,
                            'subject': subject,
                            'body': body,
                            'html': True
                        }
            if email_messages:
                send_emails_batch(list(email_messages.values()), progress_callback=progress_callback)
        except Exception as e:
            print(f"[ERROR] Failed to send absent attendance emails: {e}")
    def send_present_attendance_emails(self, session_id: int, progress_callback=None):
        """
        Send an email to each student marked present in the given session, with class and lecturer name.
        """
        try:
            from email_utils import ATTENDANCE_TEMPLATE, send_emails_batch
            present_records = self.get_attendance_for_session(session_id)
            session = self.get_session_by_id(session_id)
            class_name = ""
            lecturer_name = ""
            if session:
                class_info = self.get_class_by_id(session.get('class_id'))
                class_name = class_info.get('class_name', '') if class_info else ''
                lecturer_id = session.get('lecturer_id') if 'lecturer_id' in session else None
                if lecturer_id:
                    lec = self.get_lecturer_by_lecturer_id(lecturer_id)
                    if lec:
                        lecturer_name = f"{lec.get('first_name', '')} {lec.get('last_name', '')}".strip()
            print("[Present Attendance Emails] Fetched emails:")
            email_messages = {}
            for rec in present_records:
                if rec.get('present_at'):
                    email = rec.get('email') if 'email' in rec else None
                    if not email:
                        user = self.get_user_by_student_id(rec['student_id'])
                        print(f"    Lookup user for student_id={rec['student_id']}: {user}")
                        email = user.get('email') if user else None
                    print(f"  {email}")
                    if email and '@' in email and email not in email_messages:
                        subject = "Attendance Marked"
                        body = ATTENDANCE_TEMPLATE.format(
                            first_name=rec.get('first_name', ''),
                            class_name=class_name,
                            lecturer_name=lecturer_name
                        )
                        email_messages[email] = {
                            'recipient_email': email,
                            'subject': subject,
                            'body': body,
                            'html': True
                        }
            if email_messages:
                send_emails_batch(list(email_messages.values()), progress_callback=progress_callback)
        except Exception as e:
            print(f"[ERROR] Failed to send present attendance emails: {e}")
    def reset_student_password_and_email(self, student_id: str) -> None:
        """
        Resets a student's password, generates a random password, updates it, and emails the student (no admin authentication).
        """
        import random
        import string
        # Get student info
        student = self.get_student(student_id)
        if not student:
            raise Exception("Student not found.")
        email = student.get("email")
        if not email:
            raise Exception("Student email not found.")
        # Generate random password
        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        # Update password (hashed)
        self.update_user(student_id, {"password": new_password}, {})
        # Email the new password to the student
        subject = "Your Attendance System Password Has Been Reset"
        body = f"""
        <html><body>
        <h2>Password Reset</h2>
        <p>Hello {student.get('first_name', '')},</p>
        <p>Your password has been reset by the administrator. Your new temporary password is:</p>
        <p><b>{new_password}</b></p>
        <p>Please log in and change your password after your first login.</p>
        <br><p>Best regards,<br>Attendance System Team</p>
        </body></html>
        """
        send_email(email, subject, body, html=True)
    def unassign_students_from_class(self, class_id: int, student_ids: list) -> None:
        """
        Remove the given student_ids from the class_students_two table for the specified class_id.
        """
        if not student_ids:
            return
        q = "DELETE FROM class_students_two WHERE class_id=%s AND student_id=%s"
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    for sid in student_ids:
                        cur.execute(q, (class_id, sid))
                conn.commit()
        except Exception as e:
            print(f"[ERROR] Failed to unassign students from class {class_id}: {e}")
            raise
    def get_students_for_class(self, class_id: int) -> list:
        """
        Returns all students assigned to the given class_id, including first_name, last_name, student_id, and course.
        """
        q = (
            """
            SELECT s.student_id, u.first_name, u.last_name, s.course
            FROM students s
            JOIN users u ON s.user_id = u.id
            JOIN class_students_two cs ON s.student_id = cs.student_id
            WHERE cs.class_id = %s AND u.active = 1
            ORDER BY u.last_name ASC, u.first_name ASC
            """
        )
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (class_id,))
                    return cur.fetchall()
        except Exception as e:
            print(f"[ERROR] Failed to fetch students for class {class_id}: {e}")
            return []
    def mark_absent_students_for_session(self, session_id: int, present_student_ids: list) -> None:
        """
        For the given attendance session, mark all students assigned to the class as absent except those in present_student_ids.
        """
        # Get class_id for the session
        session = self.get_session_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        class_id = session["class_id"] if isinstance(session, dict) else session[1]
        # Get all students assigned to the class
        all_student_ids = set(self.get_student_ids_for_class(class_id))
        present_set = set(present_student_ids)
        absent_student_ids = all_student_ids - present_set
        if not absent_student_ids:
            return
        # Insert absent records
        q = "INSERT INTO attendance_records_two (session_id, student_id, present_at, confidence) VALUES (%s, %s, NULL, 0)"
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                for sid in absent_student_ids:
                    cur.execute(q, (session_id, sid))
            conn.commit()
    def assign_lecturer_to_class(self, class_id: int, lecturer_id: str, date: str = None, start_time: str = None, end_time: str = None, room: str = None) -> None:
        """
        Assign a lecturer to a class in the classes_two table and optionally update date, start_time, end_time, and room.
        """
        fields = ["lecturer_id"]
        values = [lecturer_id]
        if date is not None:
            fields.append("date")
            values.append(date)
        if start_time is not None:
            fields.append("start_time")
            values.append(start_time)
        if end_time is not None:
            fields.append("end_time")
            values.append(end_time)
        if room is not None:
            fields.append("room")
            values.append(room)
        set_clause = ", ".join([f"{field} = %s" for field in fields])
        q = f"UPDATE classes_two SET {set_clause} WHERE id = %s"
        values.append(class_id)
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(q, tuple(values))
                conn.commit()
    def update_student_profile_photo(self, student_id: str, photo_bytes: bytes) -> int:
        """Update the profile_photo BLOB for a student. Returns affected row count."""
        student_id = str(student_id).strip() if student_id is not None else student_id
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    # Log all student_ids in the table
                    cur.execute("SELECT student_id FROM students")
                    all_ids = [str(row['student_id']).strip() for row in cur.fetchall()]
                    print(f"[DEBUG] All student_ids in DB: {all_ids}")
                    # Log result of direct SELECT for this student_id
                    cur.execute("SELECT student_id FROM students WHERE student_id=%s", (student_id,))
                    match_row = cur.fetchone()
                    print(f"[DEBUG] Direct SELECT for student_id={repr(student_id)}: {match_row}")
                    # Now do the update
                    # Update profile_photo in students
                    q = "UPDATE students SET profile_photo=%s WHERE student_id=%s"
                    cur.execute(q, (photo_bytes, student_id))
                    affected = cur.rowcount
                    print(f"[DEBUG] update_student_profile_photo: student_id={repr(student_id)}, affected={affected}")
                    # Also update users.updated_at for the corresponding user
                    cur.execute("SELECT user_id FROM students WHERE student_id=%s", (student_id,))
                    user_row = cur.fetchone()
                    if user_row and 'user_id' in user_row:
                        cur.execute("UPDATE users SET updated_at=NOW() WHERE id=%s", (user_row['user_id'],))
                conn.commit()
            return affected
        except Exception as e:
            print(f"[ERROR] Failed to update profile photo for {repr(student_id)}: {e}")
            return 0

    def get_student_profile_photo(self, student_id: str) -> bytes:
        """Retrieve the profile_photo BLOB for a student."""
        student_id = str(student_id).strip() if student_id is not None else student_id
        q = "SELECT profile_photo FROM students WHERE student_id=%s"
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (student_id,))
                    row = cur.fetchone()
                    if row and row['profile_photo']:
                        return row['profile_photo']
            return None
        except Exception as e:
            print(f"[ERROR] Failed to fetch profile photo for {repr(student_id)}: {e}")
            return None
    def download_attendance_csv(self, student_id: str, file_path: str) -> None:
        """
        Export all attendance records for a student as a CSV file.
        :param student_id: The student's unique ID
        :param file_path: The path to save the CSV file
        """
        import csv
        q = (
            """
            SELECT ar.session_id, ar.present_at, ar.confidence, c.class_name, ats.name AS session_name, ats.started_at, ats.ended_at, l.first_name AS lecturer_first_name, l.last_name AS lecturer_last_name
            FROM attendance_records_two ar
            LEFT JOIN attendance_sessions_two ats ON ar.session_id = ats.id
            LEFT JOIN classes_two c ON ats.class_id = c.id
            LEFT JOIN lecturers_table_two l ON ats.lecturer_id = l.lecturer_id
            WHERE ar.student_id = %s
            ORDER BY ar.present_at DESC
            """
        )
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (student_id,))
                    records = cur.fetchall()
            fieldnames = [
                'session_id', 'session_name', 'class_name', 'lecturer_first_name', 'lecturer_last_name',
                'present_at', 'confidence', 'started_at', 'ended_at'
            ]
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in records:
                    writer.writerow(row)
        except Exception as e:
            print(f"[ERROR] Failed to export attendance CSV for student {student_id}: {e}")
    def get_face_embeddings_for_class(self, class_id: int) -> List[Dict[str, Any]]:
        """
        Returns all face embeddings for students assigned to the given class_id and who are active.
        Each row is a dict with keys: 'student_id', 'embedding'.
        """
        q = (
            """
            SELECT fe.student_id, fe.embedding
            FROM face_embeddings fe
            JOIN students s ON fe.student_id = s.student_id
            JOIN users u ON s.user_id = u.id
            JOIN class_students_two cs ON s.student_id = cs.student_id
            WHERE cs.class_id = %s AND u.active = 1
            ORDER BY fe.student_id ASC, fe.created_at DESC
            """
        )
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (class_id,))
                    rows = cur.fetchall()
                    # Unpickle embeddings
                    for r in rows:
                        if r.get('embedding'):
                            try:
                                r['embedding'] = pickle.loads(r['embedding'])
                            except Exception:
                                pass
                    return rows
        except Exception:
            raise
    def admin_login(self, admin_id: int, details: dict = None):
        """
        Log an admin login event to the audit log.
        :param admin_id: The admin's user ID
        :param details: Optional dictionary with context (e.g., IP address, device info)
        """
        self.log_admin_action(admin_id, "admin_login", details or {})

    def admin_logout(self, admin_id: int, details: dict = None):
        """
        Log an admin logout event to the audit log.
        :param admin_id: The admin's user ID
        :param details: Optional dictionary with context (e.g., IP address, device info)
        """
        self.log_admin_action(admin_id, "admin_logout", details or {})

    def log_admin_action(self, admin_id: int, action: str, details: dict):
        """
        Log an admin action to the admin_audit_log table.
        :param admin_id: The admin's user ID
        :param action: Short string describing the action (e.g., 'create_user')
        :param details: Dictionary with context (will be stored as JSON)
        """
        import json
        print(f"[DEBUG] log_admin_action called with admin_id={admin_id}, action={action}, details={details}")
        q = """
            INSERT INTO admin_audit_log (admin_id, action, details, created_at)
            VALUES (%s, %s, %s, NOW())
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (admin_id, action, json.dumps(details)))
                    print(f"[DEBUG] log_admin_action: Inserted row, rowcount={cur.rowcount}")
                conn.commit()
                print(f"[DEBUG] log_admin_action: Commit successful.")
        except Exception as e:
            print(f"[AUDIT LOG ERROR] Failed to log admin action: {e}")

    # Example usage (call this in your admin actions):
    # self.log_admin_action(admin_id, 'create_user', {'user_id': new_user_id, 'email': email})
    def get_lecturer_by_lecturer_id(self, lecturer_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single lecturer by their lecturer_id (string, e.g., 'L001') from lecturers_table_two.
        Returns a dict with lecturer info if found, else None.
        """
        q = "SELECT * FROM lecturers_table_two WHERE lecturer_id = %s LIMIT 1"
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor(pymysql.cursors.DictCursor) as cur:
                    cur.execute(q, (lecturer_id,))
                    return cur.fetchone()
        except Exception:
            raise

    def get_attendance_for_session(self, session_id: int) -> list:
        """
        Returns all attendance records for a session.
        """
        q = """
            SELECT ar.id, ar.session_id, ar.student_id, ar.present_at, ar.confidence,
                   u.first_name, u.last_name, s.course
                FROM attendance_records_two ar
            LEFT JOIN students s ON ar.student_id = s.student_id
            LEFT JOIN users u ON s.user_id = u.id
            WHERE ar.session_id=%s
            ORDER BY ar.present_at ASC
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (session_id,))
                    return cur.fetchall()
        except Exception:
            raise

    def get_session_by_id(self, session_id: int):
        """Fetch session info (name, class_id, started_at) by session_id."""
        q = "SELECT id, class_id, name, started_at FROM attendance_sessions_two WHERE id=%s"
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(q, (session_id,))
                return cur.fetchone()

    def get_class_by_id(self, class_id: int):
        """Fetch class info (class_name) by class_id."""
        q = "SELECT id, class_name FROM classes_two WHERE id=%s"
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(q, (class_id,))
                return cur.fetchone()

    def create_attendance_session(self, class_id: int, lecturer_identifier: Any, name: str = None) -> int:
        """
        Creates an attendance session row and returns session_id.
        lecturer_identifier should be lecturer_id string like 'L001'.
        """
        try:
            lecturer_id = str(lecturer_identifier)
            q = """
                INSERT INTO attendance_sessions_two (class_id, lecturer_id, name, started_at, status)
                VALUES (%s, %s, %s, NOW(), 'active')
                """
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (class_id, lecturer_id, name or None))
                    session_id = cur.lastrowid
                conn.commit()
            return session_id
        except Exception:
            raise

    def assign_students_to_class(self, class_id, student_ids):
        """
        Assigns a list of student_ids to a class in class_students_two. Removes previous assignments for that class and adds the new ones.
        """
        if not student_ids:
            return
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                # Remove existing assignments for this class
                cur.execute("DELETE FROM class_students_two WHERE class_id = %s", (class_id,))
                # Insert new assignments
                insert_q = "INSERT INTO class_students_two (class_id, student_id) VALUES (%s, %s)"
                for sid in student_ids:
                    cur.execute(insert_q, (class_id, sid))
            conn.commit()

    def get_student_ids_for_class(self, class_id):
        """
        Returns a list of student_ids assigned to the given class_id.
        """
        q = "SELECT student_id FROM class_students_two WHERE class_id = %s"
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(q, (class_id,))
                return [row["student_id"] for row in cur.fetchall()]

    def create_class(self, class_data: Dict[str, Any]) -> int:
        """
        Create a new class in the classes_two table.
        class_data should contain: cohort_id, lecturer_id, class_name, code, description, schedule
        Returns the new class id.
        """
        q = """
            INSERT INTO classes_two (cohort_id, lecturer_id, class_name, code, description, date, start_time, end_time, room)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        print(f"[DEBUG] Received class_data for create_class: {class_data}")
        try:
            cohort_id = int(class_data.get("cohort_id", 1))
            lecturer_id = str(class_data["lecturer_id"])
            class_name = class_data["class_name"]
            code = class_data["code"]
            description = class_data.get("description", "")
            date = class_data.get("date", None)
            start_time = class_data.get("start_time", None)
            end_time = class_data.get("end_time", None)
            room = class_data.get("room", None)
        except KeyError as e:
            print(f"[ERROR] Missing required field for create_class: {e}")
            raise ValueError(f"Missing required field for create_class: {e}")
        params = (cohort_id, lecturer_id, class_name, code, description, date, start_time, end_time, room)
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(q, params)
                conn.commit()
                return cur.lastrowid

    def update_class(self, class_id: int, class_data: Dict[str, Any]) -> None:
        """
        Update an existing class in the classes_two table.
        class_data should contain: cohort_id, lecturer_id, class_name, code, description, schedule
        """
        q = """
            UPDATE classes_two SET cohort_id=%s, lecturer_id=%s, class_name=%s, code=%s, description=%s, date=%s, start_time=%s, end_time=%s, room=%s
            WHERE id=%s
        """
        params = (
            int(class_data["cohort_id"]),
            str(class_data["lecturer_id"]),
            class_data["class_name"],
            class_data["code"],
            class_data.get("description", ""),
            class_data.get("date", None),
            class_data.get("start_time", None),
            class_data.get("end_time", None),
            class_data.get("room", None),
            int(class_id)
        )
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(q, params)
                conn.commit()

    def get_lecturers_table_two(self):
        """Return all lecturers from lecturers_table_two table."""
        q = "SELECT * FROM lecturers_table_two"
        with self.db_manager.get_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(q)
                return cur.fetchall()

    def authenticate_lecturer(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate a lecturer by email and password (hashed) from the lecturers_table_two table.
        Returns the lecturer row as a dict if successful, else None.
        """
        q = "SELECT * FROM lecturers_table_two WHERE email=%s AND active=1 LIMIT 1"
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (email,))
                    lecturer = cur.fetchone()
            if lecturer and verify_password(password, lecturer.get("password")):
                # Update last_login to NOW()
                try:
                    with self.db_manager.get_connection() as conn2:
                        with conn2.cursor() as cur2:
                            cur2.execute("UPDATE lecturers_table_two SET last_login=NOW() WHERE lecturer_id=%s", (lecturer["lecturer_id"],))
                        conn2.commit()
                except Exception as e:
                    print(f"Failed to update last_login: {e}")
                return lecturer
            return None
        except Exception:
            return None
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    # ---------------- Face embeddings ----------------
    def get_all_face_embeddings(self) -> List[Dict[str, Any]]:
        """
        Returns all face embeddings for all students (for recognition/testing).
        Each row is a dict with keys: 'student_id', 'embedding'.
        """
        q = """
            SELECT fe.student_id, fe.embedding
            FROM face_embeddings fe
            JOIN students s ON fe.student_id = s.student_id
            JOIN users u ON s.user_id = u.id
            WHERE u.active=1
            ORDER BY fe.student_id ASC, fe.created_at DESC
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q)
                    return cur.fetchall()
        except Exception:
            raise

    # ------------------ Create (students/users) ------------------
    def add_user(self, user_dict: Dict[str, Any], student_dict: Dict[str, Any]) -> Optional[Any]:
        """
        Adds a user row and a students row and returns created student_id (student.student_id) if available.
        user_dict should contain: first_name, last_name, email, phone, password (plaintext), role, ...
        student_dict should contain: student_id (optional), school, cohort, course, year_of_study (optional)
        """
        password_plain = user_dict.get("password") or ""
        password_hashed = hash_password(password_plain)

        insert_user_q = """
            INSERT INTO users
                (first_name, last_name, email, phone, password, role, registration_date, active, created_at, updated_at, created_by, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), 1, NOW(), NOW(), NULL, 1)
        """

        # For students table, if student_id is None we let DB auto-generate (if schema supports)
        insert_student_q = """
            INSERT INTO students (student_id, user_id, school, cohort, course, year_of_study)
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        insert_user_q,
                        (
                            user_dict.get("first_name"),
                            user_dict.get("last_name"),
                            user_dict.get("email"),
                            user_dict.get("phone"),
                            password_hashed,
                            user_dict.get("role", "Student"),
                        ),
                    )
                    user_id = cur.lastrowid

                    # Choose student_id value: if provided, use it; else create based on user_id
                    s_id = student_dict.get("student_id")
                    if not s_id:
                        # create a student_id from user_id (e.g., 10000 + user_id)
                        s_id = str(10000 + int(user_id))

                    cur.execute(
                        insert_student_q,
                        (
                            s_id,
                            user_id,
                            student_dict.get("school"),
                            student_dict.get("cohort"),
                            student_dict.get("course"),
                            student_dict.get("year_of_study"),
                        ),
                    )
                conn.commit()


            # Send email notification to the new user
            import random
            import string
            try:
                email = user_dict.get("email")
                if email:
                    # Generate a random password
                    password_plain = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
                    user_updates = {}
                    # Hash and set the password in the DB
                    user_updates['password'] = hash_password(password_plain)
                    # Update the user with the new password
                    set_clause = ", ".join([f"{k}=%s" for k in user_updates.keys()])
                    params = tuple(user_updates.values()) + (user_id,)
                    q = f"UPDATE users SET {set_clause} WHERE id=%s"
                    with self.db_manager.get_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(q, params)
                        conn.commit()
                    from email_utils import WELCOME_TEMPLATE
                    from datetime import datetime
                    subject = "Welcome to the Attendance System"
                    body = WELCOME_TEMPLATE.format(
                        first_name=user_dict.get('first_name', ''),
                        user_email=email,
                        default_password=password_plain,
                        year=datetime.now().year
                    )
                    send_email(email, subject, body, html=True)
            except Exception as e:
                print(f"Failed to send welcome email: {e}")

            return s_id

        except Exception:
            raise

    # ------------------ Read users/students ------------------
    def get_users(self) -> List[Dict[str, Any]]:
        """
        Return list of users joined with students. Each row is a dict.
        """
        q = """
            SELECT u.id AS user_id, u.first_name, u.last_name, u.email, u.phone, u.role,
                   u.registration_date, u.active, u.is_active,
                   s.student_id, s.school, s.cohort, s.course, s.year_of_study
            FROM users u
            JOIN students s ON u.id = s.user_id
            ORDER BY s.student_id ASC
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q)
                    rows = cur.fetchall()
                    return rows
        except Exception:
            raise

    def get_student(self, student_id) -> Optional[Dict[str, Any]]:
        """
        Return single student + user dict or None.
        """
        q = """
            SELECT u.id AS user_id, u.first_name, u.last_name, u.email, u.phone, u.role,
                   u.registration_date, u.active, u.is_active,
                   s.student_id, s.school, s.cohort, s.course, s.year_of_study
            FROM users u
            JOIN students s ON u.id = s.user_id
            WHERE s.student_id=%s
            LIMIT 1
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (student_id,))
                    return cur.fetchone()
        except Exception:
            raise

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        q = "SELECT * FROM users WHERE email=%s AND active=1 LIMIT 1"
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (email,))
                    return cur.fetchone()
        except Exception:
            raise

    def get_student_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        q = """
            SELECT u.id as user_id, u.first_name, u.last_name, u.email, s.student_id, s.school, s.cohort, s.course, s.year_of_study
            FROM users u JOIN students s ON u.id = s.user_id
            WHERE u.email=%s AND u.active=1 LIMIT 1
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (email,))
                    return cur.fetchone()
        except Exception:
            raise

    # ------------------ Update users/students ------------------
    def update_user(
        self, student_id, user_updates: Dict[str, Any], student_updates: Dict[str, Any]
    ) -> None:
        """
        Update users and students tables for the given student_id.
        user_updates: dict of column->value for users table (first_name, last_name, email, phone, role, password)
        student_updates: dict of column->value for students table (school, cohort, course, year_of_study)
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    # Update users via join
                    if user_updates:
                        # Handle password hashing if password in updates
                        if "password" in user_updates and user_updates["password"]:
                            user_updates["password"] = hash_password(user_updates["password"])
                        set_clause = ", ".join([f"u.{k}=%s" for k in user_updates.keys()])
                        params = tuple(user_updates.values()) + (student_id,)
                        q = f"UPDATE users u JOIN students s ON u.id = s.user_id SET {set_clause} WHERE s.student_id=%s"
                        cur.execute(q, params)

                    if student_updates:
                        set_clause2 = ", ".join([f"{k}=%s" for k in student_updates.keys()])
                        params2 = tuple(student_updates.values()) + (student_id,)
                        q2 = f"UPDATE students SET {set_clause2} WHERE student_id=%s"
                        cur.execute(q2, params2)

                conn.commit()
        except Exception:
            raise

    # ------------------ Toggle active ------------------
    def toggle_active(self, student_id) -> None:
        """
        Flip active flag for the user linked to the student_id.
        """
        q = """
            UPDATE users u
            JOIN students s ON u.id = s.user_id
            SET u.active = IF(u.active=1, 0, 1)
            WHERE s.student_id=%s
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (student_id,))
                conn.commit()
        except Exception:
            raise

    # ------------------ Face embeddings ------------------
    def add_face_embedding(self, student_id, embedding) -> None:
        """
        Stores a pickled embedding (bytes) into face_embeddings.student_id column.
        embedding can be numpy array, list, etc., it will be pickled.
        Embedding is normalized before saving.
        """
        # Only add embedding if user is active
        check_active_q = """
            SELECT u.active FROM users u
            JOIN students s ON u.id = s.user_id
            WHERE s.student_id = %s
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(check_active_q, (student_id,))
                    row = cur.fetchone()
                    if not row or not row.get('active'):
                        print(f"Embedding not added: student_id {student_id} is not active.")
                        return
            # Normalize embedding before saving
            import numpy as np
            embedding = np.array(embedding)
            embedding = embedding / np.linalg.norm(embedding)
            b = pickle.dumps(embedding)
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO face_embeddings (student_id, embedding, created_at) VALUES (%s, %s, NOW())", (student_id, b))
                conn.commit()
        except Exception:
            raise

    def get_face_embeddings(self, student_id) -> List[Any]:
        """
        Returns list of unpickled embeddings for the student_id (only if user active).
        """
        q = """
            SELECT fe.embedding
            FROM face_embeddings fe
            JOIN students s ON fe.student_id = s.student_id
            JOIN users u ON s.user_id = u.id
            WHERE fe.student_id=%s AND u.active=1
            ORDER BY fe.created_at DESC
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (student_id,))
                    rows = cur.fetchall()
                    embeddings = []
                    for r in rows:
                        raw = r.get("embedding")
                        if raw:
                            try:
                                embeddings.append(pickle.loads(raw))
                            except Exception:
                                # if stored as raw bytes of array, return raw
                                embeddings.append(raw)
                    return embeddings
        except Exception:
            raise

    # ------------------ Authentication helper ------------------
    def verify_credentials(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Utility for GUI login: returns user row if credentials valid, else None.
        Uses hash verify.
        """
        try:
            user = self.get_user_by_email(email)
            if not user:
                return None
            stored = user.get("password") or ""
            if verify_password(password, stored):
                return user
            return None
        except Exception:
            raise

    # ------------------ Helper: users by id ------------------
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Return user row by users.id
        """
        q = "SELECT * FROM users WHERE id=%s LIMIT 1"
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (user_id,))
                    return cur.fetchone()
        except Exception:
            raise

    # ------------------ Lecturers (dedicated table) ------------------
    def _resolve_lecturer_pk(self, lecturer_identifier: Any) -> Optional[int]:
        """
        Accepts either:
        - lecturers_table_two.id (int/string numeric)
        - users.id (int/string numeric) -> looks up lecturers_table_two row with user_id = users.id
        - lecturer_id (string like 'L001')
        Returns lecturers_table_two.id or None if not found.
        """
        if lecturer_identifier is None:
            return None
        try:
            lid = int(lecturer_identifier)
        except Exception:
            # not numeric; might be a lecturer_id like 'L001' or string; try to find by lecturer_id
            try:
                with self.db_manager.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT id FROM lecturers_table_two WHERE lecturer_id=%s LIMIT 1", (str(lecturer_identifier),))
                        r = cur.fetchone()
                        return r["id"] if r else None
            except Exception:
                return None
        # if numeric: first try treating as lecturers_table_two.id
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM lecturers_table_two WHERE id=%s LIMIT 1", (lid,))
                    r = cur.fetchone()
                    if r:
                        return r["id"]
                    # fall back: treat as users.id -> find lecturers_table_two row with user_id = lid
                    cur.execute("SELECT id FROM lecturers_table_two WHERE user_id=%s LIMIT 1", (lid,))
                    r2 = cur.fetchone()
                    if r2:
                        return r2["id"]
        except Exception:
            return None
        return None

    def create_lecturer(self, lecturer_data: Dict[str, Any], admin_id: int = None) -> int:
        """
        Create a lecturer in the lecturers table only (stand-alone).
        Auto-generates lecturer_id (L001, L002...).
        Returns lecturers.id (PK).
        """
        pwd = lecturer_data.get("password", "")
        hashed = hash_password(pwd)

        # Auto-generate lecturer_id like L001 for lecturers_table_two
        next_id_q = "SELECT LPAD(COALESCE(MAX(CAST(SUBSTRING(lecturer_id, 2) AS UNSIGNED)), 0) + 1, 3, '0') AS next_id FROM lecturers_table_two"

        lecturer_q = """
            INSERT INTO lecturers_table_two 
                (lecturer_id, email, first_name, last_name, other_name, phone, password, department, academic_rank, hire_date, office_location, specialization, active, last_login, registration_date, created_at, updated_at, created_by, updated_by, failed_login_attempts, locked_until)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    # Generate next lecturer_id
                    cur.execute(next_id_q)
                    res = cur.fetchone()
                    next_id = res["next_id"] if res and "next_id" in res else "001"
                    lecturer_id_val = f"L{next_id}"

                    # Insert lecturer row (stand-alone)
                    cur.execute(
                        lecturer_q,
                        (
                            lecturer_id_val,
                            lecturer_data.get("email"),
                            lecturer_data.get("first_name"),
                            lecturer_data.get("last_name"),
                            lecturer_data.get("other_name"),
                            lecturer_data.get("phone"),
                            hashed,
                            lecturer_data.get("department"),
                            lecturer_data.get("academic_rank"),
                            lecturer_data.get("hire_date"),
                            lecturer_data.get("office_location"),
                            lecturer_data.get("specialization"),
                            1,  # active
                            None,  # last_login
                            None,  # registration_date (NOW() default)
                            None,  # created_at (NOW() default)
                            None,  # updated_at (NOW() default)
                            None,  # created_by (backend/admin)
                            None,  # updated_by (backend/admin)
                            0,     # failed_login_attempts
                            None   # locked_until
                        ),
                    )
                    lecturer_row_id = cur.lastrowid
                conn.commit()
            return lecturer_id_val
            if admin_id is not None:
                self.log_admin_action(admin_id, "create_lecturer", {"lecturer_id": lecturer_id_val, **lecturer_data})
            return lecturer_id_val
        except Exception:
            raise

    def get_lecturers(self) -> List[Dict[str, Any]]:
        """
        Fetch all lecturers from the lecturers table, joined with users and their assigned classes.
        Returns a list of dicts; each dict contains lecturer info and 'classes' as a list of names.
        """
        q = """
        SELECT 
            lecturer_id,
            first_name,
            last_name,
            other_name,
            email,
            phone,
            password,
            department,
            academic_rank,
            hire_date,
            office_location,
            specialization,
            active,
            last_login,
            registration_date,
            created_at,
            updated_at,
            created_by,
            updated_by,
            failed_login_attempts,
            locked_until
        FROM lecturers_table_two
        ORDER BY lecturer_id DESC
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q)
                    rows = cur.fetchall()
            return rows
        except Exception:
            raise

    def get_lecturer_by_id(self, lecturer_pk: int) -> Optional[Dict[str, Any]]:
        """
        Fetch a single lecturer by their lecturers.id (PK), including first_name and last_name from users.
        """
        q = """
            SELECT l.*, u.first_name, u.last_name
            FROM lecturers l
            LEFT JOIN users u ON l.user_id = u.id
            WHERE l.id = %s LIMIT 1
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (lecturer_pk,))
                    return cur.fetchone()
        except Exception:
            raise

    def update_lecturer(self, lecturer_pk: int, lecturer_updates: Dict[str, Any], admin_id: int = None) -> None:
        """
        Update lecturers_table_two for the given lecturer_pk (lecturers PK).
        lecturer_updates: columns for lecturers_table_two table
        """
        try:
            print(f"[DEBUG] update_lecturer called with lecturer_id={lecturer_pk}")
            print(f"[DEBUG] lecturer_updates: {lecturer_updates}")
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    if lecturer_updates:
                        set_clause = ", ".join([f"{k}=%s" for k in lecturer_updates.keys()])
                        params = tuple(lecturer_updates.values()) + (lecturer_pk,)
                        q = f"UPDATE lecturers_table_two SET {set_clause} WHERE lecturer_id=%s"
                        print(f"[DEBUG] Executing SQL: {q} with params {params}")
                        cur.execute(q, params)
                conn.commit()
            if admin_id is not None:
                self.log_admin_action(admin_id, "update_lecturer", {"lecturer_id": lecturer_pk, **lecturer_updates})
        except Exception as e:
            print(f"[DEBUG] Exception in update_lecturer: {e}")
            raise

    def delete_lecturer(self, lecturer_pk: int, delete_user: bool = False, admin_id: int = None) -> None:
        """
        Delete a lecturer from the lecturers table. Optionally deletes the related users row.
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    if delete_user:
                        # find user_id
                        cur.execute("SELECT user_id FROM lecturers WHERE id=%s", (lecturer_pk,))
                        r = cur.fetchone()
                        if r and r.get("user_id"):
                            user_id = r["user_id"]
                            cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
                    # delete mappings first (to avoid FK issues)
                    cur.execute("DELETE FROM lecturer_classes WHERE lecturer_id=%s", (lecturer_pk,))
                    # delete lecturer row
                    cur.execute("DELETE FROM lecturers WHERE id=%s", (lecturer_pk,))
                conn.commit()
            if admin_id is not None:
                self.log_admin_action(admin_id, "delete_lecturer", {"lecturer_id": lecturer_pk, "delete_user": delete_user})
        except Exception:
            raise

    def toggle_lecturer_active(self, lecturer_identifier: Any, admin_id: int = None) -> None:
        """
        Toggle active flag on the users table for the lecturer referenced by lecturer_identifier (lecturers.id or users.id).
        """
        try:
            lecturer_pk = self._resolve_lecturer_pk(lecturer_identifier)
            if lecturer_pk is None:
                # fallback: if passed numeric assume it's a users.id
                try:
                    uid = int(lecturer_identifier)
                    with self.db_manager.get_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("UPDATE users SET active = IF(active=1, 0, 1) WHERE id=%s", (uid,))
                        conn.commit()
                    if admin_id is not None:
                        self.log_admin_action(admin_id, "toggle_lecturer_active", {"user_id": uid})
                    return
                except Exception:
                    raise ValueError("Lecturer not found to toggle active.")

            # get user_id
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT user_id FROM lecturers WHERE id=%s", (lecturer_pk,))
                    r = cur.fetchone()
                    if not r:
                        raise ValueError("Lecturer not found.")
                    user_id = r["user_id"]
                    cur.execute("UPDATE users SET active = IF(active=1, 0, 1) WHERE id=%s", (user_id,))
                conn.commit()
            if admin_id is not None:
                self.log_admin_action(admin_id, "toggle_lecturer_active", {"lecturer_pk": lecturer_pk})
        except Exception:
            raise

    def reset_lecturer_password(self, lecturer_identifier: Any, new_password: str, admin_id: int = None) -> None:
        """
        Reset the lecturer's password (hashing applied).
        lecturer_identifier can be lecturers.id or users.id.
        """
        try:
            hashed = hash_password(new_password)
            # try resolving lecturer PK to get user_id
            lecturer_pk = self._resolve_lecturer_pk(lecturer_identifier)
            if lecturer_pk:
                with self.db_manager.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT user_id FROM lecturers WHERE id=%s", (lecturer_pk,))
                        r = cur.fetchone()
                        if not r:
                            raise ValueError("Lecturer not found.")
                        user_id = r["user_id"]
                        cur.execute("UPDATE users SET password=%s WHERE id=%s", (hashed, user_id))
                    conn.commit()
                if admin_id is not None:
                    self.log_admin_action(admin_id, "reset_lecturer_password", {"lecturer_pk": lecturer_pk, "user_id": user_id})
                return
            # fallback: if numeric treat as users.id
            try:
                uid = int(lecturer_identifier)
                with self.db_manager.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE users SET password=%s WHERE id=%s", (hashed, uid))
                    conn.commit()
                if admin_id is not None:
                    self.log_admin_action(admin_id, "reset_lecturer_password", {"user_id": uid})
                return
            except Exception:
                raise ValueError("Could not resolve lecturer identifier for password reset.")
        except Exception:
            raise

    # ------------------ Classes & Assignments ------------------
    def get_classes(self) -> List[Dict[str, Any]]:
        """
        Return available classes (id, class_name, code, cohort_id, room, lecturer_id, lecturer_name, student_count) from classes_two.
        Joins lecturers_table_two for lecturer_name and counts students from class_students_two.
        """
        q = """
            SELECT c.id, c.class_name, c.code, c.cohort_id, c.room, c.lecturer_id,
                   CONCAT(l.first_name, ' ', l.last_name) AS lecturer_name,
                   (
                       SELECT COUNT(*) FROM class_students_two cs WHERE cs.class_id = c.id
                   ) AS student_count
            FROM classes_two c
            LEFT JOIN lecturers_table_two l ON c.lecturer_id = l.lecturer_id
            ORDER BY c.class_name ASC
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q)
                    return cur.fetchall()
        except Exception:
            raise


    def assign_lecturer_to_classes(self, lecturer_identifier: Any, class_ids: Iterable[Any], admin_id: int = None) -> None:
        """
        Bulk assign classes to a lecturer. Replaces existing assignments.
        Also updates classes_two. Unassigned classes will have lecturer_id set to NULL.
        Checks that lecturer_id exists before assignment. Handles FK errors.
        lecturer_identifier: lecturers.id or users.id or lecturer_id string like 'L001'.
        class_ids: iterable of class ids (ints or string convertible).
        """
        try:
            lecturer_id = str(lecturer_identifier)
            # Normalize class_ids to ints
            cids = [int(x) for x in class_ids]

            print(f"[DEBUG] assign_lecturer_to_classes: lecturer_id={lecturer_id}, class_ids={cids}")

            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    # Check if lecturer_id exists in lecturers_table_two
                    cur.execute("SELECT COUNT(*) FROM lecturers_table_two WHERE lecturer_id=%s", (lecturer_id,))
                    exists = cur.fetchone()[0]
                    print(f"[DEBUG] lecturer_id exists in lecturers_table_two: {exists}")
                    if not exists and cids:
                        raise ValueError(f"Lecturer ID {lecturer_id} does not exist in lecturers_table_two.")

                    # Remove existing mappings
                    cur.execute("DELETE FROM lecturer_classes WHERE lecturer_id=%s", (lecturer_id,))
                    # Set lecturer_id=NULL in classes_two for all classes previously assigned to this lecturer
                    cur.execute("UPDATE classes_two SET lecturer_id=NULL WHERE lecturer_id=%s", (lecturer_id,))
                    # Insert new mappings and update classes_two
                    if cids:
                        ins_q = "INSERT INTO lecturer_classes (lecturer_id, class_id) VALUES (%s, %s)"
                        for cid in cids:
                            cur.execute(ins_q, (lecturer_id, cid))
                        # Set lecturer_id in classes_two for assigned classes (only if lecturer_id exists)
                        print(f"[DEBUG] Updating classes_two: setting lecturer_id={lecturer_id} for class_ids={cids}")
                        cur.execute(f"UPDATE classes_two SET lecturer_id=%s WHERE id IN ({','.join(['%s']*len(cids))})", tuple([lecturer_id] + cids))
                conn.commit()
            if admin_id is not None:
                self.log_admin_action(admin_id, "assign_lecturer_to_classes", {"lecturer_id": lecturer_id, "class_ids": cids})
        except Exception as e:
            # Provide clearer error for FK issues
            if hasattr(e, 'args') and e.args and 'foreign key constraint fails' in str(e.args[1]).lower():
                print(f"[ERROR] Foreign key constraint failed for lecturer_id={lecturer_id}, class_ids={cids}")
                raise Exception("Failed to assign lecturer: The lecturer_id does not exist in lecturers_table_two or is invalid.")
            print(f"[ERROR] Exception in assign_lecturer_to_classes: {e}")
            raise

    def get_lecturer_classes(self, lecturer_identifier: Any) -> List[Dict[str, Any]]:
        """
        Returns all classes assigned to a lecturer (single lecturer per class model).
        Accepts lecturer_identifier which should be lecturer_id string like 'L001'.
        """
        try:
            lecturer_id = str(lecturer_identifier)
            print(f"[DEBUG] Fetching classes for lecturer_id: {lecturer_id}")
            q = """
                SELECT id, cohort_id, class_name, code
                FROM classes_two
                WHERE lecturer_id=%s
                ORDER BY class_name ASC
            """
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (lecturer_id,))
                    results = cur.fetchall()
                    print(f"[DEBUG] Classes fetched: {results}")
                    return results
        except Exception as e:
            print(f"[DEBUG] Exception in get_lecturer_classes: {e}")
            raise


    def add_attendance_record(self, session_id: int, student_id: str, confidence: float) -> None:
        """
        Insert a recognized student's attendance record.
        """
        q = """
                INSERT INTO attendance_records_two (session_id, student_id, present_at, confidence)
                VALUES (%s, %s, NOW(), %s)
            """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (session_id, student_id, confidence))
                conn.commit()
            # Send email notification to the student
            try:
                # Fetch student email, name, and class name
                with self.db_manager.get_connection() as conn2:
                    with conn2.cursor() as cur2:
                        cur2.execute("""
                            SELECT u.email, u.first_name, c.class_name
                            FROM users u
                            JOIN students s ON u.id = s.user_id
                            JOIN attendance_sessions_two ats ON ats.id = %s
                            JOIN classes_two c ON ats.class_id = c.id
                            WHERE s.student_id = %s
                        """, (session_id, student_id))
                        row = cur2.fetchone()
                        if row:
                            email, first_name, class_name = row
                            # Skip if email is missing or invalid
                            if not email or '@' not in email or email.strip().lower() == 'email':
                                print(f"Skipping attendance email: invalid or missing email for student_id {student_id}")
                            else:
                                from email_utils import ATTENDANCE_TEMPLATE
                                subject = "Attendance Marked"
                                body = ATTENDANCE_TEMPLATE.format(first_name=first_name, session_id=session_id, class_name=class_name)
                                send_email(email, subject, body, html=True)
            except Exception as e:
                print(f"Failed to send attendance email: {e}")
        except Exception:
            raise

    def get_attendance_summary_per_class(self, student_id: str) -> list:
        """
        Returns a list of dicts: [{class_id, class_name, total_sessions, attended_sessions, attendance_percentage}]
        """
        q = (
            """
            SELECT
                c.id AS class_id,
                c.class_name,
                COUNT(DISTINCT ats.id) AS total_sessions,
                COUNT(DISTINCT CASE WHEN ar.present_at IS NOT NULL THEN ats.id END) AS attended_sessions,
                ROUND(
                    100.0 * COUNT(DISTINCT CASE WHEN ar.present_at IS NOT NULL THEN ats.id END) /
                    NULLIF(COUNT(DISTINCT ats.id), 0), 2
                ) AS attendance_percentage
            FROM classes_two c
            JOIN class_students_two cs ON cs.class_id = c.id
            JOIN attendance_sessions_two ats ON ats.class_id = c.id
            LEFT JOIN attendance_records_two ar ON ar.session_id = ats.id AND ar.student_id = %s
            WHERE cs.student_id = %s
            GROUP BY c.id, c.class_name
            """
        )
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (student_id, student_id))
                    return cur.fetchall()
        except Exception as e:
            print(f"[ERROR] Failed to fetch attendance summary for student {student_id}: {e}")
            return []

def get_attendance_for_session(self, session_id: int) -> List[Dict[str, Any]]:
        """
        Returns all attendance records for a session.
        """
        q = """
            SELECT ar.id, ar.session_id, ar.student_id, ar.present_at, ar.confidence,
                   u.first_name, u.last_name, s.course
                FROM attendance_records_two ar
            LEFT JOIN students s ON ar.student_id = s.student_id
            LEFT JOIN users u ON s.user_id = u.id
            WHERE ar.session_id=%s
            ORDER BY ar.present_at ASC
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (session_id,))
                    return cur.fetchall()
        except Exception:
            raise


# If run as script, allow a quick DB test (do not run in production)
if __name__ == "__main__":
    print("Testing DatabaseManager connection...")
    try:
        dm = DatabaseManager()
        with dm.get_connection() as c:
            with c.cursor() as cur:
                cur.execute("SELECT 1 as ok")
                print("DB OK:", cur.fetchone())
    except Exception as ex:
        print("DB connection failed:", ex)
