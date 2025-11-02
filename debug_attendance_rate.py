import mysql.connector
import os

def get_db_connection():
    db_config = {
        'host': 'localhost',
        'user': 'root',
        'password': '',  # Set your MySQL root password if any
        'database': 'frs_v3.1'  # Set your database name
    }
    return mysql.connector.connect(**db_config)

def debug_attendance_rate(lecturer_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    print(f"Lecturer ID: {lecturer_id}")
    cursor.execute('''
        SELECT s.id as session_id, s.class_id
        FROM attendance_sessions_two s
        WHERE s.lecturer_id = %s
    ''', (lecturer_id,))
    sessions = cursor.fetchall()
    print(f"Sessions for lecturer: {sessions}")
    session_ids = [str(row[0]) for row in sessions]
    if not session_ids:
        print("No sessions found for this lecturer.")
        return
    session_ids_str = ','.join(session_ids)
    cursor.execute(f'''
        SELECT ar.session_id, ar.student_id, ar.confidence
        FROM attendance_records_two ar
        WHERE ar.session_id IN ({session_ids_str})
    ''')
    records = cursor.fetchall()
    print(f"Attendance records: {records}")
    present_count = sum(1 for r in records if r[2] and float(r[2]) != 0)
    total_count = len(records)
    print(f"Present count: {present_count}")
    print(f"Total count: {total_count}")
    if total_count > 0:
        attendance_rate = (present_count / total_count) * 100
    else:
        attendance_rate = 0
    print(f"Attendance rate: {attendance_rate:.2f}%")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python debug_attendance_rate.py <lecturer_id>")
    else:
        debug_attendance_rate(sys.argv[1])
