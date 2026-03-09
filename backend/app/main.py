from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.api.middleware import AuthContextMiddleware, DBSessionMiddleware, RawBodyMiddleware, TenantContextMiddleware
from app.api.routes import (
    abdm,
    auth,
    auth_hpr,
    consents,
    emergency_access,
    governance,
    internal,
    internal_consents,
    patients,
    records,
)
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.middleware.idempotency import IdempotencyMiddleware
from app.middleware.emergency_enforcement import EmergencyEnforcementMiddleware
from app.models.user import User
from app.routing.policy import RouteClass, route_policy, validate_route_policies


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_route_policies(app)
    if settings.admin_email and settings.admin_password:
        db: Session = SessionLocal()
        try:
            existing = db.query(User).filter(User.email == settings.admin_email).first()
            if not existing:
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
    yield


app = FastAPI(title=settings.project_name, lifespan=lifespan)

# Starlette prepends middleware; execution order matches the reverse of add_middleware calls.
# Desired execution: TenantContext -> DBSession -> AuthContext -> EmergencyEnforcement -> RawBody -> Idempotency
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RawBodyMiddleware)
app.add_middleware(EmergencyEnforcementMiddleware)
app.add_middleware(AuthContextMiddleware)
app.add_middleware(DBSessionMiddleware)
app.add_middleware(TenantContextMiddleware)

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(auth_hpr.router)
app.include_router(abdm.router)
app.include_router(records.router)
app.include_router(patients.router)
app.include_router(consents.router)
app.include_router(internal_consents.router)
app.include_router(emergency_access.router)
app.include_router(internal.router)
app.include_router(governance.router)


@app.get("/")
@route_policy(
    route_class=RouteClass.SYSTEM,
    tenant_scoped=False,
    phi_access=False,
    decrypts_data=False,
    consent_required=False,
    export_endpoint=False,
    governance_mutation=False,
    abdm_signed_route=False,
    patient_scope_supported=False,
    patient_id_source=None,
    background_capable=False,
    response_static=True,
    allowed_during_emergency=True,
)
def root():
    return {
        "message": "ABDM HIE-CM Integration",
        "detail": "Colposcope imaging backend",
    }
