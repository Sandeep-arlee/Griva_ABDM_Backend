from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import session as db_session_module
from app.models.tenant import Tenant
from app.routing.policy import _POLICY_REGISTRY

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
TENANT_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
TENANT_B = uuid.UUID("00000000-0000-0000-0000-000000000002")

event.listen(Session, "do_orm_execute", db_session_module._add_tenant_criteria)
event.listen(Session, "before_flush", db_session_module._set_tenant_id)


@pytest.fixture(scope="session")
def db_engine():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    if "_test" not in (TEST_DATABASE_URL or ""):
        pytest.skip("TEST_DATABASE_URL must point to a _test database")

    settings.database_url = TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    db_session_module.engine = engine
    db_session_module.SessionLocal.configure(bind=engine)

    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    alembic_ini = Path(__file__).resolve().parents[2] / "backend" / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "backend" / "alembic"))
    command.upgrade(cfg, "head")

    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def setup_test_db(db_engine):
    return db_engine


@pytest.fixture(autouse=True)
def _cleanup_db(db_engine):
    with db_engine.begin() as conn:
        tables = conn.execute(
            text(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename <> 'alembic_version';
                """
            )
        ).scalars().all()
        if tables:
            joined = ", ".join(f'"{t}"' for t in tables)
            conn.execute(text(f"TRUNCATE TABLE {joined} CASCADE"))
    yield


@pytest.fixture(autouse=True)
def _reset_policy_registry():
    _POLICY_REGISTRY.clear()
    yield


@pytest.fixture(autouse=True)
def _seed_tenants(db_engine, _cleanup_db):
    db = db_session_module.SessionLocal()
    if not db.query(Tenant).filter(Tenant.id == TENANT_A).first():
        db.add(Tenant(id=TENANT_A, name="Tenant A"))
    if not db.query(Tenant).filter(Tenant.id == TENANT_B).first():
        db.add(Tenant(id=TENANT_B, name="Tenant B"))
    db.commit()
    db.close()


@pytest.fixture()
def db_session(db_engine):
    db = db_session_module.SessionLocal()
    db.info["tenant_id"] = None
    if not db.query(Tenant).filter(Tenant.id == TENANT_A).first():
        db.add(Tenant(id=TENANT_A, name="Tenant A"))
    if not db.query(Tenant).filter(Tenant.id == TENANT_B).first():
        db.add(Tenant(id=TENANT_B, name="Tenant B"))
    db.commit()
    yield db
    db.close()
