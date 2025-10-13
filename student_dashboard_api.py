"""
student_dashboard_api.py

Flask API for student dashboard endpoints.
Connects frontend dashboard to the database using UserDataManager.
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from user_data_manager import UserDataManager
import os


app = Flask(__name__)
CORS(app)
udm = UserDataManager()

@app.route('/api/student/profile', methods=['GET'])
def get_profile():
    student_id = request.args.get('student_id')
    if not student_id:
        return jsonify({'error': 'student_id required'}), 400
    profile = udm.get_student(student_id)
    if not profile:
        return jsonify({'error': 'Student not found'}), 404
    return jsonify(profile)

@app.route('/api/student/attendance/records', methods=['GET'])
def get_attendance_records():
    student_id = request.args.get('student_id')
    if not student_id:
        return jsonify({'error': 'student_id required'}), 400
    records = udm.db_manager.get_attendance_records_for_student(student_id)
    return jsonify(records)

@app.route('/api/student/attendance/download', methods=['GET'])
def download_attendance_csv():
    student_id = request.args.get('student_id')
    if not student_id:
        return jsonify({'error': 'student_id required'}), 400
    file_path = f'tmp/{student_id}_attendance.csv'
    os.makedirs('tmp', exist_ok=True)
    udm.download_attendance_csv(student_id, file_path)
    return send_file(file_path, as_attachment=True)


# Login endpoint for student authentication
@app.route('/api/student/login', methods=['POST'])
def student_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    user = udm.verify_credentials(email, password)
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
    # Get student info
    student = udm.get_student_by_email(email)
    if not student:
        return jsonify({'error': 'No student record found for this user'}), 404
    # Return minimal info needed for frontend
    return jsonify({
        'studentId': student['student_id'],
        'studentName': f"{student['first_name']} {student['last_name']}",
        'email': student['email'],
    })

if __name__ == '__main__':
    app.run(debug=True)
