import firebase_admin
from firebase_admin import credentials, firestore
import os

key_path = os.path.join(os.path.dirname(__file__), "..", "nurseonServiceAccountKey.json")

if not firebase_admin._apps:
    cred = credentials.Certificate(key_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()