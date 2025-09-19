
import sys
import os
from embedding_loader import EmbeddingLoader
from deepface import DeepFace
from mtcnn import MTCNN
import cv2
import numpy as np

# Usage: python rec_faces_test.py [admission_number]

DATA_DIR = "face_embeddings"
embeddings_path = os.path.join(DATA_DIR, "embeddings.pkl")
user_info_path = os.path.join(DATA_DIR, "user_info.csv")

if len(sys.argv) > 1:
    admission_number = sys.argv[1]
else:
    admission_number = None

# Load embeddings using EmbeddingLoader
loader = EmbeddingLoader(embeddings_path, user_info_path)
active_names = loader.load_active_names()

if admission_number:
    print(f"[INFO] Filtering for admission number: {admission_number}")
    active_names = {admission_number} if admission_number in active_names or not active_names else active_names & {admission_number}
    embeddings, student_ids = loader.load_embeddings({admission_number})
else:
    embeddings, student_ids = loader.load_embeddings(active_names)

if len(embeddings) == 0:
    print("No embeddings found. Please capture faces first.")
    sys.exit(1)

print(f"Loaded {len(embeddings)} embeddings for testing.")

# Load FaceNet model and MTCNN detector
facenet_model = DeepFace.build_model('Facenet')
detector = MTCNN()

cap = cv2.VideoCapture(0)
print("Press 'q' to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        break
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    faces = detector.detect_faces(rgb_frame)
    for face in faces:
        x, y, w, h = face['box']
        x, y = max(0, x), max(0, y)
        face_img = rgb_frame[y:y+h, x:x+w]
        try:
            face_bgr = cv2.cvtColor(face_img, cv2.COLOR_RGB2BGR)
            embedding = DeepFace.represent(face_bgr, model_name='Facenet', enforce_detection=False)[0]["embedding"]
            # Compare with all embeddings
            sims = [np.dot(embedding, e) / (np.linalg.norm(embedding) * np.linalg.norm(e)) for e in embeddings]
            best_idx = int(np.argmax(sims))
            best_score = sims[best_idx]
            label = f"Unknown"
            if best_score > 0.7:
                label = f"{student_ids[best_idx]} ({best_score:.2f})"
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        except Exception as e:
            cv2.putText(frame, "Error", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    cv2.imshow("Test Face Recognition", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Test session ended. No attendance was marked.")
