
# Modular MySQL/MariaDB connection manager
import pymysql

class DatabaseManager:
    def __init__(self, host='localhost', user='root', password='', db='frs_v3.1'):
        self.host = host
        self.user = user
        self.password = password
        self.db = db

    def get_connection(self):
        return pymysql.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            db=self.db,
            cursorclass=pymysql.cursors.DictCursor
        )

class UserDataManager:
    def __init__(self, db_manager=None):
        self.db_manager = db_manager or DatabaseManager()

    def add_user(self, user_dict, student_dict):
        # user_dict: {first_name, last_name, email, phone, password, role, ...}
        # student_dict: {student_id, school, cohort, course}
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                # Insert user
                cur.execute("""
                    INSERT INTO users (first_name, last_name, email, phone, password, role, registration_date, active, created_at, updated_at, created_by, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), 1, NOW(), NOW(), NULL, 1)
                """, (
                    user_dict['first_name'], user_dict['last_name'], user_dict['email'], user_dict['phone'],
                    user_dict['password'], user_dict['role']
                ))
                user_id = cur.lastrowid
                # Insert student
                cur.execute("""
                    INSERT INTO students (student_id, user_id, school, cohort, course)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    student_dict['student_id'], user_id, student_dict['school'], student_dict['cohort'], student_dict['course']
                ))
            conn.commit()

    def get_users(self):
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT u.*, s.student_id, s.school, s.cohort, s.course
                    FROM users u
                    JOIN students s ON u.id = s.user_id
                """)
                return cur.fetchall()

    def update_user(self, student_id, user_updates, student_updates):
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                # Update users table
                set_clause = ', '.join([f"{k}=%s" for k in user_updates])
                if set_clause:
                    cur.execute(f"UPDATE users u JOIN students s ON u.id = s.user_id SET {set_clause} WHERE s.student_id=%s",
                        tuple(user_updates.values()) + (student_id,))
                # Update students table
                set_clause2 = ', '.join([f"{k}=%s" for k in student_updates])
                if set_clause2:
                    cur.execute(f"UPDATE students SET {set_clause2} WHERE student_id=%s",
                        tuple(student_updates.values()) + (student_id,))
            conn.commit()

    def toggle_active(self, student_id):
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users u JOIN students s ON u.id = s.user_id
                    SET u.active = IF(u.active=1, 0, 1)
                    WHERE s.student_id=%s
                """, (student_id,))
            conn.commit()

    def get_student(self, student_id):
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT u.*, s.student_id, s.school, s.cohort, s.course
                    FROM users u
                    JOIN students s ON u.id = s.user_id
                    WHERE s.student_id=%s
                """, (student_id,))
                return cur.fetchone()

    def add_face_embedding(self, student_id, embedding):
        import pickle
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO face_embeddings (student_id, embedding, created_at)
                    VALUES (%s, %s, NOW())
                """, (student_id, pickle.dumps(embedding)))
            conn.commit()

    def get_face_embeddings(self, student_id):
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                # Only return embeddings if user is active
                cur.execute("""
                    SELECT fe.embedding FROM face_embeddings fe
                    JOIN students s ON fe.student_id = s.student_id
                    JOIN users u ON s.user_id = u.id
                    WHERE fe.student_id=%s AND u.active=1
                """, (student_id,))
                return [row['embedding'] for row in cur.fetchall()]
