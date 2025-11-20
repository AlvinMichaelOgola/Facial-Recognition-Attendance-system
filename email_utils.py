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
<body style="font-family: Arial, sans-serif; background-color: #f8f9fa; margin:0; padding:0;">
  <div style="background-color: #003366; color: #fff; padding: 20px; text-align: center;">
    <h1 style="margin:0; font-size:2em;">RollCall FRS</h1>
    <p style="margin:0; font-size:1.1em;">Facial Recognition Attendance System</p>
  </div>
  <div style="padding: 24px;">
    <h2 style="color:#003366;">Welcome, {first_name}!</h2>
    <p>We're excited to have you on board. Your account for <b>RollCall FRS</b> has been created. You can now log in and start marking your attendance with ease.</p>
    <hr style="margin:20px 0;">
    <p><b>Your login details:</b></p>
    <ul>
      <li><b>Email:</b> <span style="font-family: monospace;">{user_email}</span></li>
      <li><b>Default Password:</b> <span style="font-family: monospace;">{default_password}</span></li>
    </ul>
    <p style="color: red;">Please change your password after your first login for security.</p>
    <p><b>How to get started:</b></p>
    <ol>
      <li>Go to the RollCall FRS dashboard using the link below.</li>
      <li>Log in with your email and default password.</li>
      <li>Change your password from your profile settings.</li>
      <li>Begin tracking your attendance!</li>
    </ol>
    
    <hr style="margin:20px 0;">
    <p>If you have any questions or need help, contact our support team at <a href="mailto:support@rollcallfrs.com">support@rollcallfrs.com</a>.</p>
  </div>
  <footer style="background-color:#e9ecef; color:#333; text-align:center; padding:12px; font-size:0.95em;">
    &copy; {year} RollCall FRS. All rights reserved.
  </footer>
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
