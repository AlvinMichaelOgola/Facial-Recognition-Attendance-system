import cv2
import numpy as np
from deepface import DeepFace
from mtcnn import MTCNN
from sklearn.metrics.pairwise import cosine_similarity

import time
import threading
import queue


class FaceRecognizer:
    def __init__(self, model_name='Facenet', all_embeddings=None, all_labels=None, similarity_threshold=0.7, stable_frames=15, max_queue_size=5):
        self.model_name = model_name
        # Normalize all stored embeddings
        if all_embeddings is not None and len(all_embeddings) > 0:
            self.all_embeddings = np.array([e / np.linalg.norm(e) for e in all_embeddings])
        else:
            self.all_embeddings = all_embeddings
        self.all_labels = all_labels
        self.similarity_threshold = similarity_threshold
        self.stable_frames = stable_frames  # Number of frames to confirm identity
        self.detector = MTCNN()
        self.model = DeepFace.build_model(self.model_name)
        self.frame_queue = queue.Queue(maxsize=max_queue_size)
        self.result_queue = queue.Queue(maxsize=max_queue_size)
        self.stop_threads = False
        # Smoothing: track last N predictions for each face box (by position hash)
        self.smoothing_buffers = {}  # key: box hash, value: list of (identity, similarity)
        self.smoothing_buffer_size = stable_frames
        self.unknown_debounce = 5  # require 5 consecutive 'Unknown' to switch
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()


    def _worker(self):
        while not self.stop_threads:
            try:
                frame = self.frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
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
                if face_img is None or face_img.size == 0:
                    continue
                if len(face_img.shape) != 3 or face_img.shape[2] != 3:
                    continue
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
                            if self.all_embeddings is not None and len(self.all_embeddings) > 0:
                                sims = cosine_similarity([embedding], self.all_embeddings)[0]
                                best_idx = np.argmax(sims)
                                max_similarity = sims[best_idx]
                                if max_similarity >= self.similarity_threshold:
                                    identity = self.all_labels[best_idx]
                            # --- Smoothing logic ---
                            box = face_boxes[i]
                            box_hash = (box[0]//10, box[1]//10, box[2]//10, box[3]//10)  # quantize for stability
                            buf = self.smoothing_buffers.get(box_hash, [])
                            buf.append((identity, max_similarity))
                            if len(buf) > self.smoothing_buffer_size:
                                buf = buf[-self.smoothing_buffer_size:]
                            self.smoothing_buffers[box_hash] = buf
                            # Count most common identity in buffer
                            id_counts = {}
                            for ident, sim in buf:
                                id_counts[ident] = id_counts.get(ident, 0) + 1
                            # Debounce 'Unknown': only switch if last N are 'Unknown'
                            if buf[-self.unknown_debounce:]==[('Unknown',0)]*self.unknown_debounce:
                                smoothed_identity = 'Unknown'
                                smoothed_similarity = 0
                            else:
                                smoothed_identity = max(id_counts, key=id_counts.get)
                                # Use max similarity for that identity
                                smoothed_similarity = max([sim for ident, sim in buf if ident==smoothed_identity], default=0)
                            new_draw_faces.append((box, smoothed_identity, smoothed_similarity, time.time()))
                except Exception as e:
                    pass
            self.result_queue.put(new_draw_faces)

    def submit_frame(self, frame):
        """
        Submit a frame for recognition. Non-blocking if queue is full.
        """
        try:
            self.frame_queue.put_nowait(frame)
        except queue.Full:
            pass  # Drop frame if queue is full

    def get_latest_result(self):
        """
        Get the latest recognition result. Returns None if no result is available.
        """
        try:
            return self.result_queue.get_nowait()
        except queue.Empty:
            return None

    def set_embeddings(self, all_embeddings, all_labels):
        """
        Update the embeddings and labels used for recognition.
        """
        # Normalize all stored embeddings
        if all_embeddings is not None and len(all_embeddings) > 0:
            self.all_embeddings = np.array([e / np.linalg.norm(e) for e in all_embeddings])
        else:
            self.all_embeddings = all_embeddings
        self.all_labels = all_labels
        self.smoothing_buffers = {}  # Reset smoothing buffers on new embeddings
