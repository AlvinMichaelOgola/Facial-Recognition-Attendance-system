import cv2
import os
import pickle
import numpy as np
import csv
from deepface import DeepFace
from mtcnn import MTCNN
from datetime import datetime

# -------------------- CONFIGURATION --------------------
DATA_DIR = "face_embeddings"
EMBEDDINGS_PATH = os.path.join(DATA_DIR, "embeddings.pkl")
CSV_PATH = os.path.join(DATA_DIR, "user_info.csv")
MAX_FRAMES = 50

# -------------------- SETUP --------------------
os.makedirs(DATA_DIR, exist_ok=True)

# Load existing embeddings if available
if os.path.exists(EMBEDDINGS_PATH):
    with open(EMBEDDINGS_PATH, "rb") as f:
        saved_faces = pickle.load(f)
else:
    saved_faces = {}

# Load FaceNet model once for speed
facenet_model = DeepFace.build_model('Facenet')

# Initialize MTCNN for face detection
# (DeepFace can also detect, but you use MTCNN for consistency)
detector = MTCNN()

# -------------------- USER INPUT --------------------
import sys
# Expect user details from command-line arguments (from GUI)
if len(sys.argv) >= 9:
    person_name = sys.argv[1]
    student_id = sys.argv[2]
    email = sys.argv[3]
    phone = sys.argv[4]
    department = sys.argv[5]
    year = sys.argv[6]
    role = sys.argv[7]
    registration_date = sys.argv[8]
else:
    raise RuntimeError("User details must be provided by the GUI as command-line arguments.")

# -------------------- CAMERA SETUP --------------------
cap = cv2.VideoCapture(0)
print("\nPress 's' to start capturing faces. Press 'q' to quit.")

# Wait for 's' key to start
while True:
    ret, frame = cap.read()
    if not ret:
        break
    cv2.putText(frame, "Press 's' to start capture", (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
    cv2.imshow("Add Faces", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('s'):
        break
    elif key == ord('q'):
        cap.release()
        cv2.destroyAllWindows()
        exit()

print(f"\n🎥 Capturing up to {MAX_FRAMES} frames for {person_name}. Press 'q' to quit early.")
count = 0

while count < MAX_FRAMES:
    ret, frame = cap.read()
    if not ret:
        break
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    faces = detector.detect_faces(rgb_frame)
    # Only process the largest face (if any)
    if faces:
        largest_face = max(faces, key=lambda f: f['box'][2] * f['box'][3])
        x, y, w, h = largest_face['box']
        x, y = max(0, x), max(0, y)
        face_img = rgb_frame[y:y+h, x:x+w]
        try:
            face_bgr = cv2.cvtColor(face_img, cv2.COLOR_RGB2BGR)
            embedding = DeepFace.represent(face_bgr, model_name='Facenet', enforce_detection=False)[0]["embedding"]
            if person_name not in saved_faces:
                saved_faces[person_name] = []
            saved_faces[person_name].append(embedding)
            count += 1
            # Always show green border for added face
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, f"{person_name} ({count})", (x, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        except Exception as e:
            cv2.putText(frame, "Error: Face skipped", (x, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    # Show frame
    cv2.putText(frame, f"Frames captured: {count}/{MAX_FRAMES}", (10, frame.shape[0]-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
    cv2.imshow("Add Faces", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Save embeddings
with open(EMBEDDINGS_PATH, "wb") as f:
    pickle.dump(saved_faces, f)

# Save user info to CSV
write_header = not os.path.exists(CSV_PATH)
with open(CSV_PATH, 'a', newline='') as csvfile:
    writer = csv.writer(csvfile)
    if write_header:
        writer.writerow(["Name", "StudentID", "Email", "Phone", "Department", "Year", "Role", "RegistrationDate"])
    writer.writerow([person_name, student_id, email, phone, department, year, role, registration_date])

print(f"\n[INFO] Saved embeddings for {person_name}, total faces captured: {count}")
cap.release()
cv2.destroyAllWindows()
