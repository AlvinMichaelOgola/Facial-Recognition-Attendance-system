import cv2
import os
import pickle
import numpy as np
from deepface import DeepFace
from mtcnn import MTCNN

# Initialize MTCNN for face detection
# (DeepFace can also detect, but you use MTCNN for consistency)
detector = MTCNN()

# Folder to store embeddings
DATA_DIR = "face_embeddings"
os.makedirs(DATA_DIR, exist_ok=True)
embeddings_path = os.path.join(DATA_DIR, "embeddings.pkl")

# Load existing embeddings if available
if os.path.exists(embeddings_path):
    with open(embeddings_path, "rb") as f:
        saved_faces = pickle.load(f)
else:
    saved_faces = {}

# Load FaceNet model once for speed
facenet_model = DeepFace.build_model('Facenet')

# Start webcam
cap = cv2.VideoCapture(0)
person_name = input("Enter the person's name: ").strip()

print("🎥 Press 'q' to quit early. Capturing 50 frames per person.")
MAX_FRAMES = 50
count = 0

while count < MAX_FRAMES:
    ret, frame = cap.read()
    if not ret:
        break

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    faces = detector.detect_faces(rgb_frame)
    print(f"[DEBUG] Detected {len(faces)} faces in frame {count+1}")

    # Only process the largest face (if any)
    if faces:
        largest_face = max(faces, key=lambda f: f['box'][2] * f['box'][3])
        x, y, w, h = largest_face['box']
        x, y = max(0, x), max(0, y)
        face_img = rgb_frame[y:y+h, x:x+w]
        print(f"[DEBUG] Face crop shape: {face_img.shape}")

        try:
            # Use DeepFace to get FaceNet embedding from cropped face
            face_bgr = cv2.cvtColor(face_img, cv2.COLOR_RGB2BGR)
            embedding = DeepFace.represent(face_bgr, model_name='Facenet', enforce_detection=False)[0]["embedding"]
            print(f"[DEBUG] Embedding (first 5): {embedding[:5]}")

            if person_name not in saved_faces:
                saved_faces[person_name] = []
            saved_faces[person_name].append(embedding)
            count += 1

            # Draw rectangle and count
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, f"{person_name} ({count})", (x, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        except Exception as e:
            print("[DEBUG] Skipping a face due to error:", e)

    cv2.imshow("Add Faces", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Save embeddings
with open(embeddings_path, "wb") as f:
    pickle.dump(saved_faces, f)

print(f"[INFO] Saved embeddings for {person_name}, total faces captured: {count}")
cap.release()
cv2.destroyAllWindows()
