from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from fastapi.routing import APIRoute


class RouteClass(str, Enum):
    SYSTEM = "SYSTEM"
    TENANT_READ = "TENANT_READ"
    TENANT_WRITE = "TENANT_WRITE"
    TENANT_EXPORT = "TENANT_EXPORT"
    GOVERNANCE_MUTATION = "GOVERNANCE_MUTATION"
    ABDM_SIGNED = "ABDM_SIGNED"


class PatientIdSource(str, Enum):
    PATH = "path"
    QUERY = "query"
    BODY = "body"


@dataclass(frozen=True)
class RoutePolicy:
    route_class: RouteClass
    tenant_scoped: bool
    phi_access: bool
    decrypts_data: bool
    consent_required: bool
    export_endpoint: bool
    governance_mutation: bool
    abdm_signed_route: bool
    patient_scope_supported: bool
    patient_id_source: PatientIdSource | None
    background_capable: bool
    response_static: bool
    allowed_during_emergency: bool
    allow_pre_tenant: bool = False

    def validate(self) -> list[str]:
        errors: list[str] = []

        if self.route_class == RouteClass.SYSTEM:
            if self.tenant_scoped:
                errors.append("SYSTEM routes must not be tenant_scoped")
            if self.phi_access:
                errors.append("SYSTEM routes must not access PHI")
            if self.consent_required:
                errors.append("SYSTEM routes must not require consent")
            if self.export_endpoint:
                errors.append("SYSTEM routes must not be export endpoints")
            if self.governance_mutation:
                errors.append("SYSTEM routes must not be governance mutations")
            if self.abdm_signed_route:
                errors.append("SYSTEM routes must not be ABDM signed")
            if self.patient_scope_supported:
                errors.append("SYSTEM routes must not be patient-scoped")

        if self.allow_pre_tenant:
            if self.route_class != RouteClass.SYSTEM:
                errors.append("allow_pre_tenant requires route_class=SYSTEM")
            if self.tenant_scoped:
                errors.append("allow_pre_tenant requires tenant_scoped=False")

        if self.route_class == RouteClass.ABDM_SIGNED:
            if not self.abdm_signed_route:
                errors.append("ABDM_SIGNED routes must set abdm_signed_route=True")
            if self.export_endpoint:
                errors.append("ABDM_SIGNED routes must not be export endpoints")
            if self.governance_mutation:
                errors.append("ABDM_SIGNED routes must not be governance mutations")
            if self.phi_access:
                errors.append("ABDM_SIGNED routes must not be PHI access routes")
            if self.consent_required:
                errors.append("ABDM_SIGNED routes must not require internal consent")
            if not self.tenant_scoped:
                errors.append("ABDM_SIGNED routes must be tenant_scoped")

        if self.route_class in {RouteClass.TENANT_READ, RouteClass.TENANT_WRITE, RouteClass.TENANT_EXPORT}:
            if not self.tenant_scoped:
                errors.append("TENANT_* routes must be tenant_scoped")

        if self.route_class == RouteClass.TENANT_EXPORT:
            if not self.export_endpoint:
                errors.append("TENANT_EXPORT routes must set export_endpoint=True")
            if not self.phi_access:
                errors.append("TENANT_EXPORT routes must be PHI access routes")
            if not self.consent_required:
                errors.append("TENANT_EXPORT routes must require consent")

        if self.export_endpoint and self.route_class != RouteClass.TENANT_EXPORT:
            errors.append("export_endpoint requires route_class=TENANT_EXPORT")

        if self.governance_mutation and self.route_class != RouteClass.GOVERNANCE_MUTATION:
            errors.append("governance_mutation requires route_class=GOVERNANCE_MUTATION")

        if self.route_class == RouteClass.GOVERNANCE_MUTATION:
            if not self.governance_mutation:
                errors.append("GOVERNANCE_MUTATION routes must set governance_mutation=True")
            if not self.tenant_scoped:
                errors.append("GOVERNANCE_MUTATION routes must be tenant_scoped")
            if self.allowed_during_emergency:
                errors.append("GOVERNANCE_MUTATION routes must be denied during emergency")

        if self.abdm_signed_route and self.route_class != RouteClass.ABDM_SIGNED:
            errors.append("abdm_signed_route requires route_class=ABDM_SIGNED")

        if self.phi_access:
            if not self.tenant_scoped:
                errors.append("PHI access routes must be tenant_scoped")
            if not self.consent_required:
                errors.append("PHI access routes must require consent")
        if self.consent_required and not self.phi_access:
            errors.append("consent_required requires phi_access=True")

        if self.decrypts_data and not self.phi_access:
            errors.append("decrypts_data requires phi_access=True")
        if self.decrypts_data and not self.tenant_scoped:
            errors.append("decrypts_data requires tenant_scoped=True")

        if self.background_capable and not self.tenant_scoped:
            errors.append("background_capable requires tenant_scoped=True")

        if self.patient_scope_supported:
            if not self.phi_access:
                errors.append("patient_scope_supported requires phi_access=True")
            if not self.tenant_scoped:
                errors.append("patient_scope_supported requires tenant_scoped=True")
            if self.patient_id_source is None:
                errors.append("patient_scope_supported requires patient_id_source")
        else:
            if self.patient_id_source is not None:
                errors.append("patient_id_source must be None when patient_scope_supported=False")

        return errors


def route_policy(**kwargs):
    policy = RoutePolicy(**kwargs)

    def decorator(func):
        setattr(func, "__route_policy__", policy)
        return func

    return decorator


_POLICY_REGISTRY: dict[str, RoutePolicy] = {}
POLICY_REGISTRY: MappingProxyType[str, RoutePolicy] = MappingProxyType(_POLICY_REGISTRY)


def _should_skip_route(route: APIRoute) -> bool:
    if not isinstance(route, APIRoute):
        return True
    if route.path in {"/docs", "/redoc", "/openapi.json"}:
        return True
    return False


def validate_route_policies(app) -> None:
    from app.api import deps

    errors: list[str] = []

    def _has_dependency(dep, target) -> bool:
        if dep.call is target:
            return True
        for child in dep.dependencies:
            if _has_dependency(child, target):
                return True
        return False

    for route in app.routes:
        if _should_skip_route(route):
            continue
        policy: RoutePolicy | None = getattr(route.endpoint, "__route_policy__", None)
        if policy is None:
            errors.append(f"{route.path} missing RoutePolicy")
            continue
        if route.name in _POLICY_REGISTRY:
            errors.append(f"{route.path} duplicate RoutePolicy registration")
        else:
            _POLICY_REGISTRY[route.name] = policy

        policy_errors = policy.validate()
        if policy_errors:
            for err in policy_errors:
                errors.append(f"{route.path} invalid policy: {err}")

        if policy.tenant_scoped:
            has_db_dep = _has_dependency(route.dependant, deps.get_db)
            if not has_db_dep:
                errors.append(f"{route.path} tenant_scoped route must depend on get_db")
            has_user_dep = _has_dependency(route.dependant, deps.get_current_user)
            if not has_user_dep:
                errors.append(f"{route.path} tenant_scoped route must depend on get_current_user")
        if policy.allow_pre_tenant:
            has_user_dep = _has_dependency(route.dependant, deps.get_current_user)
            if not has_user_dep:
                errors.append(f"{route.path} allow_pre_tenant route must depend on get_current_user")

    if errors:
        joined = "; ".join(errors)
        raise RuntimeError(f"RoutePolicy validation failed: {joined}")
