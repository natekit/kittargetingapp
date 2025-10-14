from fastapi import FastAPI
from mangum import Mangum

# Create FastAPI app
app = FastAPI(title="Kit Targeting App API", version="1.0.0")

@app.get("/")
def read_root():
    return {"message": "Kit Targeting App API"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "API is running"}

# Vercel handler using Mangum
handler = Mangum(app)