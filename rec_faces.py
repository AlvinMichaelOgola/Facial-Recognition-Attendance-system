import os
import time
import datetime
import threading
import logging
import psutil
import cv2
import math
import sys
import numpy as np
import json
from deepface import DeepFace 

# --- Custom Project Modules ---
from embedding_loader import EmbeddingLoader
from user_data_manager import UserDataManager
from face_recognizer import FaceRecognizer
from camera_utils import initialize_camera

# ---------------- Config ----------------
MODEL_NAME = 'Facenet'
SIMILARITY_THRESHOLD = 0.75
STABLE_FRAMES = 8 
ROI_SIZE = 400
BLUR_THRESHOLD = 100

DATA_DIR = "face_embeddings"
os.makedirs('data', exist_ok=True)
os.makedirs('reports', exist_ok=True)

# Logging configuration
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

db_manager = UserDataManager()
loader = EmbeddingLoader(db_manager=db_manager.db_manager)
recognizer = None

# ---------------- Attendance State ----------------
session_active = False
marked_names = set()
current_session_id = None
_last_seen_faces = {}
_SMOOTHING_SECONDS = 0.3 

# --- STATISTICS TRACKER ---
session_stats = {
    "start_time": 0,
    "total_frames": 0,
    "total_detections": 0,
    "total_knowns": 0,
    "total_unknowns": 0,
    "fps_history": [],
    "cpu_history": []
}

# ---------------- Core Logic ----------------

def start_session(session_id=None, student_ids=None):
    """Initializes the AI engine and resets stats."""
    global session_active, marked_names, recognizer, current_session_id, session_stats
    session_active = True
    marked_names = set()
    current_session_id = session_id
    
    # Reset Stats
    session_stats = {
        "start_time": time.time(),
        "total_frames": 0,
        "total_detections": 0,
        "total_knowns": 0,
        "total_unknowns": 0,
        "fps_history": [],
        "cpu_history": []
    }
    
    # 1. Load Student Data
    print(f"[INFO] Loading Student Database for Session {session_id}...")
    try:
        if student_ids:
            try:
                all_embeddings, all_labels = loader.load_embeddings(from_db=True, student_ids=student_ids)
            except TypeError:
                all_embeddings, all_labels = loader.load_embeddings(from_db=True)
        else:
            all_embeddings, all_labels = loader.load_embeddings(from_db=True)
    except Exception as e:
        print(f"[ERROR] Failed to load embeddings: {e}")
        all_embeddings, all_labels = [], []

    # 2. PRE-LOAD MODEL
    print("[INFO] Pre-loading FaceNet Model...")
    try:
        DeepFace.build_model(MODEL_NAME) 
    except Exception as e:
        print(f"[WARN] Model build warning: {e}")
    
    # 3. Initialize Worker
    recognizer = FaceRecognizer(
        MODEL_NAME, 
        all_embeddings, 
        all_labels, 
        similarity_threshold=SIMILARITY_THRESHOLD, 
        stable_frames=STABLE_FRAMES
    )
    logging.info(f"Session {session_id} started.")

def end_session():
    """Stops the AI engine and saves a detailed performance report."""
    global session_active
    session_active = False
    if recognizer:
        recognizer.stop_threads = True
    
    # --- GENERATE REPORT ---
    try:
        duration = time.time() - session_stats["start_time"]
        
        # Calculate Averages
        avg_fps = np.mean(session_stats["fps_history"]) if session_stats["fps_history"] else 0
        avg_cpu = np.mean(session_stats["cpu_history"]) if session_stats["cpu_history"] else 0
        
        # Calculate Recognition Rate
        total = session_stats["total_detections"]
        rec_rate = (session_stats["total_knowns"] / total * 100) if total > 0 else 0

        report_data = {
            "session_id": current_session_id,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": round(duration, 2),
            "performance": {
                "average_fps": round(avg_fps, 2),
                "average_cpu_usage": round(avg_cpu, 2),
                "total_frames_processed": session_stats["total_frames"]
            },
            "detection_stats": {
                "total_faces_seen": session_stats["total_detections"],
                "known_faces": session_stats["total_knowns"],
                "unknown_faces": session_stats["total_unknowns"],
                "recognition_rate": f"{rec_rate:.2f}%"
            },
            "attendance": {
                "total_marked": len(marked_names),
                "marked_ids": list(marked_names)
            }
        }
        
        report_path = f"reports/stats_session_{current_session_id}.json"
        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=4)
            
        print(f"[INFO] Performance report saved to {report_path}")
        
    except Exception as e:
        print(f"[WARN] Failed to save statistics report: {e}")

