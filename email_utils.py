import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configure your SMTP server details here

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SENDER_EMAIL = 'cargoconnect084@gmail.com'
SENDER_PASSWORD = 'pkyb knsp atnb rmip'


# --- HTML Email Templates ---
WELCOME_TEMPLATE = '''
<html>
<body>
  <h2>Welcome to the Attendance System, {first_name}!</h2>
  <p>Your account has been created. You can now access the system and mark your attendance.</p>
  <p>If you have any questions, please contact your administrator.</p>
  <br>
  <p>Best regards,<br>Attendance System Team</p>
</body>
</html>
'''

ATTENDANCE_TEMPLATE = '''
<html>
<body>
  <h2>Attendance Marked</h2>
  <p>Hello {first_name},</p>
  <p>Your attendance has been marked for session <b>{session_id}</b> in class <b>{class_name}</b>.</p>
  <p>If you believe this is a mistake, please contact your lecturer.</p>
  <br>
  <p>Best regards,<br>Attendance System Team</p>
</body>
</html>
'''

def send_email(recipient_email, subject, body, html=False):
    msg = MIMEMultipart('alternative')
    msg['From'] = SENDER_EMAIL
    msg['To'] = recipient_email
    msg['Subject'] = subject
    if html:
        msg.attach(MIMEText(body, 'html'))
    else:
        msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
        server.quit()
        print(f"Email sent to {recipient_email}")
    except Exception as e:
        print(f"Failed to send email to {recipient_email}: {e}")
