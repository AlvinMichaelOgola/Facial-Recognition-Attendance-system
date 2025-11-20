import unittest
from flask import Flask
from main import app

class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_get_classes(self):
        response = self.client.get('/api/classes')
        self.assertEqual(response.status_code, 200)

    def test_attendance_post(self):
        response = self.client.post('/api/attendance', json={'student_id': 1, 'class_id': 1})
        self.assertIn(response.status_code, [200, 201, 400])

if __name__ == '__main__':
    unittest.main()
