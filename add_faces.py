


import cv2
import numpy as np
from deepface import DeepFace
from mtcnn import MTCNN
import sys
import time
from user_data_manager import UserDataManager
import logging
from email_utils import send_email
import math

# Setup error logging
logging.basicConfig(filename='face_capture_errors.log',
                    level=logging.ERROR,
                    format='%(asctime)s %(levelname)s: %(message)s')

# -------------------- CONFIGURATION --------------------
MAX_FRAMES = 50
MIN_CAPTURE_INTERVAL = 0.5  # seconds between captures
BLUR_THRESHOLD = 100.0  # lower = more blurry

# -------------------- USER INPUT --------------------
# Expect only student_id from command-line arguments
if len(sys.argv) >= 2:
    student_id = sys.argv[1]
    print(f"[DEBUG] add_faces.py received student_id: {student_id}")
else:
    raise RuntimeError("student_id must be provided by the GUI as a command-line argument.")

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
    # Flip camera horizontally for mirror effect
    frame = cv2.flip(frame, 1)
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



# Estimate yaw (left/right turn) from MTCNN landmarks
def estimate_yaw(landmarks):
    left_eye = np.array(landmarks['left_eye'])
    right_eye = np.array(landmarks['right_eye'])
    nose = np.array(landmarks['nose'])
    # Vector from left to right eye
    eye_vec = right_eye - left_eye
    # Vector from midpoint of eyes to nose
    eye_mid = (left_eye + right_eye) / 2
    nose_vec = nose - eye_mid
    # Yaw: angle between eye_vec and horizontal (should be close to 0 for frontal)
    yaw = math.degrees(math.atan2(nose_vec[0], nose_vec[1]+1e-6))
    return yaw

# Check if face is frontal (within threshold degrees)
def is_frontal(landmarks, threshold=15):
    try:
        yaw = estimate_yaw(landmarks)
        return abs(yaw) < threshold
    except Exception:
        return False


pose_step = 0
count = 0
last_capture_time = 0


while count < MAX_FRAMES:
    ret, frame = cap.read()
    if not ret:
        break
    # Flip camera horizontally for mirror effect
    frame = cv2.flip(frame, 1)
    # Resize frame for faster detection (keep original for embedding)
    display_frame = frame.copy()
    small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
    rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
    faces = detector.detect_faces(rgb_small)
    # Only process the largest face (if any)
    if faces:
        largest_face = max(faces, key=lambda f: f['box'][2] * f['box'][3])
        x, y, w, h = largest_face['box']
        # Scale box back to original size
        x, y, w, h = int(x*2), int(y*2), int(w*2), int(h*2)
        x, y = max(0, x), max(0, y)
        MIN_FACE_SIZE = 80
        pose_feedback = ""
        if w < MIN_FACE_SIZE or h < MIN_FACE_SIZE:
            pose_feedback = "Face too small"
        face_img = frame[y:y+h, x:x+w]
        if pose_feedback:
            cv2.putText(display_frame, pose_feedback, (x, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        else:
            now = time.time()
            if now - last_capture_time >= MIN_CAPTURE_INTERVAL:
                try:
                    face_bgr = face_img
                    embedding = DeepFace.represent(face_bgr, model_name='Facenet', enforce_detection=False)[0]["embedding"]
                    # Save embedding to database
                    try:
                        data_manager.add_face_embedding(student_id, embedding)
                        print(f"[SUCCESS] Saved embedding for student_id {student_id} (frame {count+1})")
                        # --- Email alert on first successful embedding save ---
                        if count == 0:
                            user = data_manager.get_user_by_student_id(student_id)
                            if user and user.get('email'):
                                email = user['email']
                                first_name = user.get('first_name', 'Student')
                                subject = "Face Data Re-Captured"
                                body = f"""
                                <html>
                                <body>
                                  <h2>Face Data Re-Captured</h2>
                                  <p>Hello {first_name},</p>
                                  <p>Your face data has just been re-captured and updated in the attendance system.</p>
                                  <p>If you did not authorize this, please contact your lecturer or system administrator immediately.</p>
                                  <br>
                                  <p>Best regards,<br>Attendance System Team</p>
                                </body>
                                </html>
                                """
                                try:
                                    send_email(email, subject, body, html=True)
                                    print(f"[INFO] Notification email sent to {email}")
                                except Exception as e:
                                    print(f"[WARN] Failed to send notification email: {e}")
                    except Exception as db_exc:
                        error_msg = f"[DB ERROR] Failed to save embedding for student_id {student_id}: {db_exc}"
                        print(error_msg)
                        logging.error(error_msg)
                        cv2.putText(display_frame, "DB Error", (x, y-10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        continue
                    count += 1
                    last_capture_time = now
                    # Always show green border for added face
                    cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(display_frame, f"{student_id} ({count})", (x, y-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                except Exception as e:
                    error_msg = f"Face skipped for student_id {student_id} due to error: {e}"
                    print(error_msg)
                    logging.error(error_msg)
                    cv2.putText(display_frame, "Error: Face skipped", (x, y-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    # Show progress bar
    bar_length = 300
    filled = int(bar_length * count / MAX_FRAMES)
    cv2.rectangle(display_frame, (10, display_frame.shape[0]-30), (10+bar_length, display_frame.shape[0]-10), (200,200,200), 2)
    cv2.rectangle(display_frame, (10, display_frame.shape[0]-30), (10+filled, display_frame.shape[0]-10), (0,255,0), -1)
    cv2.putText(display_frame, f"Frames captured: {count}/{MAX_FRAMES}", (10, display_frame.shape[0]-40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
    cv2.imshow("Add Faces", display_frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

print(f"\n[INFO] Saved embeddings for student_id {student_id}, total faces captured: {count}")
cap.release()
cv2.destroyAllWindows()
