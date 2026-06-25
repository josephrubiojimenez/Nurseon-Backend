import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import your centralized initialized database wrapper early
# This guarantees your Firestore pool is active before routers load
from database.firebase import db 

# Router imports
from route.smart_notes import smart_notes_router
from route.auth import auth_router
from route.document import doc_router

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

app = FastAPI(
    title="Nurseon Production API",
    description="Nurseon Backend Services",
    version="1.0.0"
)

# --- 🔐 PRODUCTION CORS CONFIGURATION ---
# Handles access boundaries safely between your local Vite UI client and Render's domain
origins = [
    "http://localhost:5173",      # Local Vite dev server
    "http://127.0.0.1:5173",     # Local Vite dev server alternative
    "http://localhost:3000",      # Local React standard port
    "http://127.0.0.1:3000",
    # 🌍 PLACEHOLDERS FOR YOUR LIVE WEB APPS:
    # "https://nurseon.vercel.app", 
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
        "status": "online",
        "message": "Nurseon Production Engine Operational"
    }

if __name__ == "__main__":
    import uvicorn
    # Local fallback driver execution
    uvicorn.run(
        "Nurseon:app",
        host="127.0.0.1",
        port=5000,
        reload=True
    )