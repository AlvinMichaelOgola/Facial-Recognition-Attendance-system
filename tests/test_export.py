import unittest
from lec_main import export_attendance_to_pdf, export_attendance_to_csv

class TestExportFeatures(unittest.TestCase):
    def test_export_csv(self):
        result = export_attendance_to_csv('data/test_attendance.csv')
        self.assertTrue(result)

    def test_export_pdf(self):
        result = export_attendance_to_pdf('data/test_attendance.csv', 'data/test_attendance.pdf')
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()
