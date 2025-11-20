import unittest
from face_recognizer import recognize_face, load_embeddings

class TestFaceRecognition(unittest.TestCase):
    def test_embedding_matching(self):
        # Load sample embeddings and test image
        embeddings = load_embeddings('data/sample_embeddings.npy')
        result = recognize_face('data/test_face.jpg', embeddings)
        self.assertIsNotNone(result)

    def test_no_face_detected(self):
        embeddings = load_embeddings('data/sample_embeddings.npy')
        result = recognize_face('data/no_face.jpg', embeddings)
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
