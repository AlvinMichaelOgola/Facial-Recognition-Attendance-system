from flask import Flask, request, jsonify, send_file, session
from flask_cors import CORS
import mysql.connector
import hashlib
import os
import csv

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'change_this_secret_key')
# DEVELOPMENT ONLY: Allow all origins for CORS
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# --- Student Roster for a Class ---
@app.route('/api/lecturer/class/<int:class_id>/students', methods=['GET'])
def get_class_student_roster(class_id):
	try:
		conn = get_db_connection()
		cursor = conn.cursor(dictionary=True)
		cursor.execute('''
			SELECT s.student_id, u.first_name, u.last_name, u.email
			FROM class_students_two cs
			JOIN students s ON cs.student_id = s.student_id
			JOIN users u ON s.user_id = u.id
			WHERE cs.class_id = %s
		''', (class_id,))
		students = [
			{
				'id': row['student_id'],
				'name': f"{row['first_name']} {row['last_name']}",
				'email': row['email']
			}
			for row in cursor.fetchall()
		]
		cursor.close()
		conn.close()
		return jsonify(students)
	except Exception as e:
		return jsonify({'error': f'Failed to fetch student roster: {str(e)}'}), 500

# --- Top 5 Most Absent Students for a Class ---
@app.route('/api/lecturer/class/<int:class_id>/top_absent', methods=['GET'])
def get_class_top_absent_students(class_id):
	try:
		conn = get_db_connection()
		cursor = conn.cursor(dictionary=True)
		# Get all students in the class
		cursor.execute('''
			SELECT s.student_id, u.first_name, u.last_name
			FROM class_students_two cs
			JOIN students s ON cs.student_id = s.student_id
			JOIN users u ON s.user_id = u.id
			WHERE cs.class_id = %s
		''', (class_id,))
		students = {row['student_id']: f"{row['first_name']} {row['last_name']}" for row in cursor.fetchall()}

		# Count absences for each student in this class (confidence = 0 means absent)
		cursor.execute('''
			SELECT ar.student_id, COUNT(*) as absences
			FROM attendance_records_two ar
			JOIN attendance_sessions_two sess ON ar.session_id = sess.id
			WHERE sess.class_id = %s AND ar.confidence = 0
			GROUP BY ar.student_id
			ORDER BY absences DESC
			LIMIT 5
		''', (class_id,))
		top_absent = []
		for row in cursor.fetchall():
			name = students.get(row['student_id'], row['student_id'])
			top_absent.append({
				'name': name,
				'absences': row['absences']
			})
		cursor.close()
		conn.close()
		return jsonify(top_absent)
	except Exception as e:
		return jsonify({'error': f'Failed to fetch top absent students: {str(e)}'}), 500
from flask import Flask, request, jsonify, send_file, session
from flask_cors import CORS
import mysql.connector
import hashlib
import os
import csv

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'change_this_secret_key')
# DEVELOPMENT ONLY: Allow all origins for CORS
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
# To allow more origins, add them to the list above. For production, set to your deployed frontend URL.


# --- Lecturer Classes List (for dashboard) ---
@app.route('/api/lecturer/classes/list', methods=['GET'])
def get_lecturer_classes_list():
	lecturer_id = request.args.get('lecturer_id')
	print(f"[DEBUG] /api/lecturer/classes/list called with lecturer_id={lecturer_id}")
	if not lecturer_id:
		print("[DEBUG] lecturer_id missing in request")
		return jsonify({'error': 'lecturer_id required'}), 400
	try:
		conn = get_db_connection()
		cursor = conn.cursor(dictionary=True)
		# Get all classes for this lecturer
		cursor.execute("""
			SELECT c.id, c.code, c.class_name, c.start_time, c.end_time, c.room, c.date
			FROM classes_two c
			WHERE c.lecturer_id = %s
		""", (lecturer_id,))
		classes = cursor.fetchall()
		print(f"[DEBUG] Classes fetched: {classes}")
		# For each class, get student count
		for cls in classes:
			cursor.execute("SELECT COUNT(*) as student_count FROM class_students_two WHERE class_id = %s", (cls['id'],))
			cls['student_count'] = cursor.fetchone()['student_count']
			# Optionally, add attendance rate if you want (set to None for now)
			cls['attendance_rate'] = None
		print(f"[DEBUG] Classes with student counts: {classes}")
		# Convert non-serializable fields
		for cls in classes:
			# Convert start_time and end_time (timedelta) to HH:MM
			for key in ["start_time", "end_time"]:
				val = cls.get(key)
				if val is not None:
					# val is timedelta, convert to HH:MM
					total_seconds = int(val.total_seconds())
					hours = total_seconds // 3600
					minutes = (total_seconds % 3600) // 60
					cls[key] = f"{hours:02d}:{minutes:02d}"
			# Convert date to YYYY-MM-DD
			if cls.get("date") is not None:
				cls["date"] = str(cls["date"])
		cursor.close()
		conn.close()
		return jsonify(classes)
	except Exception as e:
		print(f"[DEBUG] Exception in get_lecturer_classes_list: {e}")
		return jsonify({'error': f'Failed to fetch classes list: {str(e)}'}), 500


