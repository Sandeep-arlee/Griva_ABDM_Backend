-- Generated via:
-- pg_dump --schema-only --no-owner --no-privileges -h localhost -U griva -d griva > docs/schema_snapshot.sql

--
-- PostgreSQL database dump
--

\restrict FKBgUFALQOfwBJEQMIvtDSM6iucYSRWIvVUrtzylZKl73Q26DJ3RnVK76IOMjPC

-- Dumped from database version 16.11 (Ubuntu 16.11-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.11 (Ubuntu 16.11-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: btree_gist; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;


--
-- Name: EXTENSION btree_gist; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION btree_gist IS 'support for indexing common datatypes in GiST';


--
-- Name: consent_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.consent_status AS ENUM (
    'REQUESTED',
    'GRANTED',
    'REVOKED',
    'EXPIRED',
    'DENIED'
);


--
-- Name: hi_request_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.hi_request_status AS ENUM (
    'REQUESTED',
    'PROCESSING',
    'COMPLETED',
    'FAILED'
);


--
-- Name: prevent_emergency_event_modification_v2(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_emergency_event_modification_v2() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            RAISE EXCEPTION 'Emergency audit events are immutable';
        END;
        $$;


--
-- Name: prevent_emergency_identity_update_v2(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_emergency_identity_update_v2() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
               OR NEW.super_admin_id IS DISTINCT FROM OLD.super_admin_id
               OR NEW.scope_type IS DISTINCT FROM OLD.scope_type
               OR NEW.scope_patient_id IS DISTINCT FROM OLD.scope_patient_id
               OR NEW.approved_at IS DISTINCT FROM OLD.approved_at
               OR NEW.expires_at IS DISTINCT FROM OLD.expires_at
               OR NEW.requested_at IS DISTINCT FROM OLD.requested_at THEN
                RAISE EXCEPTION 'Immutable emergency session identity fields cannot be updated';
            END IF;
            RETURN NEW;
        END;
        $$;


--
-- Name: prevent_emergency_session_delete_v2(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_emergency_session_delete_v2() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            RAISE EXCEPTION 'Emergency sessions are immutable and cannot be deleted';
        END;
        $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    id uuid NOT NULL,
    event_type character varying NOT NULL,
    request_id character varying NOT NULL,
    hip_id character varying,
    hiu_id character varying,
    cm_id character varying,
    consent_id character varying,
    status_code integer NOT NULL,
    meta jsonb NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL
);


--
-- Name: consent_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.consent_events (
    id uuid NOT NULL,
    consent_id uuid NOT NULL,
    event_type public.consent_status NOT NULL,
    event_payload jsonb NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now(),
    tenant_id uuid
);


--
-- Name: consent_grants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.consent_grants (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    internal_consent_id uuid NOT NULL,
    granted_by_user_id uuid NOT NULL,
    scope jsonb NOT NULL,
    granted_at timestamp with time zone DEFAULT now()
);


--
-- Name: consent_revocations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.consent_revocations (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    internal_consent_id uuid NOT NULL,
    revoked_by_user_id uuid NOT NULL,
    reason character varying NOT NULL,
    meta jsonb NOT NULL,
    revoked_at timestamp with time zone DEFAULT now()
);


--
-- Name: consents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.consents (
    id uuid NOT NULL,
    abdm_consent_id character varying NOT NULL,
    patient_id character varying NOT NULL,
    hiu_id character varying NOT NULL,
    hip_id character varying NOT NULL,
    status public.consent_status NOT NULL,
    valid_from timestamp with time zone NOT NULL,
    valid_to timestamp with time zone NOT NULL,
    raw_payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    tenant_id uuid NOT NULL
);


--
-- Name: emergency_access_events_v2; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emergency_access_events_v2 (
    id uuid NOT NULL,
    session_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    super_admin_id uuid NOT NULL,
    event_type text NOT NULL,
    resource_type text,
    resource_id uuid,
    record_count integer,
    payload_size_bytes bigint,
    ip inet NOT NULL,
    user_agent text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_emergency_access_events_v2_type CHECK ((event_type = ANY (ARRAY['REQUESTED'::text, 'APPROVED'::text, 'USED'::text, 'EXPORT'::text, 'DECRYPT'::text, 'REVOKED'::text, 'EXPIRED'::text])))
);


--
-- Name: emergency_access_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emergency_access_sessions (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    super_admin_id uuid NOT NULL,
    reason text NOT NULL,
    approved_by uuid,
    approved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    CONSTRAINT ck_emergency_access_sessions_expires_after_created CHECK ((expires_at > created_at))
);


--
-- Name: emergency_access_sessions_v2; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emergency_access_sessions_v2 (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    super_admin_id uuid NOT NULL,
    scope_type text NOT NULL,
    scope_patient_id uuid,
    reason text NOT NULL,
    requested_at timestamp with time zone DEFAULT now() NOT NULL,
    approved_at timestamp with time zone NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    created_ip inet NOT NULL,
    created_user_agent text NOT NULL,
    decrypt_count integer DEFAULT 0 NOT NULL,
    export_count integer DEFAULT 0 NOT NULL,
    export_payload_bytes bigint DEFAULT '0'::bigint NOT NULL,
    last_used_at timestamp with time zone,
    CONSTRAINT ck_emergency_access_sessions_v2_duration CHECK ((expires_at <= (approved_at + '01:00:00'::interval))),
    CONSTRAINT ck_emergency_access_sessions_v2_scope CHECK ((((scope_type = 'TENANT_WIDE'::text) AND (scope_patient_id IS NULL)) OR ((scope_type = 'PATIENT_SCOPED'::text) AND (scope_patient_id IS NOT NULL)))),
    CONSTRAINT ck_emergency_access_sessions_v2_time_order CHECK ((expires_at > approved_at))
);


--
-- Name: health_information_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.health_information_events (
    id uuid NOT NULL,
    health_information_request_id uuid NOT NULL,
    event_type character varying NOT NULL,
    event_payload jsonb NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now(),
    tenant_id uuid NOT NULL
);


--
-- Name: health_information_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.health_information_requests (
    id uuid NOT NULL,
    request_id character varying NOT NULL,
    consent_id uuid NOT NULL,
    hip_id character varying NOT NULL,
    hiu_id character varying NOT NULL,
    status public.hi_request_status NOT NULL,
    date_range jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    tenant_id uuid NOT NULL
);


--
-- Name: internal_consents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.internal_consents (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    subject_patient_id character varying NOT NULL,
    purpose character varying NOT NULL,
    status character varying DEFAULT 'GRANTED'::character varying NOT NULL,
    metadata jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: medical_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.medical_records (
    id uuid NOT NULL,
    patient_id character varying NOT NULL,
    record_type character varying NOT NULL,
    uri character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    tenant_id uuid NOT NULL
);


--
-- Name: patient_abha_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patient_abha_links (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    patient_id uuid NOT NULL,
    abha_address_enc json,
    abha_number_enc json,
    abha_hash character varying NOT NULL,
    link_status character varying DEFAULT 'VERIFIED'::character varying NOT NULL,
    verified_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


--
-- Name: patients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patients (
    id uuid NOT NULL,
    patient_id character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid
);


--
-- Name: tenant_keys; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenant_keys (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    encrypted_dek character varying NOT NULL,
    key_version character varying,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: tenants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenants (
    id uuid NOT NULL,
    name character varying NOT NULL,
    status character varying DEFAULT 'ACTIVE'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: trusted_keys; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trusted_keys (
    id uuid NOT NULL,
    key_id character varying NOT NULL,
    public_key character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    is_active boolean DEFAULT true NOT NULL,
    tenant_id uuid
);


--
-- Name: trusted_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trusted_requests (
    id uuid NOT NULL,
    request_id character varying NOT NULL,
    signature character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    tenant_id uuid
);


--
-- Name: user_tenant_memberships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_tenant_memberships (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    role character varying NOT NULL,
    status character varying DEFAULT 'ACTIVE'::character varying NOT NULL,
    joined_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_user_tenant_membership_status CHECK (((status)::text = ANY ((ARRAY['ACTIVE'::character varying, 'INVITED'::character varying, 'SUSPENDED'::character varying])::text[])))
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    email character varying,
    hashed_password character varying,
    role character varying,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    tenant_id uuid,
    hpr_id character varying,
    hpr_verified_at timestamp with time zone,
    hpr_profile_enc jsonb,
    status character varying DEFAULT 'ACTIVE'::character varying NOT NULL,
    CONSTRAINT ck_users_identity_present CHECK (((email IS NOT NULL) OR (hpr_id IS NOT NULL))),
    CONSTRAINT ck_users_status CHECK (((status)::text = ANY ((ARRAY['ACTIVE'::character varying, 'DISABLED'::character varying])::text[])))
);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: consent_events consent_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_events
    ADD CONSTRAINT consent_events_pkey PRIMARY KEY (id);


--
-- Name: consent_grants consent_grants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_grants
    ADD CONSTRAINT consent_grants_pkey PRIMARY KEY (id);


--
-- Name: consent_revocations consent_revocations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_revocations
    ADD CONSTRAINT consent_revocations_pkey PRIMARY KEY (id);


--
-- Name: consents consents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consents
    ADD CONSTRAINT consents_pkey PRIMARY KEY (id);


--
-- Name: emergency_access_events_v2 emergency_access_events_v2_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_access_events_v2
    ADD CONSTRAINT emergency_access_events_v2_pkey PRIMARY KEY (id);


--
-- Name: emergency_access_sessions emergency_access_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_access_sessions
    ADD CONSTRAINT emergency_access_sessions_pkey PRIMARY KEY (id);


--
-- Name: emergency_access_sessions_v2 emergency_access_sessions_v2_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_access_sessions_v2
    ADD CONSTRAINT emergency_access_sessions_v2_pkey PRIMARY KEY (id);


--
-- Name: emergency_access_sessions emergency_no_overlap; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_access_sessions
    ADD CONSTRAINT emergency_no_overlap EXCLUDE USING gist (tenant_id WITH =, super_admin_id WITH =, tstzrange(created_at, expires_at) WITH &&) WHERE ((revoked_at IS NULL));


--
-- Name: emergency_access_sessions_v2 emergency_no_overlap_v2; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_access_sessions_v2
    ADD CONSTRAINT emergency_no_overlap_v2 EXCLUDE USING gist (tenant_id WITH =, super_admin_id WITH =, tstzrange(approved_at, expires_at) WITH &&) WHERE ((revoked_at IS NULL));


--
-- Name: health_information_events health_information_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_information_events
    ADD CONSTRAINT health_information_events_pkey PRIMARY KEY (id);


--
-- Name: health_information_requests health_information_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_information_requests
    ADD CONSTRAINT health_information_requests_pkey PRIMARY KEY (id);


--
-- Name: internal_consents internal_consents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.internal_consents
    ADD CONSTRAINT internal_consents_pkey PRIMARY KEY (id);


--
-- Name: medical_records medical_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medical_records
    ADD CONSTRAINT medical_records_pkey PRIMARY KEY (id);


--
-- Name: patient_abha_links patient_abha_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_abha_links
    ADD CONSTRAINT patient_abha_links_pkey PRIMARY KEY (id);


--
-- Name: patients patients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT patients_pkey PRIMARY KEY (id);


--
-- Name: tenant_keys tenant_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_keys
    ADD CONSTRAINT tenant_keys_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: trusted_keys trusted_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trusted_keys
    ADD CONSTRAINT trusted_keys_pkey PRIMARY KEY (id);


--
-- Name: trusted_requests trusted_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trusted_requests
    ADD CONSTRAINT trusted_requests_pkey PRIMARY KEY (id);


--
-- Name: user_tenant_memberships uq_user_tenant; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tenant_memberships
    ADD CONSTRAINT uq_user_tenant UNIQUE (user_id, tenant_id);


--
-- Name: users uq_users_hpr_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT uq_users_hpr_id UNIQUE (hpr_id);


--
-- Name: user_tenant_memberships user_tenant_memberships_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tenant_memberships
    ADD CONSTRAINT user_tenant_memberships_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_emergency_events_v2_created_desc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_emergency_events_v2_created_desc ON public.emergency_access_events_v2 USING btree (created_at DESC);


--
-- Name: idx_emergency_events_v2_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_emergency_events_v2_session ON public.emergency_access_events_v2 USING btree (session_id);


--
-- Name: idx_emergency_events_v2_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_emergency_events_v2_tenant ON public.emergency_access_events_v2 USING btree (tenant_id);


--
-- Name: idx_emergency_events_v2_tenant_created_desc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_emergency_events_v2_tenant_created_desc ON public.emergency_access_events_v2 USING btree (tenant_id, created_at DESC, id DESC);


--
-- Name: idx_emergency_events_v2_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_emergency_events_v2_type ON public.emergency_access_events_v2 USING btree (event_type);


--
-- Name: idx_emergency_sessions_v2_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_emergency_sessions_v2_active ON public.emergency_access_sessions_v2 USING btree (tenant_id) WHERE (revoked_at IS NULL);


--
-- Name: idx_emergency_sessions_v2_admin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_emergency_sessions_v2_admin ON public.emergency_access_sessions_v2 USING btree (super_admin_id);


--
-- Name: idx_emergency_sessions_v2_expiry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_emergency_sessions_v2_expiry ON public.emergency_access_sessions_v2 USING btree (expires_at);


--
-- Name: idx_emergency_sessions_v2_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_emergency_sessions_v2_tenant ON public.emergency_access_sessions_v2 USING btree (tenant_id);


--
-- Name: ix_abha_links_tenant_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_abha_links_tenant_hash ON public.patient_abha_links USING btree (tenant_id, abha_hash);


--
-- Name: ix_audit_logs_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_tenant_id ON public.audit_logs USING btree (tenant_id);


--
-- Name: ix_audit_logs_tenant_id_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_tenant_id_request_id ON public.audit_logs USING btree (tenant_id, request_id);


--
-- Name: ix_consent_events_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_consent_events_tenant_id ON public.consent_events USING btree (tenant_id);


--
-- Name: ix_consent_events_tenant_id_consent_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_consent_events_tenant_id_consent_id ON public.consent_events USING btree (tenant_id, consent_id);


--
-- Name: ix_consent_grants_internal_consent_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_consent_grants_internal_consent_id ON public.consent_grants USING btree (internal_consent_id);


--
-- Name: ix_consent_grants_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_consent_grants_tenant_id ON public.consent_grants USING btree (tenant_id);


--
-- Name: ix_consent_revocations_internal_consent_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_consent_revocations_internal_consent_id ON public.consent_revocations USING btree (internal_consent_id);


--
-- Name: ix_consent_revocations_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_consent_revocations_tenant_id ON public.consent_revocations USING btree (tenant_id);


--
-- Name: ix_consents_abdm_consent_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_consents_abdm_consent_id ON public.consents USING btree (abdm_consent_id);


--
-- Name: ix_consents_patient_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_consents_patient_id ON public.consents USING btree (patient_id);


--
-- Name: ix_consents_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_consents_tenant_id ON public.consents USING btree (tenant_id);


--
-- Name: ix_consents_tenant_id_abdm_consent_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_consents_tenant_id_abdm_consent_id ON public.consents USING btree (tenant_id, abdm_consent_id);


--
-- Name: ix_emergency_access_sessions_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_access_sessions_expires_at ON public.emergency_access_sessions USING btree (expires_at);


--
-- Name: ix_emergency_access_sessions_tenant_admin_expires; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_access_sessions_tenant_admin_expires ON public.emergency_access_sessions USING btree (tenant_id, super_admin_id, expires_at);


--
-- Name: ix_health_information_requests_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_health_information_requests_request_id ON public.health_information_requests USING btree (request_id);


--
-- Name: ix_hi_events_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hi_events_tenant_id ON public.health_information_events USING btree (tenant_id);


--
-- Name: ix_hi_events_tenant_id_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hi_events_tenant_id_request_id ON public.health_information_events USING btree (tenant_id, health_information_request_id);


--
-- Name: ix_hi_requests_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hi_requests_tenant_id ON public.health_information_requests USING btree (tenant_id);


--
-- Name: ix_hi_requests_tenant_id_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hi_requests_tenant_id_request_id ON public.health_information_requests USING btree (tenant_id, request_id);


--
-- Name: ix_internal_consents_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_internal_consents_tenant_id ON public.internal_consents USING btree (tenant_id);


--
-- Name: ix_internal_consents_tenant_id_patient_purpose; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_internal_consents_tenant_id_patient_purpose ON public.internal_consents USING btree (tenant_id, subject_patient_id, purpose);


--
-- Name: ix_medical_records_patient_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_medical_records_patient_id ON public.medical_records USING btree (patient_id);


--
-- Name: ix_medical_records_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_medical_records_tenant_id ON public.medical_records USING btree (tenant_id);


--
-- Name: ix_medical_records_tenant_id_patient_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_medical_records_tenant_id_patient_id ON public.medical_records USING btree (tenant_id, patient_id);


--
-- Name: ix_patients_patient_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_patients_patient_id ON public.patients USING btree (patient_id);


--
-- Name: ix_patients_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_patients_tenant_id ON public.patients USING btree (tenant_id);


--
-- Name: ix_patients_tenant_id_patient_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_patients_tenant_id_patient_id ON public.patients USING btree (tenant_id, patient_id);


--
-- Name: ix_tenant_keys_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tenant_keys_tenant_id ON public.tenant_keys USING btree (tenant_id);


--
-- Name: ix_tenant_keys_tenant_id_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tenant_keys_tenant_id_active ON public.tenant_keys USING btree (tenant_id, is_active);


--
-- Name: ix_tenants_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_tenants_name ON public.tenants USING btree (name);


--
-- Name: ix_trusted_keys_key_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_trusted_keys_key_id ON public.trusted_keys USING btree (key_id);


--
-- Name: ix_trusted_keys_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trusted_keys_tenant_id ON public.trusted_keys USING btree (tenant_id);


--
-- Name: ix_trusted_keys_tenant_id_key_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trusted_keys_tenant_id_key_id ON public.trusted_keys USING btree (tenant_id, key_id);


--
-- Name: ix_trusted_requests_request_id_signature; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_trusted_requests_request_id_signature ON public.trusted_requests USING btree (request_id, signature);


--
-- Name: ix_trusted_requests_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trusted_requests_tenant_id ON public.trusted_requests USING btree (tenant_id);


--
-- Name: ix_trusted_requests_tenant_id_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trusted_requests_tenant_id_request_id ON public.trusted_requests USING btree (tenant_id, request_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_tenant_id ON public.users USING btree (tenant_id);


--
-- Name: ix_users_tenant_id_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_tenant_id_email ON public.users USING btree (tenant_id, email);


--
-- Name: emergency_access_sessions_v2 trg_no_delete_emergency_sessions_v2; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_no_delete_emergency_sessions_v2 BEFORE DELETE ON public.emergency_access_sessions_v2 FOR EACH ROW EXECUTE FUNCTION public.prevent_emergency_session_delete_v2();


--
-- Name: emergency_access_events_v2 trg_prevent_event_modification_v2; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_prevent_event_modification_v2 BEFORE DELETE OR UPDATE ON public.emergency_access_events_v2 FOR EACH ROW EXECUTE FUNCTION public.prevent_emergency_event_modification_v2();


--
-- Name: emergency_access_sessions_v2 trg_prevent_identity_update_v2; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_prevent_identity_update_v2 BEFORE UPDATE ON public.emergency_access_sessions_v2 FOR EACH ROW EXECUTE FUNCTION public.prevent_emergency_identity_update_v2();


--
-- Name: consent_events consent_events_consent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_events
    ADD CONSTRAINT consent_events_consent_id_fkey FOREIGN KEY (consent_id) REFERENCES public.consents(id);


--
-- Name: consent_grants consent_grants_granted_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_grants
    ADD CONSTRAINT consent_grants_granted_by_user_id_fkey FOREIGN KEY (granted_by_user_id) REFERENCES public.users(id);


--
-- Name: consent_grants consent_grants_internal_consent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_grants
    ADD CONSTRAINT consent_grants_internal_consent_id_fkey FOREIGN KEY (internal_consent_id) REFERENCES public.internal_consents(id);


--
-- Name: consent_grants consent_grants_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_grants
    ADD CONSTRAINT consent_grants_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: consent_revocations consent_revocations_internal_consent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_revocations
    ADD CONSTRAINT consent_revocations_internal_consent_id_fkey FOREIGN KEY (internal_consent_id) REFERENCES public.internal_consents(id);


--
-- Name: consent_revocations consent_revocations_revoked_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_revocations
    ADD CONSTRAINT consent_revocations_revoked_by_user_id_fkey FOREIGN KEY (revoked_by_user_id) REFERENCES public.users(id);


--
-- Name: consent_revocations consent_revocations_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_revocations
    ADD CONSTRAINT consent_revocations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: emergency_access_events_v2 emergency_access_events_v2_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_access_events_v2
    ADD CONSTRAINT emergency_access_events_v2_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.emergency_access_sessions_v2(id) ON DELETE RESTRICT;


--
-- Name: emergency_access_events_v2 emergency_access_events_v2_super_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_access_events_v2
    ADD CONSTRAINT emergency_access_events_v2_super_admin_id_fkey FOREIGN KEY (super_admin_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: emergency_access_events_v2 emergency_access_events_v2_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_access_events_v2
    ADD CONSTRAINT emergency_access_events_v2_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: emergency_access_sessions emergency_access_sessions_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_access_sessions
    ADD CONSTRAINT emergency_access_sessions_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.users(id);


--
-- Name: emergency_access_sessions emergency_access_sessions_super_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_access_sessions
    ADD CONSTRAINT emergency_access_sessions_super_admin_id_fkey FOREIGN KEY (super_admin_id) REFERENCES public.users(id);


--
-- Name: emergency_access_sessions emergency_access_sessions_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_access_sessions
    ADD CONSTRAINT emergency_access_sessions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: emergency_access_sessions_v2 emergency_access_sessions_v2_super_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_access_sessions_v2
    ADD CONSTRAINT emergency_access_sessions_v2_super_admin_id_fkey FOREIGN KEY (super_admin_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: emergency_access_sessions_v2 emergency_access_sessions_v2_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_access_sessions_v2
    ADD CONSTRAINT emergency_access_sessions_v2_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: audit_logs fk_audit_logs_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT fk_audit_logs_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: consent_events fk_consent_events_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_events
    ADD CONSTRAINT fk_consent_events_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: consents fk_consents_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consents
    ADD CONSTRAINT fk_consents_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: health_information_events fk_hi_events_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_information_events
    ADD CONSTRAINT fk_hi_events_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: health_information_requests fk_hi_requests_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_information_requests
    ADD CONSTRAINT fk_hi_requests_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: medical_records fk_medical_records_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medical_records
    ADD CONSTRAINT fk_medical_records_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: patients fk_patients_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT fk_patients_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: trusted_keys fk_trusted_keys_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trusted_keys
    ADD CONSTRAINT fk_trusted_keys_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: trusted_requests fk_trusted_requests_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trusted_requests
    ADD CONSTRAINT fk_trusted_requests_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: users fk_users_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: health_information_events health_information_events_health_information_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_information_events
    ADD CONSTRAINT health_information_events_health_information_request_id_fkey FOREIGN KEY (health_information_request_id) REFERENCES public.health_information_requests(id);


--
-- Name: health_information_requests health_information_requests_consent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_information_requests
    ADD CONSTRAINT health_information_requests_consent_id_fkey FOREIGN KEY (consent_id) REFERENCES public.consents(id);


--
-- Name: internal_consents internal_consents_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.internal_consents
    ADD CONSTRAINT internal_consents_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: patient_abha_links patient_abha_links_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_abha_links
    ADD CONSTRAINT patient_abha_links_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patients(id);


--
-- Name: patient_abha_links patient_abha_links_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_abha_links
    ADD CONSTRAINT patient_abha_links_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: tenant_keys tenant_keys_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_keys
    ADD CONSTRAINT tenant_keys_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: user_tenant_memberships user_tenant_memberships_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tenant_memberships
    ADD CONSTRAINT user_tenant_memberships_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: user_tenant_memberships user_tenant_memberships_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tenant_memberships
    ADD CONSTRAINT user_tenant_memberships_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- PostgreSQL database dump complete
--

\unrestrict FKBgUFALQOfwBJEQMIvtDSM6iucYSRWIvVUrtzylZKl73Q26DJ3RnVK76IOMjPC

