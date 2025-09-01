import pymysql
from user_data_manager import DatabaseManager

class AdminDataManager:
    def __init__(self, db_manager=None):
        self.db_manager = db_manager or DatabaseManager()

    def get_admin_by_email(self, email):
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT a.*, u.* FROM admins a
                    JOIN users u ON a.user_id = u.id
                    WHERE u.email=%s
                """, (email,))
                return cur.fetchone()

    def validate_admin_login(self, email, password, max_attempts=5, lock_minutes=15):
        admin = self.get_admin_by_email(email)
        if not admin:
            return False, "Incorrect email or password."
        from admin_security_manager import AdminSecurityManager
        asm = AdminSecurityManager(self.db_manager)
        # Check if account is locked
        from datetime import datetime
        locked_until = admin.get('locked_until')
        if locked_until and locked_until > datetime.now():
            return False, f"Account locked until {locked_until}."
        # Check password
        if asm.check_password(password, admin.get('password_hash')) and admin.get('active', 1) == 1:
            asm.reset_failed_attempts(admin['id'])
            return True, None
        else:
            asm.increment_failed_attempts(admin['id'], max_attempts=max_attempts, lock_minutes=lock_minutes)
            return False, "Incorrect email or password."
