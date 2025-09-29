
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

    def load_embeddings(self, active_names=None, from_db=False, student_ids=None):
        """
        Loads embeddings either from pickle/csv or from the database.
        If from_db=True and db_manager is set, loads from DB for active students only.
        """
        if from_db and self.user_data_manager is not None:
            # Load from DB for active students, or only those in student_ids if provided
            if student_ids is not None:
                print(f"[DEBUG] Requested embeddings for student_ids: {student_ids}")
                if not student_ids:
                    print("[DEBUG] No student_ids provided, returning empty array.")
                    return np.array([]), []
                format_strings = ','.join(['%s'] * len(student_ids))
                q = f"SELECT student_id, embedding FROM face_embeddings WHERE student_id IN ({format_strings})"
                with self.db_manager.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(q, tuple(student_ids))
                        records = cur.fetchall()
                print(f"[DEBUG] Found {len(records)} embeddings in DB for requested students.")
            else:
                records = self.user_data_manager.get_all_face_embeddings()
                print(f"[DEBUG] Loaded all embeddings from DB: {len(records)} records.")
            all_embeddings = []
            all_labels = []
            for rec in records:
                emb = rec['embedding']
                if isinstance(emb, (bytes, bytearray)):
                    emb = pickle.loads(emb)
                all_embeddings.append(emb)
                all_labels.append(rec['student_id'])
            print(f"[DEBUG] Returning {len(all_embeddings)} embeddings, labels: {all_labels}")
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
