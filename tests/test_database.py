import unittest
from user_data_manager import UserDataManager

class TestDatabaseOperations(unittest.TestCase):
    def setUp(self):
        self.db = UserDataManager(':memory:')

    def test_add_user(self):
        user_id = self.db.add_user('Test User', 'test@example.com', 'student')
        self.assertIsNotNone(user_id)

    def test_get_user(self):
        user_id = self.db.add_user('Test User', 'test@example.com', 'student')
        user = self.db.get_user(user_id)
        self.assertEqual(user['name'], 'Test User')

if __name__ == '__main__':
    unittest.main()
