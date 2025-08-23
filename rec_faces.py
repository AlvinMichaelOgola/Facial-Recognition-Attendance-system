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

# -------------------- CONFIGURATION --------------------
DATA_DIR = "face_embeddings"
embeddings_path = os.path.join(DATA_DIR, "embeddings.pkl")
attendance_file = os.path.join('data', 'attendance.csv')
os.makedirs('data', exist_ok=True)

# -------------------- LOAD EMBEDDINGS --------------------
if not os.path.exists(embeddings_path):
    print("[ERROR] No embeddings found. Run add_faces.py first.")
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
detector = MTCNN()  # You can switch to a faster detector if needed

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

# -------------------- BACKGROUND FACE RECOGNITION THREAD --------------------
def recognize_faces():
    global frame, result, draw_faces
    while not stop_threads:
        if frame is not None:
            with result_lock:
                local_frame = frame.copy()
            rgb_frame = cv2.cvtColor(local_frame, cv2.COLOR_BGR2RGB)
            faces = detector.detect_faces(rgb_frame)
            new_draw_faces = []
            for face in faces:
                x, y, w, h = face['box']
                x, y = max(0, x), max(0, y)
                face_img = rgb_frame[y:y+h, x:x+w]
                try:
                    face_bgr = cv2.cvtColor(face_img, cv2.COLOR_RGB2BGR)
                    embedding = DeepFace.represent(face_bgr, model_name='Facenet', enforce_detection=False)[0]["embedding"]
                    embedding = np.array(embedding)
                    embedding = embedding / np.linalg.norm(embedding)
                    identity = "Unknown"
                    max_similarity = 0
                    if len(all_embeddings) > 0:
                        sims = cosine_similarity([embedding], all_embeddings)[0]
                        best_idx = np.argmax(sims)
                        max_similarity = sims[best_idx]
                        if max_similarity >= 0.7:
                            identity = all_labels[best_idx]
                    new_draw_faces.append(((x, y, w, h), identity, max_similarity, time.time()))
                except Exception as e:
                    pass
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
                if session_active and identity != "Unknown" and identity not in marked_names:
                    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    with open(attendance_file, 'a') as f:
                        f.write(f"{identity},{timestamp}\n")
                    marked_names.add(identity)
                    print(f"[INFO] Marked attendance for {identity} at {timestamp}")

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



#.\venv310\Scripts\Activate.ps1
# python .\add_faces.py