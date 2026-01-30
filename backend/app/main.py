#uvicorn app.main:app --reload

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.api.routes import abdm, auth, consents, patients, records
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User

app = FastAPI(title=settings.project_name)

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(abdm.router)
app.include_router(records.router)
app.include_router(patients.router)
app.include_router(consents.router)


@app.get("/")
def root():
    return {
        "message": "ABDM HIE-CM Integration",
        "detail": "Colposcope imaging backend",
    }


@app.on_event("startup")
def ensure_admin_user():
    if not settings.admin_email or not settings.admin_password:
        return

    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.admin_email).first()
        if existing:
            return

        user = User(
            email=settings.admin_email,
            hashed_password=get_password_hash(settings.admin_password),
            role=settings.admin_role,
            is_active=True,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()
