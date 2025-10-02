from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import core, seed

app = FastAPI(title="Kit Targeting App API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(core.router, prefix="/api", tags=["core"])
app.include_router(seed.router, prefix="/api", tags=["seed"])


@app.get("/")
def read_root():
    return {"message": "Kit Targeting App API"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