db_config = {
	'host': 'localhost',
	'user': 'root',
	'password': '',  # Set your MySQL root password if any
	'database': 'frs_v3.1'  # Set your database name
}

def get_db_connection():
	return mysql.connector.connect(**db_config)

# Lecturer logout endpoint
@app.route('/api/lecturer/logout', methods=['POST'])
def lecturer_logout():
    # If using server-side sessions, clear session here
    # session.clear()  # Uncomment if using Flask sessions
    return jsonify({'success': True, 'message': 'Logged out successfully.'})

# --- Lecturer Profile ---
@app.route('/api/lecturer/profile', methods=['GET'])
def get_lecturer_profile():
    lecturer_id = request.args.get('lecturer_id')
    if not lecturer_id:
        return jsonify({'error': 'lecturer_id required'}), 400
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT lecturer_id, first_name, last_name, other_name, email, phone, department, academic_rank, hire_date, office_location, specialization, active, last_login FROM lecturers_table_two WHERE lecturer_id = %s", (lecturer_id,))
        profile = cursor.fetchone()
        cursor.close()
        conn.close()
        if not profile:
            return jsonify({'error': 'Lecturer not found'}), 404
        return jsonify(profile)
    except Exception as e:
        return jsonify({'error': f'Failed to fetch profile: {str(e)}'}), 500

@app.route('/api/lecturer/profile', methods=['POST'])
def update_lecturer_profile():
	data = request.get_json()
	lecturer_id = data.get('lecturer_id')
	if not lecturer_id:
		return jsonify({'error': 'lecturer_id required'}), 400
	allowed_fields = ['email', 'phone', 'office_location', 'specialization']
	updates = {k: v for k, v in data.items() if k in allowed_fields and v is not None}
	if not updates:
		return jsonify({'error': 'No valid fields to update'}), 400
	try:
		conn = get_db_connection()
		cursor = conn.cursor()
		set_clause = ', '.join([f"{k}=%s" for k in updates.keys()])
		values = list(updates.values()) + [lecturer_id]
		cursor.execute(f"UPDATE lecturers_table_two SET {set_clause} WHERE lecturer_id = %s", values)
		conn.commit()
		cursor.close()
		conn.close()
		return jsonify({'success': True, 'message': 'Profile updated successfully'})
	except Exception as e:
		return jsonify({'error': f'Failed to update profile: {str(e)}'}), 500

# --- Lecturer Classes ---
@app.route('/api/lecturer/classes', methods=['GET'])
def get_lecturer_classes():
	lecturer_id = request.args.get('lecturer_id')
	if not lecturer_id:
		return jsonify({'error': 'lecturer_id required'}), 400
	try:
		conn = get_db_connection()
		cursor = conn.cursor()
		# Use classes_two and return only the count
		cursor.execute("SELECT COUNT(*) FROM classes_two WHERE lecturer_id = %s", (lecturer_id,))
		result = cursor.fetchone()
		cursor.close()
		conn.close()
		return jsonify({'total_classes': result[0] if result else 0})
	except Exception as e:
		return jsonify({'error': f'Failed to fetch classes: {str(e)}'}), 500

