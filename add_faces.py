


import cv2
import numpy as np
from deepface import DeepFace
from mtcnn import MTCNN
import sys
from user_data_manager import UserDataManager
import logging

# Setup error logging
logging.basicConfig(filename='face_capture_errors.log',
                    level=logging.ERROR,
                    format='%(asctime)s %(levelname)s: %(message)s')

# -------------------- CONFIGURATION --------------------
MAX_FRAMES = 50

# -------------------- USER INPUT --------------------
# Expect only student_id from command-line arguments
if len(sys.argv) >= 2:
    student_id = sys.argv[1]
else:
    raise RuntimeError("student_id must be provided by the GUI as a command-line argument.")

# -------------------- SETUP --------------------
data_manager = UserDataManager()

# Load FaceNet model once for speed
facenet_model = DeepFace.build_model('Facenet')
# Initialize MTCNN for face detection
detector = MTCNN()

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

print(f"\n🎥 Capturing up to {MAX_FRAMES} frames for student_id {student_id}. Press 'q' to quit early.")
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
        # Minimum face size check (e.g., 80x80 pixels)
        MIN_FACE_SIZE = 80
        if w < MIN_FACE_SIZE or h < MIN_FACE_SIZE:
            cv2.putText(frame, "Face too small", (x, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        else:
            face_img = rgb_frame[y:y+h, x:x+w]
            try:
                face_bgr = cv2.cvtColor(face_img, cv2.COLOR_RGB2BGR)
                embedding = DeepFace.represent(face_bgr, model_name='Facenet', enforce_detection=False)[0]["embedding"]
                # Save embedding to database
                data_manager.add_face_embedding(student_id, embedding)
                count += 1
                # Always show green border for added face
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(frame, f"{student_id} ({count})", (x, y-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            except Exception as e:
                error_msg = f"Face skipped for student_id {student_id} due to error: {e}"
                print(error_msg)
                logging.error(error_msg)
                cv2.putText(frame, "Error: Face skipped", (x, y-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    # Show frame
    cv2.putText(frame, f"Frames captured: {count}/{MAX_FRAMES}", (10, frame.shape[0]-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
    cv2.imshow("Add Faces", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

print(f"\n[INFO] Saved embeddings for student_id {student_id}, total faces captured: {count}")
cap.release()
cv2.destroyAllWindows()
