# rec_faces.py
import os
import time
import datetime
import threading
import logging
import psutil
import cv2

from embedding_loader import EmbeddingLoader
from user_data_manager import UserDataManager
from face_recognizer import FaceRecognizer

# ---------------- Config ----------------
MODEL_NAME = 'Facenet'
SIMILARITY_THRESHOLD = 0.9
STABLE_FRAMES = 10
DATA_DIR = "face_embeddings"
embeddings_path = os.path.join(DATA_DIR, "embeddings.pkl")
user_info_path = os.path.join(DATA_DIR, "user_info.csv")
os.makedirs('data', exist_ok=True)

# Logging configuration
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

db_manager = UserDataManager()
loader = EmbeddingLoader(db_manager=db_manager.db_manager)
recognizer = None
all_embeddings = None
all_labels = None

# ---------------- Attendance State ----------------
# session_active will be toggled by GUI start/end calls

session_active = False
marked_names = set()
attendance_buffer = []
BUFFER_SIZE = 5
current_session_id = None

def flush_attendance():
    """
    On session end, write only the current session's attendance records to the CSV with proper columns, overwriting previous content.
    """
    import csv
    global current_session_id
    try:
        records = db_manager.get_attendance_for_session(current_session_id)
        fieldnames = [
            'student_id', 'first_name', 'last_name', 'course', 'present_at', 'confidence'
        ]
        # Fetch session and class info for filename
        session_info = db_manager.get_session_by_id(current_session_id)
        class_info = db_manager.get_class_by_id(session_info['class_id']) if session_info else None
        # Fetch lecturer name
        lecturer_name = "lecturer"
        if session_info and session_info.get('lecturer_id'):
            try:
                lec = db_manager.get_lecturer_by_id(session_info['lecturer_id'])
                if lec:
                    first = lec.get('first_name') or ''
                    last = lec.get('last_name') or ''
                    lecturer_name = f"{first}_{last}".strip('_')
            except Exception:
                pass
        session_name = session_info['name'] if session_info and session_info.get('name') else f'session_{current_session_id}'
        class_name = class_info['class_name'] if class_info and class_info.get('class_name') else 'unknown_class'
        date_str = session_info['started_at'].strftime('%Y-%m-%d') if session_info and session_info.get('started_at') else time.strftime('%Y-%m-%d')
        # Sanitize for filename
        def sanitize(s):
            return ''.join(c for c in str(s) if c.isalnum() or c in ('-_')).rstrip()
        session_name_safe = sanitize(session_name).replace(' ', '_')
        class_name_safe = sanitize(class_name).replace(' ', '_')
        lecturer_name_safe = sanitize(lecturer_name).replace(' ', '_')
        session_csv = os.path.join('data', f'attendance_{date_str}_{lecturer_name_safe}_{class_name_safe}_{current_session_id}.csv')
        with open(session_csv, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            if records and len(records) > 0:
                for rec in records:
                    writer.writerow({
                        'student_id': rec.get('student_id'),
                        'first_name': rec.get('first_name'),
                        'last_name': rec.get('last_name'),
                        'course': rec.get('course'),
                        'present_at': rec.get('present_at'),
                        'confidence': rec.get('confidence'),
                    })
            else:
                # Write a message row if no attendance was recorded
                writer.writerow({k: 'NO ATTENDANCE RECORDED' if k == 'student_id' else '' for k in fieldnames})
        logging.info(f"Wrote {len(records) if records else 0} attendance records for session {current_session_id} to {session_csv}")
    except Exception as e:
        logging.error(f"Failed to write attendance CSV for session {current_session_id}: {e}")

# ---------------- Recognition thread ----------------
# The FaceRecognizer implementation should expose:
# - recognize_faces() -> target for background thread
# - result_lock -> threading.Lock used to synchronize access to recognizer.frame and recognizer.draw_faces
# - draw_faces -> list of (box, identity, similarity, last_seen)
# - frame attribute writable by GUI process_frame
# - stop_threads flag to ask thread to stop


# ---------------- Public API (for GUI) ----------------
def start_session(session_id=None, student_ids=None):
    """
    Called from GUI when session begins. Resets marks and sets session active.
    If student_ids is provided, reload embeddings for only those students.
    """
    global session_active, marked_names, all_embeddings, all_labels, recognizer, recognition_thread, current_session_id
    session_active = True
    marked_names = set()
    current_session_id = session_id
    # Always reload embeddings for the session (required for recognizer init)
    if student_ids is not None:
        all_embeddings, all_labels = loader.load_embeddings(from_db=True, student_ids=student_ids)
    else:
        all_embeddings, all_labels = loader.load_embeddings(from_db=True)
    # (Re)create recognizer with correct args
    recognizer = FaceRecognizer(MODEL_NAME, all_embeddings, all_labels, similarity_threshold=SIMILARITY_THRESHOLD, stable_frames=STABLE_FRAMES)
    recognition_thread = threading.Thread(target=recognizer.recognize_faces, daemon=True)
    recognition_thread.start()
    logging.info(f"rec_faces: session started (session_id={session_id}) with {len(all_embeddings)} embeddings for students: {set(all_labels)}")

def end_session():
    """
    Called from GUI when session ends. Flushes buffer and disables marking.
    """
    global session_active
    session_active = False
    flush_attendance()
    cleanup()
    logging.info("rec_faces: session ended, buffer flushed, and recognition thread stopped")

def process_frame(frame):
    """
    Integration point for GUI:
    - Accepts a BGR OpenCV frame (numpy array)
    - Sends the frame copy to the recognizer via recognizer.frame (protected by result_lock)
    - Reads recognizer.draw_faces (protected by result_lock) and draws boxes/labels on the provided frame
    - Performs attendance marking (buffered) and returns any newly marked identities
    Returns:
        processed_frame (BGR image with overlays), recognized_names (list of identities that were newly marked)
    """
    global marked_names, attendance_buffer
    recognized_names = []

    # Update shared frame for recognition (non-blocking if recognizer not ready)
    try:
        with recognizer.result_lock:
            recognizer.frame = frame.copy()
    except Exception:
        # recognizer may not be fully initialized; ignore
        pass

    # Copy draw_faces snapshot
    try:
        with recognizer.result_lock:
            draw_snapshot = list(recognizer.draw_faces)
    except Exception:
        draw_snapshot = []

    # Iterate detections and draw
    for detection in draw_snapshot:
        try:
            box, identity, similarity, last_seen = detection
            # box expected to be (x, y, w, h)
            x, y, w, h = box
            # Draw rectangle
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            # Draw label
            label_text = f"{identity} {similarity:.2f}"
            cv2.putText(frame, label_text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            # Attendance marking: require session active, not Unknown, not already marked, and high confidence
            if session_active and identity != "Unknown" and identity not in marked_names and similarity >= 0.85:
                try:
                    # Save attendance to DB
                    db_manager.add_attendance_record(current_session_id, identity, float(similarity))
                    marked_names.add(identity)
                    logging.info(f"rec_faces: Marked attendance for {identity} (saved to DB)")
                    recognized_names.append(identity)
                except Exception as e:
                    logging.error(f"Failed to save attendance for {identity}: {e}")
        except Exception:
            # ignore malformed detection entries
            continue

    # Overlay system info
    try:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        perf_text = f"CPU: {cpu:.0f}%  MEM: {mem:.0f}%"
        cv2.putText(frame, perf_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    except Exception:
        pass

    return frame, recognized_names

def get_marked_names():
    """Return a copy of marked names set."""
    return set(marked_names)

def cleanup():
    """Stop recognizer thread and flush buffers."""
    try:
        recognizer.stop_threads = True
    except Exception:
        pass
    try:
        if recognition_thread.is_alive():
            recognition_thread.join(timeout=2.0)
    except Exception:
        pass
    flush_attendance()