# --- Class Details & Analytics ---
@app.route('/api/lecturer/class/<int:class_id>', methods=['GET'])
def get_class_details(class_id):
	try:
		conn = get_db_connection()
		cursor = conn.cursor(dictionary=True)
		# Get class info (try classes_two first, fallback to classes)
		cursor.execute("SELECT * FROM classes_two WHERE id = %s", (class_id,))
		class_info = cursor.fetchone()
		if not class_info:
			cursor.execute("SELECT * FROM classes WHERE class_id = %s", (class_id,))
			class_info = cursor.fetchone()
			if not class_info:
				cursor.close()
				conn.close()
				return jsonify({'error': 'Class not found'}), 404

		# Student count
		cursor.execute("SELECT COUNT(*) as student_count FROM class_students_two WHERE class_id = %s", (class_id,))
		student_count = cursor.fetchone()['student_count']

		# Session count
		cursor.execute("SELECT COUNT(*) as session_count FROM attendance_sessions_two WHERE class_id = %s", (class_id,))
		session_count = cursor.fetchone()['session_count']

		# Attendance rate (present/total)
		cursor.execute("SELECT id FROM attendance_sessions_two WHERE class_id = %s", (class_id,))
		session_ids = [row['id'] for row in cursor.fetchall()]
		attendance_rate = 0.0
		present = 0
		total = 0
		if session_ids:
			format_strings = ','.join(['%s'] * len(session_ids))
			cursor.execute(f"SELECT COUNT(*) as total FROM attendance_records_two WHERE session_id IN ({format_strings})", tuple(session_ids))
			total = cursor.fetchone()['total']
			cursor.execute(f"SELECT COUNT(*) as present FROM attendance_records_two WHERE session_id IN ({format_strings}) AND present_at IS NOT NULL AND present_at != ''", tuple(session_ids))
			present = cursor.fetchone()['present']
			attendance_rate = (present / total * 100) if total > 0 else 0.0

		# Compose response
		result = {
			'id': class_info.get('id') or class_info.get('class_id'),
			'code': class_info.get('code') or class_info.get('class_code'),
			'title': class_info.get('class_name') or class_info.get('title'),
			'room': class_info.get('room'),
			'date': str(class_info.get('date')) if class_info.get('date') else None,
			'start_time': str(class_info.get('start_time')) if class_info.get('start_time') else None,
			'end_time': str(class_info.get('end_time')) if class_info.get('end_time') else None,
			'student_count': student_count,
			'session_count': session_count,
			'attendance_rate': round(attendance_rate, 2),
			'present': present,
			'total': total
		}
		cursor.close()
		conn.close()
		return jsonify(result)
	except Exception as e:
		return jsonify({'error': f'Failed to fetch class details: {str(e)}'}), 500

# --- Attendance Records & Corrections ---
@app.route('/api/lecturer/attendance/records', methods=['GET'])
def get_attendance_records():
	lecturer_id = request.args.get('lecturer_id')
	if not lecturer_id:
		return jsonify({'error': 'lecturer_id required'}), 400
	try:
		conn = get_db_connection()
		cursor = conn.cursor(dictionary=True)
		# Adjust table/field names as needed
		cursor.execute("SELECT * FROM attendance WHERE lecturer_id = %s", (lecturer_id,))
		records = cursor.fetchall()
		cursor.close()
		conn.close()
		return jsonify(records)
	except Exception as e:
		return jsonify({'error': f'Failed to fetch attendance records: {str(e)}'}), 500

@app.route('/api/lecturer/attendance/corrections', methods=['POST'])
def submit_attendance_corrections():
	data = request.get_json()
	corrections = data.get('corrections')
	if not corrections:
		return jsonify({'error': 'No corrections provided'}), 400
	try:
		conn = get_db_connection()
		cursor = conn.cursor()
		# Example: corrections = [{attendance_id, new_status}, ...]
		for corr in corrections:
			cursor.execute("UPDATE attendance SET status = %s WHERE attendance_id = %s", (corr['new_status'], corr['attendance_id']))
		conn.commit()
		cursor.close()
		conn.close()
		return jsonify({'success': True, 'message': 'Corrections saved'})
	except Exception as e:
		return jsonify({'error': f'Failed to save corrections: {str(e)}'}), 500

