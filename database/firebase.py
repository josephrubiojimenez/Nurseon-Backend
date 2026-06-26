import os
import firebase_admin
from firebase_admin import credentials, firestore

# Single Source of Truth initialization block
if not firebase_admin._apps:
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cert_path = os.path.join(current_dir, "nurseonServiceAccountKey.json")
    
    if not os.path.exists(cert_path):
        raise FileNotFoundError(f"Missing service credentials key map at: {cert_path}")
        
    cred = credentials.Certificate(cert_path)
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://nurseon-4b83e-default-rtdb.asia-southeast1.firebasedatabase.app/"
    })


db = firestore.client()