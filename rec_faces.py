# rec_faces.py
import os
import time
import datetime
import threading
import logging
import psutil
import cv2

from embedding_loader import EmbeddingLoader
from user_data_manager import DatabaseManager
from face_recognizer import FaceRecognizer

# ---------------- Config ----------------
MODEL_NAME = 'Facenet'
SIMILARITY_THRESHOLD = 0.9
STABLE_FRAMES = 10
DATA_DIR = "face_embeddings"
embeddings_path = os.path.join(DATA_DIR, "embeddings.pkl")
user_info_path = os.path.join(DATA_DIR, "user_info.csv")
attendance_file = os.path.join('data', 'attendance.csv')
os.makedirs('data', exist_ok=True)

# Logging configuration
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# ---------------- Load embeddings ----------------
# Use DatabaseManager as loader dependency (adjust if your loader API differs)
db_manager = DatabaseManager()
loader = EmbeddingLoader(db_manager=db_manager)
all_embeddings, all_labels = loader.load_embeddings(from_db=True)
logging.info(f"Loaded {len(all_embeddings)} embeddings for {len(set(all_labels))} active students: {set(all_labels)}")

# ---------------- Face recognizer ----------------
recognizer = FaceRecognizer(
    MODEL_NAME,
    all_embeddings,
    all_labels,
    similarity_threshold=SIMILARITY_THRESHOLD,
    stable_frames=STABLE_FRAMES
)

# ---------------- Attendance State ----------------
# session_active will be toggled by GUI start/end calls
session_active = False
marked_names = set()
attendance_buffer = []
BUFFER_SIZE = 5

def flush_attendance():
    """
    Flush attendance_buffer to the attendance CSV file.
    Each entry is expected to be a CSV line like: "student_id,timestamp\n"
    """
    global attendance_buffer
    if attendance_buffer:
        try:
            with open(attendance_file, 'a', encoding='utf-8') as f:
                for entry in attendance_buffer:
                    f.write(entry)
            logging.info(f"Flushed {len(attendance_buffer)} attendance records to {attendance_file}")
        except Exception as e:
            logging.error(f"Failed to flush attendance to {attendance_file}: {e}")
        attendance_buffer = []

# ---------------- Recognition thread ----------------
# The FaceRecognizer implementation should expose:
# - recognize_faces() -> target for background thread
# - result_lock -> threading.Lock used to synchronize access to recognizer.frame and recognizer.draw_faces
# - draw_faces -> list of (box, identity, similarity, last_seen)
# - frame attribute writable by GUI process_frame
# - stop_threads flag to ask thread to stop
recognition_thread = threading.Thread(target=recognizer.recognize_faces, daemon=True)
recognition_thread.start()

# ---------------- Public API (for GUI) ----------------
def start_session(session_id=None):
    """
    Called from GUI when session begins. Resets marks and sets session active.
    session_id accepted for parity with DB flow.
    """
    global session_active, marked_names
    session_active = True
    marked_names = set()
    logging.info(f"rec_faces: session started (session_id={session_id})")

def end_session():
    """
    Called from GUI when session ends. Flushes buffer and disables marking.
    """
    global session_active
    session_active = False
    flush_attendance()
    logging.info("rec_faces: session ended and buffer flushed")

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
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                attendance_buffer.append(f"{identity},{timestamp}\n")
                if len(attendance_buffer) >= BUFFER_SIZE:
                    flush_attendance()
                marked_names.add(identity)
                logging.info(f"rec_faces: Marked attendance for {identity} at {timestamp}")
                recognized_names.append(identity)
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
