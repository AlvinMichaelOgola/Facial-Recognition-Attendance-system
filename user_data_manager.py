"""
user_data_manager.py

Database-backed user & student manager for FRS MVP.

Dependencies:
- PyMySQL (pip install pymysql)

Expected DB tables (simplified):
- users (id PK, first_name, last_name, email UNIQUE, phone, password, role, registration_date, active, is_active, created_at, updated_at, created_by)
- students (id PK, student_id UNIQUE, user_id FK -> users.id, school, cohort, course, year_of_study)
- face_embeddings (id PK, student_id, embedding BLOB, created_at)
- lecturers (id PK, lecturer_id, name, email, department, academic_rank, hire_date, status, office_location, specialization, created_at, updated_at, user_id)
- classes (id PK, cohort_id, class_name, code, ...)
- lecturer_classes (id PK, lecturer_id FK -> lecturers.id, class_id FK -> classes.id)
- attendance_sessions (id PK, class_id, lecturer_id, name, started_at, ended_at, status)
- attendance_records (id PK, session_id, student_id, present_at, confidence)

If your schema uses different column names, adapt the SQL accordingly.
"""

import os
import pickle
import hashlib
from typing import Optional, List, Dict, Any, Iterable

import pymysql
import pymysql.cursors


# ----------------------
# Database connection
# ----------------------
class DatabaseManager:
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
    def get_cohorts_two(self):
        """Return all cohorts from cohorts_two table."""
        q = "SELECT * FROM cohorts_two"
        with self.db_manager.get_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(q)
                return cur.fetchall()

    def get_lecturers_table_two(self):
        """Return all lecturers from lecturers_table_two table."""
        q = "SELECT * FROM lecturers_table_two"
        with self.db_manager.get_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(q)
                return cur.fetchall()
    def create_class(self, class_data: Dict[str, Any]) -> int:
        """
        Create a new class in the classes_two table.
        class_data should contain: cohort_id, lecturer_id, class_name, code, description, schedule
        Returns the new class id.
        """
        q = """
            INSERT INTO classes_two (cohort_id, lecturer_id, class_name, code, description, schedule)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        params = (
            int(class_data["cohort_id"]),
            str(class_data["lecturer_id"]),
            class_data["class_name"],
            class_data["code"],
            class_data.get("description", ""),
            class_data.get("schedule", "")
        )
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(q, params)
                conn.commit()
                return cur.lastrowid
            with self.conn.cursor() as cur:
                cur.execute(q, params)
                self.conn.commit()
                return cur.lastrowid

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
        q = "SELECT * FROM users WHERE email=%s LIMIT 1"
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
            WHERE u.email=%s LIMIT 1
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
        """
        q = "INSERT INTO face_embeddings (student_id, embedding, created_at) VALUES (%s, %s, NOW())"
        try:
            b = pickle.dumps(embedding)
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (student_id, b))
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

    def create_lecturer(self, lecturer_data: Dict[str, Any]) -> int:
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
        Fetch a single lecturer by their lecturers.id (PK).
        """
        q = "SELECT * FROM lecturers WHERE id = %s LIMIT 1"
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (lecturer_pk,))
                    return cur.fetchone()
        except Exception:
            raise

    def update_lecturer(self, lecturer_pk: int, lecturer_updates: Dict[str, Any], user_updates: Dict[str, Any]) -> None:
        """
        Update lecturers and users tables for the given lecturer_pk (lecturers PK).
        lecturer_updates: columns for lecturers table
        user_updates: columns for users table
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    if lecturer_updates:
                        set_clause = ", ".join([f"{k}=%s" for k in lecturer_updates.keys()])
                        params = tuple(lecturer_updates.values()) + (lecturer_pk,)
                        q = f"UPDATE lecturers SET {set_clause} WHERE id=%s"
                        cur.execute(q, params)

                    if user_updates:
                        # Get user_id for this lecturer
                        cur.execute("SELECT user_id FROM lecturers WHERE id=%s", (lecturer_pk,))
                        row = cur.fetchone()
                        if row:
                            user_id = row["user_id"]
                            if "password" in user_updates and user_updates["password"]:
                                user_updates["password"] = hash_password(user_updates["password"])
                            set_clause2 = ", ".join([f"{k}=%s" for k in user_updates.keys()])
                            params2 = tuple(user_updates.values()) + (user_id,)
                            q2 = f"UPDATE users SET {set_clause2} WHERE id=%s"
                            cur.execute(q2, params2)
                conn.commit()
        except Exception:
            raise

    def delete_lecturer(self, lecturer_pk: int, delete_user: bool = False) -> None:
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
        except Exception:
            raise

    def toggle_lecturer_active(self, lecturer_identifier: Any) -> None:
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
        except Exception:
            raise

    def reset_lecturer_password(self, lecturer_identifier: Any, new_password: str) -> None:
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
                return
            # fallback: if numeric treat as users.id
            try:
                uid = int(lecturer_identifier)
                with self.db_manager.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE users SET password=%s WHERE id=%s", (hashed, uid))
                    conn.commit()
                return
            except Exception:
                raise ValueError("Could not resolve lecturer identifier for password reset.")
        except Exception:
            raise

    # ------------------ Classes & Assignments ------------------
    def get_classes(self) -> List[Dict[str, Any]]:
        """
        Return available classes (id, class_name, code, cohort_id)
        """
        q = "SELECT id, cohort_id, class_name, code FROM classes ORDER BY class_name ASC"
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q)
                    return cur.fetchall()
        except Exception:
            raise

    def assign_lecturer_to_class(self, lecturer_identifier: Any, class_id: int) -> None:
        """
        Inserts a mapping between lecturer (lecturers.id or users.id) and class.
        """
        try:
            # Always use the string lecturer_id (e.g., 'L001') for the mapping table
            lecturer_id_str = str(lecturer_identifier)
            print(f"[DEBUG] Inserting into lecturer_classes: lecturer_id={lecturer_id_str}, class_id={class_id}")
            q = "INSERT INTO lecturer_classes (lecturer_id, class_id, assigned_by, assigned_at) VALUES (%s, %s, %s, NOW())"
            assigned_by = 'system'  # Replace with admin user ID if available
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (lecturer_id_str, class_id, assigned_by))
                conn.commit()
        except Exception:
            raise

    def assign_lecturer_to_classes(self, lecturer_identifier: Any, class_ids: Iterable[Any]) -> None:
        """
        Bulk assign classes to a lecturer. Replaces existing assignments.
        lecturer_identifier: lecturers.id or users.id or lecturer_id string like 'L001'.
        class_ids: iterable of class ids (ints or string convertible).
        """
        try:
            lecturer_id = str(lecturer_identifier)
            # Normalize class_ids to ints
            cids = [int(x) for x in class_ids]

            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    # Remove existing mappings
                    cur.execute("DELETE FROM lecturer_classes WHERE lecturer_id=%s", (lecturer_id,))
                    # Insert new mappings
                    if cids:
                        ins_q = "INSERT INTO lecturer_classes (lecturer_id, class_id) VALUES (%s, %s)"
                        for cid in cids:
                            cur.execute(ins_q, (lecturer_id, cid))
                conn.commit()
        except Exception:
            raise

    def get_lecturer_classes(self, lecturer_identifier: Any) -> List[Dict[str, Any]]:
        """
        Returns all classes assigned to a lecturer (single lecturer per class model).
        Accepts lecturer_identifier which should be lecturer_id string like 'L001'.
        """
        try:
            lecturer_id = str(lecturer_identifier)
            q = """
                SELECT id, cohort_id, class_name, code
                FROM classes_two
                WHERE lecturer_id=%s
                ORDER BY class_name ASC
            """
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (lecturer_id,))
                    return cur.fetchall()
        except Exception:
            raise

    # ------------------ Attendance ------------------
    def create_attendance_session(self, class_id: int, lecturer_identifier: Any, name: Optional[str] = None) -> int:
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

    def end_attendance_session(self, session_id: int) -> None:
        """
        Marks a session as finished.
        """
        q = "UPDATE attendance_sessions_two SET ended_at=NOW(), status='finished' WHERE id=%s"
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (session_id,))
                conn.commit()
        except Exception:
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
        except Exception:
            raise

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
