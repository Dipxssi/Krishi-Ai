from fastapi import FastAPI
from app.api.query import router as query_router

app = FastAPI(title="AI Farmer Backend")

app.include_router(query_router)

@app.get("/")
def root():
  return {"message": "Backend is running..."}