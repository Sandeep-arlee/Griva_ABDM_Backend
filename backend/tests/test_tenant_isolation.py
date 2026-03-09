import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.main import app
from app.models.internal_consent import InternalConsent
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.security.user_context import AuthenticatedUser
from app.tenancy import get_current_tenant_id


TENANT_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
TENANT_B = uuid.UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture()
def client(db_session):
    def _get_db_override():
        tenant_id = get_current_tenant_id()
        if tenant_id:
            db_session.info["tenant_id"] = tenant_id
        try:
            yield db_session
        finally:
            db_session.info.pop("tenant_id", None)

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=uuid.uuid4(),
        role="ADMIN",
        tenant_id=str(TENANT_B),
        membership_id="mem-1",
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_tenant_a_records_not_visible_in_tenant_b(client, db_session):
    patient_id = "patient-iso-1"
    db_session.info["tenant_id"] = TENANT_A
    patient = Patient(tenant_id=TENANT_A, patient_id=patient_id)
    db_session.add(patient)
    db_session.flush()
    db_session.add(
        MedicalRecord(
            tenant_id=TENANT_A,
            patient_id=patient_id,
            record_type="OPConsultation",
            uri="s3://record-a",
        )
    )
    db_session.commit()

    db_session.info["tenant_id"] = TENANT_B
    db_session.add(
        InternalConsent(
            tenant_id=TENANT_B,
            subject_patient_id=patient_id,
            purpose="CARE",
            status="GRANTED",
            meta={},
        )
    )
    db_session.commit()
    db_session.info.pop("tenant_id", None)

    resp = client.get(
        f"/api/patients/{patient_id}/records",
        headers={"X-Tenant-ID": str(TENANT_B)},
    )
    assert resp.status_code in (200, 403)
    if resp.status_code == 200:
        assert resp.json() == []
