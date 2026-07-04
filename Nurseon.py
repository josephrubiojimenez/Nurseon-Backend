import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- SlowAPI Imports for Global Setup ---
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

from database.firebase import db 
from utils.firebase_health import log_firebase_status
from route.smart_notes import smart_notes_router
from route.auth import auth_router
from route.document import doc_router
from route.quiz import quiz_router
from route.case_studies import case_studies_router
from route.progress import progress_router

# Import the router alongside its internal instantiated limiter configuration instance
from route.nurseon_ai_chat import nurseon_ai_chat_router, limiter
from route.mock_board_exam import mock_board_exam_router
from route.nursing_care_plans import nursing_care_plans_router

# Ensure current directory is in system path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

app = FastAPI()

# --- Firebase Health Check on Startup ---
@app.on_event("startup")
async def startup_event():
    log_firebase_status()

# =================================================================
# 1. CORS MIDDLEWARE (Must be evaluated first for preflight/OPTIONS)
# =================================================================
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://nurseon-i179.vercel.app/",
    "https://nurseon-backend.onrender.com",
    os.environ.get("VERCEL_URL", ""),
    os.environ.get("FRONTEND_URL", ""),
]

# Clean origins array and remove trailing slashes
origins = [origin.rstrip("/") for origin in origins if origin]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_origin_regex=r"https://nurseon-i179.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

# =================================================================
# 2. RATE LIMITER MIDDLEWARE (Evaluated after CORS)
# =================================================================
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# =================================================================
# ROUTER REGISTRATIONS
# =================================================================

# Authentication
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

# Feature - Case Study
app.include_router(
    case_studies_router,
    prefix='/api/case-studies',
    tags=["Case Studies"]
)

# Feature - AI
app.include_router(
    nurseon_ai_chat_router,
    prefix='/api/nurseon-ai',
    tags=["Nurseon AI"]
)

# Feature - Mock Board Exam
app.include_router(
    mock_board_exam_router,
    prefix='/api/mock-board-exam',
    tags=["Mock Exam"]
)

# Feature - Progress
app.include_router(
    progress_router,
    prefix="/api/progress",
    tags=["Progress"]
)

# Feature - Nursing Care Plan
app.include_router(
    nursing_care_plans_router,
    prefix="/api/nursing-care-plans",
    tags=["Nursing Care Plans"]
)


# =================================================================
# SYSTEM ENDPOINTS
# =================================================================

# Base API Status
@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "Nurseon runs successfully"
    }

# Health Check Endpoint
@app.get("/api/health")
async def health_check():
    from datetime import datetime, timezone
    return {
        "status": "healthy",
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "Nurseon:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        reload=True
    )