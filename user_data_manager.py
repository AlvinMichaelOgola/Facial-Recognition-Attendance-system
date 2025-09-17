# user_data_manager.py
"""
Database-backed user & student manager for FRS MVP.

Dependencies:
- PyMySQL (pip install pymysql)

Expected DB tables (simplified):
- users (id PK, first_name, last_name, email UNIQUE, phone, password, role, registration_date, active, is_active, created_at, updated_at)
- students (id PK, student_id UNIQUE, user_id FK -> users.id, school, cohort, course, year_of_study)
- face_embeddings (id PK, student_id, embedding BLOB, created_at)

If your schema uses different column names, adapt the SQL accordingly.
"""

import os
import pymysql
import pymysql.cursors
import pickle
import hashlib
import binascii
from typing import Optional, List, Dict, Any

# ----------------------
# Database connection
# ----------------------
class DatabaseManager:
    def __init__(self, host: str = "localhost", user: str = "root", password: str = "", db: str = "frs_v3.1", port: int = 3306):
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
            charset='utf8mb4'
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
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    # ------------------ Create ------------------
    def add_user(self, user_dict: Dict[str, Any], student_dict: Dict[str, Any]) -> Optional[Any]:
        """
        Adds a user row and a students row and returns created student_id (student.student_id) if available.
        user_dict should contain: first_name, last_name, email, phone, password (plaintext), role, ...
        student_dict should contain: student_id (optional), school, cohort, course, year_of_study (optional)

        Returns:
            student_id (str or int) on success, or dict with details, or raises exception on failure.
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
                    cur.execute(insert_user_q, (
                        user_dict.get("first_name"),
                        user_dict.get("last_name"),
                        user_dict.get("email"),
                        user_dict.get("phone"),
                        password_hashed,
                        user_dict.get("role", "Student")
                    ))
                    user_id = cur.lastrowid

                    # Choose student_id value: if provided, use it; else use NULL (DB can AUTOGEN or we use user_id)
                    s_id = student_dict.get("student_id")
                    # If student_id is None, we can set it to a string based on user_id (e.g., starting at 10000)
                    if not s_id:
                        # create a student_id from user_id (e.g., 10000 + user_id)
                        s_id = str(10000 + int(user_id))

                    cur.execute(insert_student_q, (
                        s_id,
                        user_id,
                        student_dict.get("school"),
                        student_dict.get("cohort"),
                        student_dict.get("course"),
                        student_dict.get("year_of_study")
                    ))
                    # commit transaction
                conn.commit()

            return s_id

        except Exception as e:
            # If error, bubble up so GUI shows message
            raise

    # ------------------ Read ------------------
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
        except Exception as e:
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
        except Exception as e:
            raise

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        q = "SELECT * FROM users WHERE email=%s LIMIT 1"
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(q, (email,))
                    return cur.fetchone()
        except Exception as e:
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
        except Exception as e:
            raise

    # ------------------ Update ------------------
    def update_user(self, student_id, user_updates: Dict[str, Any], student_updates: Dict[str, Any]) -> None:
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
                        if 'password' in user_updates and user_updates['password']:
                            user_updates['password'] = hash_password(user_updates['password'])
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
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
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
