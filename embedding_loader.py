import os
import pickle
import numpy as np
import csv

class EmbeddingLoader:
    def __init__(self, embeddings_path, user_info_path):
        self.embeddings_path = embeddings_path
        self.user_info_path = user_info_path

    def load_active_names(self):
        active_names = set()
        if os.path.exists(self.user_info_path):
            with open(self.user_info_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if row.get('Active', '1').strip() == '1':
                        active_names.add(row['Name'])
        return active_names

    def load_embeddings(self, active_names=None):
        if not os.path.exists(self.embeddings_path):
            raise FileNotFoundError("No embeddings found. Run add_faces.py first.")
        with open(self.embeddings_path, "rb") as f:
            saved_faces = pickle.load(f)
        all_embeddings = []
        all_labels = []
        for name, embeddings_list in saved_faces.items():
            if active_names is None or name in active_names:
                for emb in embeddings_list:
                    all_embeddings.append(emb)
                    all_labels.append(name)
        return np.array(all_embeddings), all_labels
