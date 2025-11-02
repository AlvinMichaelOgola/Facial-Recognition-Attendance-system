def send_emails_batch(email_messages, progress_callback=None):
    """
    email_messages: list of dicts with keys: recipient_email, subject, body, html
    progress_callback: function(current, total) called after each email
    Reuses a single SMTP connection for all emails in the batch.
    """
    import time
    logging.info(f"Batch sending {len(email_messages)} emails...")
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        total = len(email_messages)
        for idx, msg_info in enumerate(email_messages, 1):
            msg = MIMEMultipart('alternative')
            msg['From'] = SENDER_EMAIL
            msg['To'] = msg_info['recipient_email']
            msg['Subject'] = msg_info['subject']
            if msg_info.get('html'):
                msg.attach(MIMEText(msg_info['body'], 'html'))
            else:
                msg.attach(MIMEText(msg_info['body'], 'plain'))
            try:
                server.sendmail(SENDER_EMAIL, msg_info['recipient_email'], msg.as_string())
                logging.info(f"Email sent to {msg_info['recipient_email']}")
            except Exception as e:
                logging.error(f"Failed to send email to {msg_info['recipient_email']}: {e}")
            if progress_callback:
                progress_callback(idx, total)
            time.sleep(0.2)  # Small delay to avoid spam detection
        server.quit()
    except Exception as e:
        logging.error(f"Batch email sending failed: {e}")
ABSENT_TEMPLATE = '''
<html>
<body>
  <h2>Attendance Not Marked</h2>
  <p>Hello {first_name},</p>
  <p>Your attendance was <b>not marked</b> for class <b>{class_name}</b>.</p>
  <p>If you believe this is a mistake, please contact your lecturer, {lecturer_name}, as soon as possible.</p>
  <br>
  <p>Best regards,<br>Attendance System Team</p>
</body>
</html>
'''
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
  <p>Your attendance has been marked for class <b>{class_name}</b>.</p>
  <p>If you believe this is a mistake, please contact your lecturer, {lecturer_name}.</p>
  <br>
  <p>Best regards,<br>Attendance System Team</p>
</body>
</html>
'''

import logging

def send_email(recipient_email, subject, body, html=False):
  msg = MIMEMultipart('alternative')
  msg['From'] = SENDER_EMAIL
  msg['To'] = recipient_email
  msg['Subject'] = subject
  if html:
    msg.attach(MIMEText(body, 'html'))
  else:
    msg.attach(MIMEText(body, 'plain'))

  logging.info(f"Attempting to send email to {recipient_email} with subject '{subject}'")
  try:
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SENDER_EMAIL, SENDER_PASSWORD)
    server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
    server.quit()
    logging.info(f"Email sent to {recipient_email}")
  except Exception as e:
    logging.error(f"Failed to send email to {recipient_email}: {e}")
