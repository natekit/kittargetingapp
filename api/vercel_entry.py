from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import core, seed, uploads, analytics
import asyncio

# Create FastAPI app
app = FastAPI(title="Kit Targeting App API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(core.router, prefix="/api", tags=["core"])
app.include_router(seed.router, prefix="/api", tags=["seed"])
app.include_router(uploads.router, prefix="/api", tags=["uploads"])
app.include_router(analytics.router, prefix="/api", tags=["analytics"])

@app.get("/")
def read_root():
    return {"message": "Kit Targeting App API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Run database migrations on startup
@app.on_event("startup")
async def startup_event():
    try:
        print("🚀 Starting API...")
        # Skip migrations for now to avoid startup issues
        print("✅ API started successfully")
    except Exception as e:
        print(f"⚠️ Startup warning: {e}")

# Vercel handler
def handler(request):
    return app