@app.route('/api/lecturer/attendance/download', methods=['GET'])
def download_attendance_csv():
	lecturer_id = request.args.get('lecturer_id')
	if not lecturer_id:
		return jsonify({'error': 'lecturer_id required'}), 400
	try:
		import csv
		from flask import send_file
		conn = get_db_connection()
		cursor = conn.cursor(dictionary=True)
		cursor.execute("SELECT * FROM attendance WHERE lecturer_id = %s", (lecturer_id,))
		records = cursor.fetchall()
		cursor.close()
		conn.close()
		file_path = f'tmp/{lecturer_id}_attendance.csv'
		import os
		os.makedirs('tmp', exist_ok=True)
		with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
			writer = csv.DictWriter(csvfile, fieldnames=records[0].keys() if records else [])
			writer.writeheader()
			writer.writerows(records)
		return send_file(file_path, as_attachment=True)
	except Exception as e:
		return jsonify({'error': f'Failed to download CSV: {str(e)}'}), 500

# --- Students ---
@app.route('/api/lecturer/students', methods=['GET'])
def get_lecturer_students():
	lecturer_id = request.args.get('lecturer_id')
	print(f"[DEBUG] /api/lecturer/students called with lecturer_id={lecturer_id}")
	if not lecturer_id:
		print("[DEBUG] lecturer_id missing in request")
		return jsonify({'error': 'lecturer_id required'}), 400
	try:
		conn = get_db_connection()
		cursor = conn.cursor()
		# Get count of unique students for this lecturer
		cursor.execute("""
			SELECT COUNT(DISTINCT cs.student_id) AS total_students
			FROM class_students_two cs
			JOIN classes_two c ON cs.class_id = c.id
			WHERE c.lecturer_id = %s
		""", (lecturer_id,))
		result = cursor.fetchone()
		print(f"[DEBUG] Total students found: {result[0] if result else 0}")
		cursor.close()
		conn.close()
		return jsonify({'total_students': result[0] if result else 0})
	except Exception as e:
		print(f"[DEBUG] Exception in get_lecturer_students: {e}")
		return jsonify({'error': f'Failed to fetch students: {str(e)}'}), 500

# --- Students List for Lecturer ---
@app.route('/api/lecturer/students/list', methods=['GET'])
def get_lecturer_students_list():
	lecturer_id = request.args.get('lecturer_id')
	print(f"[DEBUG] /api/lecturer/students/list called with lecturer_id={lecturer_id}")
	if not lecturer_id:
		print("[DEBUG] lecturer_id missing in request")
		return jsonify({'error': 'lecturer_id required'}), 400
	try:
		conn = get_db_connection()
		cursor = conn.cursor(dictionary=True)
		# Get students assigned to lecturer's classes, joining through students and users
		cursor.execute("""
			SELECT cs.student_id, u.first_name, u.last_name, u.email, c.class_name
			FROM class_students_two cs
			JOIN students s ON cs.student_id = s.student_id
			JOIN users u ON s.user_id = u.id
			JOIN classes_two c ON cs.class_id = c.id
			WHERE c.lecturer_id = %s
		""", (lecturer_id,))
		rows = cursor.fetchall()
		print(f"[DEBUG] Number of student rows fetched: {len(rows)}")
		# Aggregate classes for each student
		students = {}
		for row in rows:
			sid = row['student_id']
			if sid not in students:
				students[sid] = {
					'student_id': sid,
					'full_name': f"{row['first_name']} {row['last_name']}",
					'email': row['email'],
					'enrolled_classes': []
				}
			students[sid]['enrolled_classes'].append(row['class_name'])
		print(f"[DEBUG] Number of unique students aggregated: {len(students)}")
		cursor.close()
		conn.close()
		return jsonify(list(students.values()))
	except Exception as e:
		print(f"[DEBUG] Exception in get_lecturer_students_list: {e}")
		return jsonify({'error': f'Failed to fetch students list: {str(e)}'}), 500

