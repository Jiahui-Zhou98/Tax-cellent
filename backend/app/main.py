from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import upload, review, health
from app.core.config import settings

app = FastAPI(
    title="Tax-cellent",
    description="Privacy-first local tax document review system",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(review.router, prefix="/api", tags=["review"])
