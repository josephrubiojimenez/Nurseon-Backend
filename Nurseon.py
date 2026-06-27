import os
import sys
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.firebase import db 
from route.smart_notes import smart_notes_router
from route.auth import auth_router
from route.document import doc_router
from route.quiz import quiz_router

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

app = FastAPI()

origins = [
    "http://localhost:5173",      # Local Vite dev server
    "http://127.0.0.1:5173",     # Local Vite dev server alternative
    "http://localhost:3000",      # Local React standard port
    "http://127.0.0.1:3000",
    "https://nurseon.vercel.app", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Registration
app.include_router(
    auth_router,
    prefix="/api/auth",
    tags=["Authentication"]
)

# Feature - Read docs
app.include_router(
    doc_router,
    prefix="/api/documents",
    tags=["Read Documents"]
)

# Feature - Smart notes
app.include_router(
    smart_notes_router,
    prefix="/api/smart-notes",
    tags=["Smart Notes"]
)

# Feature - Quiz
app.include_router(
    quiz_router,
    prefix="/api/quiz",
    tags=["Quiz"]
)
# HTTP Status
@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "Nurseon runs successfully"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "Nurseon:app",
        host="127.0.0.1",
        port=5000,
        reload=True
    )