# --- Notifications ---
@app.route('/api/lecturer/notifications', methods=['POST'])
def send_announcement():
	data = request.get_json()
	class_ids = data.get('class_ids')
	subject = data.get('subject')
	message = data.get('message')
	if not class_ids or not subject or not message:
		return jsonify({'error': 'class_ids, subject, and message required'}), 400
	# Implement your email/notification logic here
	# For now, just return success
	return jsonify({'success': True, 'message': 'Announcement sent (mock)'})


# --- Attendance Rate ---
@app.route('/api/lecturer/attendance_rate', methods=['GET'])
def get_attendance_rate():
	lecturer_id = request.args.get('lecturer_id')
	if not lecturer_id:
		return jsonify({'error': 'lecturer_id required'}), 400
	try:
		conn = get_db_connection()
		cursor = conn.cursor()
		# 1. Get all session IDs for this lecturer
		cursor.execute("SELECT id FROM attendance_sessions_two WHERE lecturer_id = %s", (lecturer_id,))
		session_ids = [row[0] for row in cursor.fetchall()]
		if not session_ids:
			cursor.close()
			conn.close()
			return jsonify({'attendance_rate': 0.0, 'present': 0, 'total': 0})
		# 2. Count all attendance records for these sessions
		format_strings = ','.join(['%s'] * len(session_ids))
		cursor.execute(f"SELECT COUNT(*) FROM attendance_records_two WHERE session_id IN ({format_strings})", tuple(session_ids))
		total_records = cursor.fetchone()[0]
		# 3. Count present records (present_at is not null and present_at != '')
		cursor.execute(f"SELECT COUNT(*) FROM attendance_records_two WHERE session_id IN ({format_strings}) AND present_at IS NOT NULL AND present_at != ''", tuple(session_ids))
		present_records = cursor.fetchone()[0]
		cursor.close()
		conn.close()
		attendance_rate = (present_records / total_records * 100) if total_records > 0 else 0.0
		return jsonify({'attendance_rate': round(attendance_rate, 2), 'present': present_records, 'total': total_records})
	except Exception as e:
		return jsonify({'error': f'Failed to calculate attendance rate: {str(e)}'}), 500



@app.route('/api/lecturer/login', methods=['POST'])
def lecturer_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    try:
        print(f"[DEBUG] Login attempt: email={email}, password={password}")
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM lecturers_table_two WHERE email = %s LIMIT 1"
        cursor.execute(query, (email,))
        lecturer = cursor.fetchone()
        print(f"[DEBUG] DB result: {lecturer}")
        cursor.close()
        conn.close()
        if not lecturer:
            print("[DEBUG] No lecturer found with that email.")
            return jsonify({'error': 'Invalid credentials'}), 401
        PWD_SALT = os.environ.get("FRS_PWD_SALT", "change_this_default_salt")
        salted = password + PWD_SALT
        hashed_input = hashlib.sha256(salted.encode("utf-8")).hexdigest()
        print(f"[DEBUG] Comparing passwords: input_hash={hashed_input} db={lecturer['password']}")
        if hashed_input != lecturer['password']:
            print("[DEBUG] Password mismatch.")
            return jsonify({'error': 'Invalid credentials'}), 401
        # Remove password from response
        lecturer.pop('password', None)
        # Store lecturer_id in session
        session['lecturer_id'] = lecturer.get('lecturer_id')
        print(f"[DEBUG] Login successful for lecturer_id={lecturer.get('lecturer_id')}")
        return jsonify(lecturer)
    except Exception as e:
        print(f"[ERROR] Login failed: {e}")
        return jsonify({'error': f'Login failed: {str(e)}'}), 500

