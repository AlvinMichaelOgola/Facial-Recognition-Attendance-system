import cv2
import numpy as np
from deepface import DeepFace
from mtcnn import MTCNN
from sklearn.metrics.pairwise import cosine_similarity
import time
import threading

class FaceRecognizer:
    def __init__(self, model_name, all_embeddings, all_labels, similarity_threshold=0.7, stable_frames=10):
        self.model_name = model_name
        self.all_embeddings = all_embeddings
        self.all_labels = all_labels
        self.similarity_threshold = similarity_threshold
        self.stable_frames = stable_frames
        self.detector = MTCNN()
        self.model = DeepFace.build_model(model_name)
        self.draw_faces = []
        self.frame = None
        self.result_lock = threading.Lock()
        self.stop_threads = False

    def recognize_faces(self):
        frame_counter = 0
        while not self.stop_threads:
            if self.frame is not None:
                frame_counter += 1
                if frame_counter % 2 != 0:
                    time.sleep(0.01)
                    continue
                with self.result_lock:
                    local_frame = self.frame.copy()
                rgb_frame = cv2.cvtColor(local_frame, cv2.COLOR_BGR2RGB)
                faces = self.detector.detect_faces(rgb_frame)
                new_draw_faces = []
                face_imgs = []
                face_boxes = []
                for face in faces:
                    x, y, w, h = face['box']
                    if w <= 0 or h <= 0:
                        continue
                    x, y = max(0, x), max(0, y)
                    face_img = rgb_frame[y:y+h, x:x+w]
                    face_imgs.append(cv2.cvtColor(face_img, cv2.COLOR_RGB2BGR))
                    face_boxes.append((x, y, w, h))
                if face_imgs:
                    try:
                        reps = DeepFace.represent(face_imgs, model_name=self.model_name, enforce_detection=False)
                        for i, rep in enumerate(reps):
                            embedding = None
                            if isinstance(rep, dict) and "embedding" in rep:
                                embedding = np.array(rep["embedding"])
                            elif isinstance(rep, list) and len(rep) > 0 and isinstance(rep[0], dict) and "embedding" in rep[0]:
                                embedding = np.array(rep[0]["embedding"])
                            if embedding is not None:
                                embedding = embedding / np.linalg.norm(embedding)
                                identity = "Unknown"
                                max_similarity = 0
                                if len(self.all_embeddings) > 0:
                                    sims = cosine_similarity([embedding], self.all_embeddings)[0]
                                    best_idx = np.argmax(sims)
                                    max_similarity = sims[best_idx]
                                    if max_similarity >= self.similarity_threshold:
                                        identity = self.all_labels[best_idx]
                                new_draw_faces.append((face_boxes[i], identity, max_similarity, time.time()))
                    except Exception as e:
                        pass
                with self.result_lock:
                    self.draw_faces = new_draw_faces
            time.sleep(0.01)
