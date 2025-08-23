from deepface import DeepFace
import numpy as np
import cv2

# Load two different face images (replace with your own image paths)
img1 = cv2.imread('bill.jpg')
img2 = cv2.imread('obama.jpg')

print(f"[DEBUG] img1 shape: {img1.shape if img1 is not None else None}")
print(f"[DEBUG] img2 shape: {img2.shape if img2 is not None else None}")

if img1 is None or img2 is None:
    print("[ERROR] Could not load one or both images. Please check the file paths.")
    exit()

# Extract embeddings using DeepFace high-level API
emb1 = DeepFace.represent(img_path='bill.jpg', model_name='Facenet', enforce_detection=False)[0]["embedding"]
emb2 = DeepFace.represent(img_path='obama.jpg', model_name='Facenet', enforce_detection=False)[0]["embedding"]

print("[DEBUG] Embedding 1 (first 5):", emb1[:5])
print("[DEBUG] Embedding 2 (first 5):", emb2[:5])
print("Are they the same?", np.allclose(emb1, emb2))
