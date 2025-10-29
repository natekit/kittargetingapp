from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import core, seed, uploads, analytics, declined_creators

app = FastAPI(title="Kit Targeting App API", version="1.0.0")

# Configure CORS
# Use regex pattern in production to allow all origins (for public API)
# This handles Vercel screenshot service and other legitimate services
if settings.APP_ENV == "production":
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://.*",  # Allow all HTTP/HTTPS origins
        allow_credentials=False,  # Cannot use credentials with regex origins
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

# Mount routers
app.include_router(core.router, prefix="/api", tags=["core"])
app.include_router(seed.router, prefix="/api", tags=["seed"])
app.include_router(uploads.router, prefix="/api", tags=["uploads"])
app.include_router(analytics.router, prefix="/api", tags=["analytics"])
app.include_router(declined_creators.router, prefix="/api", tags=["declined-creators"])


@app.get("/")
def read_root():
    return {"message": "Kit Targeting App API"}


@app.get("/health")
@app.get("/healthz")
def health_check():
    """Health check endpoint for Render and other services."""
    return {"status": "healthy", "service": "Kit Targeting API"}
