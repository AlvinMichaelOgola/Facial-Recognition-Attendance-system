import cv2
import numpy as np
from deepface import DeepFace
from mtcnn import MTCNN
import sys
import time
import logging
import threading

# --- Custom Project Modules ---
from user_data_manager import UserDataManager
from camera_utils import initialize_camera
try:
    from email_utils import send_email
except ImportError:
    send_email = None

# -------------------- CONFIGURATION --------------------
FRAMES_PER_POSE = 5
BLUR_THRESHOLD = 100.0
BRIGHTNESS_THRESHOLD = 60.0
MIN_CAPTURE_INTERVAL = 1.0  # Throttle speed

# Setup Logging
logging.basicConfig(filename='face_capture_errors.log', level=logging.ERROR)

# -------------------- USER INPUT --------------------
if len(sys.argv) >= 2:
    student_id = sys.argv[1]
else:
    student_id = "test_student"

# -------------------- SHARED STATE (Thread Communication) --------------------
class EnrollmentState:
    def __init__(self):
        self.frame = None           # Latest frame from camera
        self.lock = threading.Lock()
        self.running = True
        
        # AI Outputs (What the UI draws)
        self.face_box = None        # (x, y, w, h)
        self.status_msg = "Initializing..."
        self.status_color = (0, 255, 255)
        self.instruction = "Loading AI..."
        self.progress = 0.0
        self.captured_count = 0
        self.stage_idx = 0
        self.is_complete = False
        
        # Logic Triggers
        self.last_capture_time = 0

state = EnrollmentState()

# -------------------- AI WORKER THREAD --------------------
def ai_worker_loop():
    """The Brain: Runs heavy detection in the background."""
    print("[INFO] AI Thread Started.")
    
    # Initialize AI here to keep Main Thread fast
    data_manager = UserDataManager()
    facenet_model = DeepFace.build_model('Facenet')
    detector = MTCNN()
    
    capture_stages = ["Front", "Left", "Right"]
    
    while state.running:
        # 1. Get latest frame safely
        with state.lock:
            if state.frame is None:
                time.sleep(0.01)
                continue
            # Work on a copy so we don't block the UI
            working_frame = state.frame.copy() 
        
        # 2. Check Completion
        if state.stage_idx >= len(capture_stages):
            state.is_complete = True
            state.instruction = "COMPLETE!"
            state.status_msg = "Closing..."
            state.status_color = (0, 255, 0)
            
            # Send Email
            if send_email:
                try:
                    user = data_manager.get_user_by_student_id(student_id)
                    if user and user.get('email'):
                        send_email(user['email'], "Face ID Enrolled", "Success.")
                except: pass
            time.sleep(2) # Let user see success message
            state.running = False
            break

        # 3. Set Instructions
        pose_name = capture_stages[state.stage_idx]
        state.instruction = f"LOOK {pose_name.upper()} ({state.captured_count}/{FRAMES_PER_POSE})"
        
        # Calculate Progress
        total_frames = len(capture_stages) * FRAMES_PER_POSE
        current_frames = (state.stage_idx * FRAMES_PER_POSE) + state.captured_count
        state.progress = current_frames / total_frames

        # 4. Run Detection (HEAVY OPERATION)
        try:
            rgb_frame = cv2.cvtColor(working_frame, cv2.COLOR_BGR2RGB)
            faces = detector.detect_faces(rgb_frame)
            
            if faces:
                largest = max(faces, key=lambda f: f['box'][2] * f['box'][3])
                box = largest['box']
                x, y, w, h = max(0, box[0]), max(0, box[1]), box[2], box[3]
                state.face_box = (x, y, w, h) # Update UI box
                
                if w < 100 or h < 100:
                    state.status_msg = "MOVE CLOSER"
                    state.status_color = (0, 255, 255)
                else:
                    # Quality Checks
                    face_img = working_frame[y:y+h, x:x+w]
                    gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
                    blur = cv2.Laplacian(gray, cv2.CV_64F).var()
                    
                    hsv = cv2.cvtColor(face_img, cv2.COLOR_BGR2HSV)
                    bright = np.mean(cv2.split(hsv)[2])
                    
                    if blur < BLUR_THRESHOLD:
                        state.status_msg = "TOO BLURRY"
                        state.status_color = (0, 0, 255)
                    elif bright < BRIGHTNESS_THRESHOLD:
                        state.status_msg = "TOO DARK"
                        state.status_color = (0, 0, 255)
                    else:
                        # Ready to capture? Check Timer
                        now = time.time()
                        if now - state.last_capture_time < MIN_CAPTURE_INTERVAL:
                            state.status_msg = "HOLD POSE..."
                            state.status_color = (0, 255, 255) # Yellow
                        else:
                            # CAPTURE!
                            state.status_msg = "CAPTURING..."
                            state.status_color = (0, 255, 0) # Green
                            
                            # Preprocess
                            lab = cv2.cvtColor(face_img, cv2.COLOR_BGR2LAB)
                            l, a, b = cv2.split(lab)
                            cl = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(l)
                            enhanced = cv2.cvtColor(cv2.merge((cl, a, b)), cv2.COLOR_LAB2BGR)
                            
                            # Embed
                            emb = DeepFace.represent(enhanced, model_name='Facenet', enforce_detection=False)[0]["embedding"]
                            data_manager.add_face_embedding(student_id, emb)
                            
                            state.captured_count += 1
                            state.last_capture_time = now
                            print(f"[SAVED] {pose_name} {state.captured_count}/{FRAMES_PER_POSE}")
                            
                            if state.captured_count >= FRAMES_PER_POSE:
                                state.stage_idx += 1
                                state.captured_count = 0
                                time.sleep(0.5)
            else:
                state.face_box = None
                state.status_msg = "NO FACE DETECTED"
                state.status_color = (0, 0, 255)
                
        except Exception as e:
            print(f"AI Error: {e}")