# --- Change Password ---
@app.route('/api/lecturer/change_password', methods=['POST'])
def change_lecturer_password():
    lecturer_id = session.get('lecturer_id')
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    print(f"[DEBUG] Session lecturer_id={lecturer_id}, current_password={current_password}, new_password={new_password}")
    if not lecturer_id or not current_password or not new_password:
        print("[DEBUG] Missing required fields or not logged in.")
        return jsonify({'error': 'Not logged in or missing fields.'}), 400
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM lecturers_table_two WHERE lecturer_id = %s", (lecturer_id,))
        lecturer = cursor.fetchone()
        print(f"[DEBUG] DB lecturer row: {lecturer}")
        if not lecturer:
            cursor.close()
            conn.close()
            print("[DEBUG] Lecturer not found.")
            return jsonify({'error': 'Lecturer not found'}), 404
        PWD_SALT = os.environ.get("FRS_PWD_SALT", "change_this_default_salt")
        salted = current_password + PWD_SALT
        hashed_input = hashlib.sha256(salted.encode("utf-8")).hexdigest()
        print(f"[DEBUG] Hashed input: {hashed_input}, DB password: {lecturer['password']}")
        if hashed_input != lecturer['password']:
            cursor.close()
            conn.close()
            print("[DEBUG] Current password is incorrect.")
            return jsonify({'error': 'Current password is incorrect'}), 401
        salted_new = new_password + PWD_SALT
        hashed_new = hashlib.sha256(salted_new.encode("utf-8")).hexdigest()
        print(f"[DEBUG] Updating password to: {hashed_new}")
        cursor.execute("UPDATE lecturers_table_two SET password = %s WHERE lecturer_id = %s", (hashed_new, lecturer_id))
        print(f"[DEBUG] Update executed, rowcount: {cursor.rowcount}")
        conn.commit()
        print("[DEBUG] Password updated and committed.")
        cursor.execute("SELECT password FROM lecturers_table_two WHERE lecturer_id = %s", (lecturer_id,))
        updated = cursor.fetchone()
        print(f"[DEBUG] Password in DB after update: {updated}")
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Password updated successfully.'})
    except Exception as e:
        print(f"[ERROR] Failed to change password: {e}")
        return jsonify({'error': f'Failed to change password: {str(e)}'}), 500

# --- Attendance by Class ---
@app.route('/api/lecturer/attendance_by_class', methods=['GET'])
def get_attendance_by_class():
    lecturer_id = request.args.get('lecturer_id')
    print(f"[DEBUG] attendance_by_class: lecturer_id={lecturer_id}")
    if not lecturer_id:
        print("[DEBUG] No lecturer_id provided")
        return jsonify({'error': 'lecturer_id required'}), 400
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Get all classes for this lecturer
        cursor.execute("SELECT id, class_name FROM classes_two WHERE lecturer_id = %s", (lecturer_id,))
        classes = cursor.fetchall()
        print(f"[DEBUG] Found {len(classes)} classes for lecturer {lecturer_id}: {classes}")
        result = []
        for cls in classes:
            class_id = cls['id']
            class_name = cls['class_name']
            cursor.execute("SELECT id FROM attendance_sessions_two WHERE class_id = %s", (class_id,))
            session_ids = [row['id'] for row in cursor.fetchall()]
            print(f"[DEBUG] Class '{class_name}' (id={class_id}) has session_ids: {session_ids}")
            if not session_ids:
                result.append({'name': class_name, 'present': 0, 'absent': 0})
                continue
            format_strings = ','.join(['%s'] * len(session_ids))
            cursor.execute(f"SELECT COUNT(*) as present FROM attendance_records_two WHERE session_id IN ({format_strings}) AND present_at IS NOT NULL AND present_at != ''", tuple(session_ids))
            present = cursor.fetchone()['present']
            cursor.execute(f"SELECT COUNT(*) as total FROM attendance_records_two WHERE session_id IN ({format_strings})", tuple(session_ids))
            total = cursor.fetchone()['total']
            absent = max(0, total - present)
            print(f"[DEBUG] Class '{class_name}': present={present}, total={total}, absent={absent}")
            result.append({'name': class_name, 'present': present, 'absent': absent})
        cursor.close()
        conn.close()
        print(f"[DEBUG] Final attendance by class result: {result}")
        return jsonify(result)
    except Exception as e:
        print(f"[ERROR] Failed to fetch attendance by class: {e}")
        return jsonify({'error': f'Failed to fetch attendance by class: {str(e)}'}), 500

if __name__ == '__main__':
	app.run(debug=True, port=5001)
