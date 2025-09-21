
import os
import pickle
import numpy as np
import csv

# Optional: import user_data_manager for DB access
try:
    from user_data_manager import UserDataManager, DatabaseManager
except ImportError:
    UserDataManager = None
    DatabaseManager = None


class EmbeddingLoader:
    def __init__(self, embeddings_path=None, user_info_path=None, db_manager=None):
        self.embeddings_path = embeddings_path
        self.user_info_path = user_info_path
        self.db_manager = db_manager
        if db_manager is not None and UserDataManager is not None:
            self.user_data_manager = UserDataManager(db_manager)
        else:
            self.user_data_manager = None

    def load_active_names(self):
        # Only used for CSV-based loading
        active_names = set()
        if self.user_info_path and os.path.exists(self.user_info_path):
            with open(self.user_info_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if row.get('Active', '1').strip() == '1':
                        active_names.add(row['Name'])
        return active_names

    def load_embeddings(self, active_names=None, from_db=False):
        """
        Loads embeddings either from pickle/csv or from the database.
        If from_db=True and db_manager is set, loads from DB for active students only.
        """
        if from_db and self.user_data_manager is not None:
            # Load from DB for active students
            records = self.user_data_manager.get_all_face_embeddings()
            all_embeddings = []
            all_labels = []
            for rec in records:
                # rec['embedding'] is a BLOB; unpickle if needed
                emb = rec['embedding']
                if isinstance(emb, (bytes, bytearray)):
                    emb = pickle.loads(emb)
                all_embeddings.append(emb)
                all_labels.append(rec['student_id'])
            return np.array(all_embeddings), all_labels
        # Fallback: load from pickle/csv
        if not self.embeddings_path or not os.path.exists(self.embeddings_path):
            raise FileNotFoundError("No embeddings found. Run add_faces.py first or use from_db=True.")
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
