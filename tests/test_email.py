import unittest
from email_utils import send_email

class TestEmailSystem(unittest.TestCase):
    def test_send_email(self):
        # This test should mock SMTP in real use
        result = send_email('test@example.com', 'Test Subject', 'Test Body')
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()