# -------------------- UI HELPER --------------------
def draw_ui(frame):
    h, w, _ = frame.shape
    
    # 1. Guide Oval
    cv2.ellipse(frame, (w//2, h//2), (130, 190), 0, 0, 360, (255,255,255), 2)
    
    # 2. AI Feedback Box
    if state.face_box:
        fx, fy, fw, fh = state.face_box
        cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), state.status_color, 2)

    # 3. Top Bar (Instructions)
    cv2.rectangle(frame, (0, 0), (w, 60), (0, 0, 0), -1)
    cv2.putText(frame, state.instruction, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
    
    # 4. Bottom Bar (Status)
    cv2.rectangle(frame, (0, h-50), (w, h), state.status_color, -1)
    # Use black text for contrast on yellow/green backgrounds
    text_color = (0,0,0) if state.status_color != (0,0,255) else (255,255,255)
    cv2.putText(frame, state.status_msg, (20, h-15), cv2.FONT_HERSHEY_SIMPLEX, 0.8, text_color, 2)
    
    # 5. Progress Bar
    bar_w = int(w * state.progress)
    cv2.rectangle(frame, (0, h-10), (bar_w, h), (0, 255, 0), -1)

    return frame

# -------------------- MAIN THREAD (Video & UI) --------------------
def main():
    # 1. Setup Camera
    cap, source_name, warning_msg = initialize_camera(prefer_droidcam=True)
    if not cap:
        print("[CRITICAL] Camera failed.")
        return

    # 2. Start AI Thread
    worker = threading.Thread(target=ai_worker_loop, daemon=True)
    worker.start()

    print("[INFO] Main UI Loop Started.")

    while state.running:
        ret, frame = cap.read()
        if not ret: break
        
        if source_name == "Laptop Webcam":
            frame = cv2.flip(frame, 1)
            
        # Update the Shared State with the new frame so AI can see it
        with state.lock:
            state.frame = frame.copy()
            
        # Draw UI based on latest AI state
        display = draw_ui(frame)
        
        if warning_msg:
             cv2.putText(display, "USING WEBCAM (PHONE NOT FOUND)", (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)

        cv2.imshow("Enrollment", display)
        
        # 30 FPS Refresh Rate (Smooth!)
        if cv2.waitKey(30) & 0xFF == ord('q'):
            state.running = False
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()