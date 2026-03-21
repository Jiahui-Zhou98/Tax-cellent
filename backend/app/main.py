from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import upload, review, health

app = FastAPI(
    title="TaxDebate Local",
    description="Privacy-first local tax document review system",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(review.router, prefix="/api", tags=["review"])
