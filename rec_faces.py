import cv2
import os
import pickle
import numpy as np
import time
import psutil
import datetime
from deepface import DeepFace
from mtcnn import MTCNN
from sklearn.metrics.pairwise import cosine_similarity
import threading
import logging

# -------------------- CONFIGURATION --------------------
MODEL_NAME = 'Facenet'  # Change to 'SFace' or 'ArcFace' for lighter models
FRAME_SKIP = 2  # Only run recognition every N frames
SIMILARITY_THRESHOLD = 0.7
STABLE_FRAMES = 10
LOG_LEVEL = logging.INFO

DATA_DIR = "face_embeddings"
embeddings_path = os.path.join(DATA_DIR, "embeddings.pkl")
attendance_file = os.path.join('data', 'attendance.csv')
os.makedirs('data', exist_ok=True)

# -------------------- LOGGING SETUP --------------------
logging.basicConfig(level=LOG_LEVEL, format='[%(levelname)s] %(message)s')

# -------------------- LOAD EMBEDDINGS --------------------
if not os.path.exists(embeddings_path):
    logging.error("No embeddings found. Run add_faces.py first.")
    exit()

with open(embeddings_path, "rb") as f:
    saved_faces = pickle.load(f)

# Flatten all embeddings with their labels
all_embeddings = []
all_labels = []
for name, embeddings_list in saved_faces.items():
    for emb in embeddings_list:
        all_embeddings.append(emb)
        all_labels.append(name)
all_embeddings = np.array(all_embeddings)

print(f"[DEBUG] Loaded {len(all_embeddings)} embeddings for {len(set(all_labels))} people: {set(all_labels)}")

# -------------------- FACE DETECTION SETUP --------------------
detector = MTCNN()
# Preload DeepFace model
_ = DeepFace.build_model(MODEL_NAME)

# -------------------- ATTENDANCE SESSION --------------------
session_active = False
marked_names = set()

# -------------------- THREADING VARIABLES --------------------
frame = None
result = None
result_lock = threading.Lock()
stop_threads = False

# For stable box/label (now a list for multiple faces)
draw_faces = []  # Each item: (box, identity, similarity, last_seen)
STABLE_FRAMES = 10

# -------------------- ATTENDANCE LOGGING BUFFER --------------------
attendance_buffer = []
BUFFER_SIZE = 5

def flush_attendance():
    global attendance_buffer
    if attendance_buffer:
        with open(attendance_file, 'a') as f:
            for entry in attendance_buffer:
                f.write(entry)
        attendance_buffer = []

# -------------------- BACKGROUND FACE RECOGNITION THREAD --------------------
def recognize_faces():
    global frame, result, draw_faces
    frame_counter = 0
    while not stop_threads:
        if frame is not None:
            frame_counter += 1
            if frame_counter % FRAME_SKIP != 0:
                time.sleep(0.01)
                continue
            with result_lock:
                local_frame = frame.copy()
            rgb_frame = cv2.cvtColor(local_frame, cv2.COLOR_BGR2RGB)
            faces = detector.detect_faces(rgb_frame)
            new_draw_faces = []
            face_imgs = []
            face_boxes = []
            # Collect all face images and their boxes
            for face in faces:
                x, y, w, h = face['box']
                # Skip faces with zero or negative width/height
                if w <= 0 or h <= 0:
                    continue
                x, y = max(0, x), max(0, y)
                face_img = rgb_frame[y:y+h, x:x+w]
                face_imgs.append(cv2.cvtColor(face_img, cv2.COLOR_RGB2BGR))
                face_boxes.append((x, y, w, h))
            # Batch process embeddings if faces found
            if face_imgs:
                try:
                    reps = DeepFace.represent(face_imgs, model_name=MODEL_NAME, enforce_detection=False)
                    for i, rep in enumerate(reps):
                        # Defensive: rep may be a dict or a list (if detection failed)
                        embedding = None
                        if isinstance(rep, dict) and "embedding" in rep:
                            embedding = np.array(rep["embedding"])
                        elif isinstance(rep, list) and len(rep) > 0 and isinstance(rep[0], dict) and "embedding" in rep[0]:
                            embedding = np.array(rep[0]["embedding"])
                        if embedding is not None:
                            embedding = embedding / np.linalg.norm(embedding)
                            identity = "Unknown"
                            max_similarity = 0
                            if len(all_embeddings) > 0:
                                sims = cosine_similarity([embedding], all_embeddings)[0]
                                best_idx = np.argmax(sims)
                                max_similarity = sims[best_idx]
                                if max_similarity >= SIMILARITY_THRESHOLD:
                                    identity = all_labels[best_idx]
                            new_draw_faces.append((face_boxes[i], identity, max_similarity, time.time()))
                        else:
                            logging.warning(f"No embedding returned for face {i} in batch.")
                except Exception as e:
                    logging.warning(f"Recognition error: {e}")
            with result_lock:
                draw_faces = new_draw_faces
        time.sleep(0.01)

# -------------------- MAIN VIDEO LOOP --------------------
cap = cv2.VideoCapture(0)
print("Press 's' to start attendance session. Press 'q' to quit.")

# Start background thread
recognition_thread = threading.Thread(target=recognize_faces)
recognition_thread.start()

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
    with result_lock:
        frame = new_frame.copy()

    # Draw all recent boxes/labels
    with result_lock:
        for box, identity, similarity, last_seen in draw_faces:
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
stop_threads = True
recognition_thread.join()
cap.release()
cv2.destroyAllWindows()

# After the main loop, flush any remaining attendance:
flush_attendance()



#.\venv310\Scripts\Activate.ps1
# python .\add_faces.py