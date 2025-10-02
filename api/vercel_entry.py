from fastapi import FastAPI

# Create minimal FastAPI app
app = FastAPI(title="Kit Targeting App API", version="1.0.0")

@app.get("/")
def read_root():
    return {"message": "Kit Targeting App API"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "API is running"}

# Vercel handler
def handler(request):
    return app