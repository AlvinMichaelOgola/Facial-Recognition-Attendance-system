import bcrypt
import pyotp
import itsdangerous
import smtplib
from email.mime.text import MIMEText
from user_data_manager import DatabaseManager
from datetime import datetime, timedelta

class AdminSecurityManager:
    def __init__(self, db_manager=None):
        self.db_manager = db_manager or DatabaseManager()
        self.token_serializer = itsdangerous.URLSafeTimedSerializer('your-secret-key')

    def hash_password(self, password):
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, password, password_hash):
        return bcrypt.checkpw(password.encode(), password_hash.encode())

    def generate_mfa_secret(self):
        return pyotp.random_base32()

    def verify_mfa(self, secret, code):
        totp = pyotp.TOTP(secret)
        return totp.verify(code)

    def generate_reset_token(self, email):
        return self.token_serializer.dumps(email)

    def verify_reset_token(self, token, max_age=3600):
        try:
            email = self.token_serializer.loads(token, max_age=max_age)
            return email
        except itsdangerous.BadSignature:
            return None

    def send_email(self, to_email, subject, body):
        # Configure SMTP server here
        smtp_server = 'smtp.example.com'
        smtp_port = 587
        smtp_user = 'your-email@example.com'
        smtp_pass = 'your-email-password'
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = to_email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [to_email], msg.as_string())

    def log_admin_action(self, admin_id, action, details=None):
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO admin_audit_log (admin_id, action, details, created_at)
                    VALUES (%s, %s, %s, NOW())
                """, (admin_id, action, details))
            conn.commit()

    def update_last_login(self, admin_id):
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE admins SET last_login=NOW() WHERE id=%s", (admin_id,))
            conn.commit()

    def increment_failed_attempts(self, admin_id, max_attempts=5, lock_minutes=15):
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT failed_attempts FROM admins WHERE id=%s", (admin_id,))
                row = cur.fetchone()
                attempts = row['failed_attempts'] + 1 if row else 1
                if attempts >= max_attempts:
                    locked_until = datetime.now() + timedelta(minutes=lock_minutes)
                    cur.execute("UPDATE admins SET failed_attempts=%s, locked_until=%s WHERE id=%s", (attempts, locked_until, admin_id))
                else:
                    cur.execute("UPDATE admins SET failed_attempts=%s WHERE id=%s", (attempts, admin_id))
            conn.commit()

    def reset_failed_attempts(self, admin_id):
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE admins SET failed_attempts=0, locked_until=NULL WHERE id=%s", (admin_id,))
            conn.commit()

    def set_email_verified(self, admin_id):
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE admins SET email_verified=1 WHERE id=%s", (admin_id,))
            conn.commit()

    def set_verification_token(self, admin_id, token):
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE admins SET verification_token=%s WHERE id=%s", (token, admin_id))
            conn.commit()

    def set_reset_token(self, admin_id, token, expiry):
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE admins SET reset_token=%s, reset_token_expiry=%s WHERE id=%s", (token, expiry, admin_id))
            conn.commit()
