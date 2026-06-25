import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials

# Router imports
from route.smart_notes import smart_notes_router
from route.auth import auth_router
from route.document import doc_router

current_dir = os.path.dirname(os.path.abspath(__file__))

if current_dir not in sys.path:
    sys.path.append(current_dir)

# --- FIREBASE INITIALIZATION ---
try:
    cert_path = os.path.join(current_dir, "nurseonServiceAccountKey.json")

    if not os.path.exists(cert_path):
        raise FileNotFoundError(
            f"Could not find Service Account Key at:\n{cert_path}"
        )

    cred = credentials.Certificate(cert_path)

    firebase_admin.initialize_app(
        cred,
        {
            "databaseURL": "https://nurseon-4b83e-default-rtdb.asia-southeast1.firebasedatabase.app/"
        }
    )
    print("Firebase Admin SDK initialized successfully.")

except ValueError:
    print("Firebase already initialized.")
except Exception as e:
    print(f"Firebase Initialization Error: {e}")


app = FastAPI(
    title="Nurseon Production API",
    description="Nurseon Backend Services",
    version="1.0.0"
)

# --- 🔐 PRODUCTION CORS CONFIGURATION ---
# This ensures both your local development tools and your future live website can talk to this API.
origins = [
    "http://localhost:5173",      # Local Vite dev server
    "http://127.0.0.1:5173",     # Local Vite dev server alternative
    "http://localhost:3000",      # Local React standard port
    "http://127.0.0.1:3000",
    # 🌍 PLACEHOLDERS FOR YOUR LIVE WEB APPS:
    # Once you deploy your frontend, uncomment or replace these with your actual production links!
    # "https://your-app-name.vercel.app", 
    # "https://your-app-name.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# --- ROUTER REGISTRATION ---
app.include_router(
    auth_router,
    prefix="/api/auth",
    tags=["Authentication"]
)

app.include_router(
    doc_router,
    prefix="/api/documents",
    tags=["Read Documents"]
)

app.include_router(
    smart_notes_router,
    prefix="/api/smart-notes",
    tags=["Smart Notes"]
)

@app.get("/")
async def root():
    return {
        "message": "Nurseon API Running Successfully"
    }

if __name__ == "__main__":
    import uvicorn

    # Local execution fallback
    uvicorn.run(
        "Nurseon:app",
        host="127.0.0.1",
        port=5000,
        reload=True
    )