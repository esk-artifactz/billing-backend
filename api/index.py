from fastapi import FastAPI

app = FastAPI()


@app.get("/")
@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "healthy", "message": "Billing API is running"}
