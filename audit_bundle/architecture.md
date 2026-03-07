# ABDM HIP Backend Architecture

## Overview
Production-grade Health Information Provider backend designed to support consent-based health data exchange within the ABDM ecosystem.

## Technology Stack
FastAPI
SQLAlchemy ORM
PostgreSQL
Alembic migrations
JWT authentication

## Core Services
API Layer
Consent Lifecycle Management
Audit Logging
Tenant Isolation

## Data Model
Key tables:
consents
consent_events
audit_logs
patients
medical_records

## Consent Lifecycle
Consent creation
Consent approval or rejection
Consent revocation
Immutable consent event history

## Security Model
JWT validation
Tenant isolation via tenant_id
Immutable audit logs
PHI stored securely in PostgreSQL

## External Integrations
ABDM registries
Facility registry
Future consent gateway callbacks
