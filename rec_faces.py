
import cv2
import os
import time
import psutil
import datetime
import threading
import logging
from embedding_loader import EmbeddingLoader
from face_recognizer import FaceRecognizer

MODEL_NAME = 'Facenet'
SIMILARITY_THRESHOLD = 0.7
STABLE_FRAMES = 10
DATA_DIR = "face_embeddings"
embeddings_path = os.path.join(DATA_DIR, "embeddings.pkl")
user_info_path = os.path.join(DATA_DIR, "user_info.csv")
attendance_file = os.path.join('data', 'attendance.csv')
os.makedirs('data', exist_ok=True)

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# Load embeddings and active users
loader = EmbeddingLoader(embeddings_path, user_info_path)
active_names = loader.load_active_names()
all_embeddings, all_labels = loader.load_embeddings(active_names)
print(f"[DEBUG] Loaded {len(all_embeddings)} embeddings for {len(set(all_labels))} active people: {set(all_labels)}")

# Face recognizer setup
recognizer = FaceRecognizer(MODEL_NAME, all_embeddings, all_labels, similarity_threshold=SIMILARITY_THRESHOLD, stable_frames=STABLE_FRAMES)

# Attendance session state
session_active = False
marked_names = set()
attendance_buffer = []
BUFFER_SIZE = 5

def flush_attendance():
    global attendance_buffer
    if attendance_buffer:
        with open(attendance_file, 'a') as f:
            for entry in attendance_buffer:
                f.write(entry)
        attendance_buffer = []

# Start background recognition thread
recognition_thread = threading.Thread(target=recognizer.recognize_faces)
recognition_thread.start()

cap = cv2.VideoCapture(0)
print("Press 's' to start attendance session. Press 'q' to quit.")

frame_count = 0
last_time = time.time()
fps = 0

while True:
    ret, new_frame = cap.read()
    if not ret:
        break
    frame_count += 1

    # FPS calculation
    now = time.time()
    if frame_count > 1:
        fps = 1 / (now - last_time)
    last_time = now

    # Update shared frame for recognition thread
    with recognizer.result_lock:
        recognizer.frame = new_frame.copy()

    # Draw all recent boxes/labels
    with recognizer.result_lock:
        for box, identity, similarity, last_seen in recognizer.draw_faces:
            if (time.time() - last_seen) * fps <= STABLE_FRAMES:
                x, y, w, h = box
                cv2.rectangle(new_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(new_frame, f"{identity} {similarity:.2f}", (x, y-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                # Attendance logic for each face
                if session_active and identity != "Unknown" and identity not in marked_names and similarity >= 0.85:
                    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    attendance_buffer.append(f"{identity},{timestamp}\n")
                    if len(attendance_buffer) >= BUFFER_SIZE:
                        flush_attendance()
                    marked_names.add(identity)
                    logging.info(f"Marked attendance for {identity} at {timestamp}")

    # Show CPU, memory, FPS, and session status
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    perf_text = f"CPU: {cpu:.0f}%  MEM: {mem:.0f}%  FPS: {fps:.1f}"
    cv2.putText(new_frame, perf_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    if session_active:
        cv2.putText(new_frame, "ATTENDANCE ACTIVE", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    cv2.imshow("Recognize Faces", new_frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('s'):
        session_active = True
        marked_names.clear()
        print("[INFO] Attendance session started.")

    # --- FPS CAP ---
    target_fps = 30
    frame_time = 1.0 / target_fps
    elapsed = time.time() - now
    if elapsed < frame_time:
        time.sleep(frame_time - elapsed)

# Cleanup
recognizer.stop_threads = True
recognition_thread.join()
cap.release()
cv2.destroyAllWindows()
flush_attendance()