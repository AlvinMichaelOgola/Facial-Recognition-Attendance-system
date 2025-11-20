from email_utils import send_email

if __name__ == "__main__":
    # Change this to your test email address
    test_email = "tevin.mdendu@strathmore.edu"
    subject = "Test Email from Attendance System"
    body = "<h2>This is a test email from the Attendance System backend.</h2><p>If you received this, SMTP is working!" 
    try:
        send_email(test_email, subject, body, html=True)
        print(f"Test email sent to {test_email}")
    except Exception as e:
        print(f"Failed to send test email: {e}")
