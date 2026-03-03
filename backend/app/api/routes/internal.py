from fastapi import APIRouter, Depends
from app.api.deps import require_roles
from app.routing.policy import RouteClass, route_policy
from app.security.metrics import security_metrics

router = APIRouter(tags=["internal"])


@router.get("/internal/metrics")
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
def get_metrics(
    _user=Depends(require_roles("SUPERADMIN", require_emergency_session=False)),
):
    return security_metrics.snapshot()
