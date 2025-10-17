import base64
from flask import send_file, make_response
from io import BytesIO
from PIL import Image
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

# Upload student profile photo (BLOB)
@app.route('/api/student/profile_photo', methods=['POST'])
def upload_profile_photo():
    student_id = request.form.get('student_id')
    if student_id is not None:
        student_id = str(student_id).strip()
    if not student_id or 'photo' not in request.files:
        return jsonify({'error': 'student_id and photo file required'}), 400
    photo_file = request.files['photo']
    # Optimize image: resize and compress
    try:
        # Check if student exists
        student = udm.get_student(student_id)
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        img = Image.open(photo_file)
        img = img.convert('RGB')  # Ensure JPEG compatible
        img.thumbnail((256, 256))  # Resize to max 256x256
        buf = BytesIO()
        img.save(buf, format='JPEG', quality=85)
        photo_bytes = buf.getvalue()
        affected = udm.update_student_profile_photo(student_id, photo_bytes)
        if affected == 0:
            return jsonify({'error': 'No student updated. Check student_id.'}), 404
        return jsonify({'success': True, 'message': 'Profile photo updated'})
    except Exception as e:
        return jsonify({'error': f'Failed to update profile photo: {str(e)}'}), 500

# Get student profile photo (BLOB, returns image or base64)
@app.route('/api/student/profile_photo', methods=['GET'])
def get_profile_photo():
    student_id = request.args.get('student_id')
    if student_id is not None:
        student_id = str(student_id).strip()
    as_base64 = request.args.get('base64', '0') == '1'
    if not student_id:
        return jsonify({'error': 'student_id required'}), 400
    # Check if student exists
    student = udm.get_student(student_id)
    if not student:
        return jsonify({'error': 'Student not found'}), 404
    photo_bytes = udm.get_student_profile_photo(student_id)
    if photo_bytes is None:
        return jsonify({'error': 'No profile photo found'}), 404
    if as_base64:
        encoded = base64.b64encode(photo_bytes).decode('utf-8')
        return jsonify({'photo_base64': encoded})
    # Try to guess mimetype (default to jpeg)
    mimetype = 'image/jpeg'
    if photo_bytes[:4] == b'\x89PNG':
        mimetype = 'image/png'
    elif photo_bytes[:2] == b'\xff\xd8':
        mimetype = 'image/jpeg'
    elif photo_bytes[:6] == b'GIF89a' or photo_bytes[:6] == b'GIF87a':
        mimetype = 'image/gif'
    response = make_response(photo_bytes)
    response.headers.set('Content-Type', mimetype)
    return response

@app.route('/api/student/profile', methods=['GET'])
def get_profile():
    student_id = request.args.get('student_id')
    if not student_id:
        return jsonify({'error': 'student_id required'}), 400
    profile = udm.get_student(student_id)
    if not profile:
        return jsonify({'error': 'Student not found'}), 404
    # Add profile_photo_url to the profile dict
    profile_photo_url = f"/api/student/profile_photo?student_id={student_id}"
    profile['profile_photo_url'] = profile_photo_url
    return jsonify(profile)


# Update student profile info
@app.route('/api/student/profile', methods=['POST'])
def update_profile():
    data = request.get_json()
    student_id = data.get('student_id')
    if not student_id:
        return jsonify({'error': 'student_id required'}), 400

    # Only allow updating certain fields
    allowed_user_fields = ['email', 'phone']
    user_updates = {k: v for k, v in data.items() if k in allowed_user_fields and v is not None}
    # You can add more allowed fields as needed
    if not user_updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    try:
        udm.update_user(student_id, user_updates, {})
        return jsonify({'success': True, 'message': 'Profile updated successfully'})
    except Exception as e:
        return jsonify({'error': f'Failed to update profile: {str(e)}'}), 500

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

@app.route('/api/student/change_password', methods=['POST'])
def change_student_password():
    data = request.get_json()
    student_id = data.get('student_id')
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    if not student_id or not current_password or not new_password:
        return jsonify({'error': 'student_id, current_password, and new_password are required'}), 400

    # Get user info
    student = udm.get_student(student_id)
    if not student:
        return jsonify({'error': 'Student not found'}), 404

    # Get user row (for password)
    user = udm.get_user_by_id(student['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404

    from user_data_manager import verify_password
    if not verify_password(current_password, user.get('password')):
        return jsonify({'error': 'Current password is incorrect'}), 401

    # Update password
    try:
        udm.update_user(student_id, {'password': new_password}, {})
        # Send email notification
        try:
            from email_utils import send_email
            subject = "Your Attendance System password was changed"
            body = f"""
            <html><body>
            <h2>Password Changed</h2>
            <p>Hello {user.get('first_name', '')},</p>
            <p>Your account password was changed on the Attendance System. If you did not perform this action, please contact support immediately.</p>
            <br><p>Best regards,<br>Attendance System Team</p>
            </body></html>
            """
            send_email(user['email'], subject, body, html=True)
        except Exception as e:
            print(f"[WARN] Failed to send password change email: {e}")
        return jsonify({'success': True, 'message': 'Password updated successfully'})
    except Exception as e:
        return jsonify({'error': f'Failed to update password: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