def process_frame(frame):
    """
    Processes a frame. GUARANTEED to return (frame, list) even on error.
    """
    global marked_names, _last_seen_faces, session_stats
    newly_marked = []
    
    # --- FPS Tracking Init ---
    if not hasattr(process_frame, "last_time"):
        process_frame.last_time = time.time()
    
    # --- SAFETY GUARD 1: Check for Empty Frame ---
    if frame is None or frame.size == 0:
        return frame, []

    try:
        # --- PERFORMANCE TRACKING ---
        now = time.time()
        dt = now - process_frame.last_time
        process_frame.last_time = now
        
        if dt > 0:
            current_fps = 1.0 / dt
            session_stats["fps_history"].append(current_fps)
            session_stats["cpu_history"].append(psutil.cpu_percent())
            session_stats["total_frames"] += 1

        # 1. Mirror Effect
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        # 2. ROI Calculation
        roi_w, roi_h = min(ROI_SIZE, w), min(ROI_SIZE, h)
        start_x = (w - roi_w) // 2
        start_y = (h - roi_h) // 2
        end_x = start_x + roi_w
        end_y = start_y + roi_h

        # 3. Scanning Animation
        scan_speed = 4.0
        scan_offset = int((math.sin(time.time() * scan_speed) + 1) / 2 * roi_h)
        scan_y = start_y + scan_offset
        
        cv2.rectangle(frame, (start_x, start_y), (end_x, end_y), (255, 150, 0), 2)
        cv2.line(frame, (start_x, scan_y), (end_x, scan_y), (255, 150, 0), 2)
        cv2.putText(frame, "ATTENDANCE ACTIVE", (start_x + 10, start_y - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 150, 0), 2)

        # 4. Prepare Crop for AI
        roi_crop = frame[start_y:end_y, start_x:end_x]
        
        try:
            gray_roi = cv2.cvtColor(roi_crop, cv2.COLOR_BGR2GRAY)
            blur_score = cv2.Laplacian(gray_roi, cv2.CV_64F).var()
            
            if blur_score > BLUR_THRESHOLD:
                lab = cv2.cvtColor(roi_crop, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                cl = clahe.apply(l)
                roi_enhanced = cv2.cvtColor(cv2.merge((cl, a, b)), cv2.COLOR_LAB2BGR)
                
                roi_rgb = cv2.cvtColor(roi_enhanced, cv2.COLOR_BGR2RGB)
                if recognizer:
                    recognizer.submit_frame(roi_rgb)
            else:
                cv2.putText(frame, "HOLD STILL", (start_x + 10, end_y - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        except Exception:
            pass

        # 5. Get Results (SAFETY GUARD 2: Handle None Result)
        draw_snapshot = []
        if recognizer:
            res = recognizer.get_latest_result()
            if res is not None:
                draw_snapshot = res

        now_ts = time.time()
        current_faces = {} 

        for detection in draw_snapshot:
            try:
                box, identity, similarity, last_seen = detection
                rx, ry, rw, rh = box
                gx = rx + start_x
                gy = ry + start_y
                current_faces[identity] = ((gx, gy, rw, rh), identity, similarity, now_ts)
                _last_seen_faces[identity] = current_faces[identity]
                
                # --- STATS UPDATE ---
                session_stats["total_detections"] += 1
                if identity == "Unknown":
                    session_stats["total_unknowns"] += 1
                else:
                    session_stats["total_knowns"] += 1
                    
            except Exception:
                continue

        _last_seen_faces = {k: v for k, v in _last_seen_faces.items() if now_ts - v[3] <= _SMOOTHING_SECONDS}

        for detection in _last_seen_faces.values():
            try:
                box, identity, similarity, last_seen = detection
                x, y, bw, bh = box
                
                color = (0, 0, 255)
                status_text = f"{similarity:.2f}"
                
                if identity in marked_names:
                    color = (0, 255, 0)
                    status_text = "PRESENT"
                elif identity != "Unknown":
                    color = (0, 255, 255)
                
                cv2.rectangle(frame, (x, y), (x + bw, y + bh), color, 2)
                cv2.putText(frame, f"{identity}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                cv2.putText(frame, status_text, (x, y + bh + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                if session_active and identity != "Unknown" and identity not in marked_names and similarity >= SIMILARITY_THRESHOLD:
                    try:
                        db_manager.add_attendance_record(current_session_id, identity, float(similarity))
                        marked_names.add(identity)
                        newly_marked.append(identity)
                        logging.info(f"Marked: {identity}")
                    except Exception:
                        pass
            except Exception:
                continue

        try:
            cpu = psutil.cpu_percent(interval=None)
            fps_disp = f"FPS: {current_fps:.1f}" if 'current_fps' in locals() else "FPS: --"
            cv2.putText(frame, f"CPU: {cpu}% | {fps_disp}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        except Exception:
            pass

        return frame, newly_marked

    except Exception as e:
        # --- SAFETY GUARD 3: Catastrophic Failure Handler ---
        print(f"[CRITICAL ERROR in process_frame]: {e}")
        return frame, []

# ---------------- Window Loop ----------------
def start_gui_session(session_id, camera_index=0):
    start_session(session_id)
    cap, _, _ = initialize_camera(prefer_droidcam=(camera_index==1))
    
    if not cap: return

    window_name = f"Session {session_id}"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    while True:
        ret, frame = cap.read()
        if not ret: break
        
        processed_frame, new_names = process_frame(frame)
        
        if processed_frame is None: 
            continue

        cv2.imshow(window_name, processed_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    end_session()
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    import sys
    sid = 101
    cam = 0
    if len(sys.argv) > 1: sid = sys.argv[1]
    if len(sys.argv) > 2: cam = int(sys.argv[2])
    start_gui_session(sid, cam)