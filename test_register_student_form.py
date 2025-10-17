import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk

from gui import Application  # Adjust import if needed

class TestRegisterStudentForm(unittest.TestCase):
    def setUp(self):
        # Set up a root window and the Application
        self.root = tk.Tk()
        self.app = Application()
        self.app.show_add_student()
        self.form = self.app

    def tearDown(self):
        self.root.destroy()

    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showerror")
    def test_register_student_success(self, mock_showerror, mock_showinfo):
        # Fill in required fields as per the form
        self.form.add_vars["first_name"].set("Test")
        self.form.add_vars["last_name"].set("Student")
        self.form.add_vars["other_names"].set("Middle")
        self.form.add_vars["email"].set("test@student.com")
        self.form.add_vars["phone"].set("712345678")
        self.form.add_vars["country_code"].set("+254")
        self.form.add_vars["course"].set("Bachelor of Commerce (BCOM)")
        self.form.add_vars["year_of_study"].set("2")

        # Mock user_manager.add_user to simulate DB insert
        self.form.user_manager = MagicMock()
        self.form.user_manager.add_user.return_value = "S12345"

        # Call registration
        self.form.register_student()

        # Check that showinfo was called (success)
        mock_showinfo.assert_called()
        mock_showerror.assert_not_called()
        # Check that phone is formatted correctly in the user_dict
        user_dict_arg = self.form.user_manager.add_user.call_args[0][0]
        self.assertTrue(user_dict_arg["phone"].startswith("+254"))

    @patch("tkinter.messagebox.showerror")
    def test_register_student_missing_fields(self, mock_showerror):
        # Leave required fields empty
        self.form.add_vars["first_name"].set("")
        self.form.add_vars["last_name"].set("")
        self.form.add_vars["email"].set("")
        self.form.add_vars["course"].set("")
        self.form.add_vars["year_of_study"].set("")

        self.form.register_student()
        mock_showerror.assert_called()

if __name__ == "__main__":
    unittest.main()
