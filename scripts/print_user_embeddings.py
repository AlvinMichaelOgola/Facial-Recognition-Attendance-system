# Set the student ID to query here:

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from user_data_manager import UserDataManager
import numpy as np

# Set the student ID to query here:
student_id = "10061"  # e.g., "10001"

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from user_data_manager import UserDataManager
import numpy as np

db = UserDataManager()
user = db.get_student(student_id)
if not user:
    print(f"No user found with student_id {student_id}")
    exit(1)

name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
embeddings = db.get_face_embeddings(student_id)

print(f"Name: {name}")
print(f"Student ID: {student_id}")
print(f"Number of embeddings: {len(embeddings)}")
for i, emb in enumerate(embeddings, 1):
    print(f"Embedding {i}: {np.array2string(np.array(emb), precision=4, separator=', ')})")
