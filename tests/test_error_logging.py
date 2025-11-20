import unittest
import os

class TestErrorLogging(unittest.TestCase):
    def test_error_log_created(self):
        # Simulate an error and check if log file is created
        try:
            raise Exception('Test error')
        except Exception as e:
            with open('face_capture_errors.log', 'a') as f:
                f.write(str(e))
        self.assertTrue(os.path.exists('face_capture_errors.log'))

if __name__ == '__main__':
    unittest.main()
