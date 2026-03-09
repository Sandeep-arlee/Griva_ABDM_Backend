from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    project_name: str = "ABDM Colposcopy Backend"
    api_v1_str: str = ""

    database_url: str = Field(
    default="postgresql+psycopg://griva:griva123@localhost:5432/griva",
    alias="DATABASE_URL",
    )

    secret_key: str = Field(default="change-me", alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    pre_tenant_token_expire_seconds: int = Field(default=300, alias="PRE_TENANT_TOKEN_EXPIRE_SECONDS")

    hpr_oauth_auth_url: str = Field(default="", alias="HPR_OAUTH_AUTH_URL")
    hpr_oauth_token_url: str = Field(default="", alias="HPR_OAUTH_TOKEN_URL")
    hpr_oauth_jwks_url: str = Field(default="", alias="HPR_OAUTH_JWKS_URL")
    hpr_oauth_client_id: str = Field(default="", alias="HPR_OAUTH_CLIENT_ID")
    hpr_oauth_client_secret: str = Field(default="", alias="HPR_OAUTH_CLIENT_SECRET")
    hpr_oauth_redirect_uri: str = Field(default="", alias="HPR_OAUTH_REDIRECT_URI")
    hpr_oauth_issuer: str = Field(default="", alias="HPR_OAUTH_ISSUER")
    hpr_oauth_scopes: str = Field(default="openid", alias="HPR_OAUTH_SCOPES")
    hpr_oauth_state_cookie_name: str = Field(
        default="griva_hpr_oauth_state",
        alias="HPR_OAUTH_STATE_COOKIE_NAME",
    )
    hpr_oauth_state_ttl_seconds: int = Field(default=300, alias="HPR_OAUTH_STATE_TTL_SECONDS")
    hpr_oauth_clock_skew_seconds: int = Field(default=60, alias="HPR_OAUTH_CLOCK_SKEW_SECONDS")
    hpr_oauth_cookie_secure: bool = Field(default=True, alias="HPR_OAUTH_COOKIE_SECURE")

    platform_identity_key_b64: str = Field(default="", alias="PLATFORM_IDENTITY_KEY_B64")
    platform_identity_key_id: str = Field(default="1", alias="PLATFORM_IDENTITY_KEY_ID")
    tenant_master_key_b64: str = Field(default="", alias="TENANT_MASTER_KEY_B64")

    admin_email: str | None = Field(default=None, alias="ADMIN_EMAIL")
    admin_password: str | None = Field(default=None, alias="ADMIN_PASSWORD")
    admin_role: str = Field(default="SUPERADMIN", alias="ADMIN_ROLE")

    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    abdm_private_key_pem: str = Field(default="", alias="ABDM_PRIVATE_KEY_PEM")
    abdm_key_id: str = Field(default="", alias="ABDM_KEY_ID")
    abdm_timestamp_tolerance_seconds: int = Field(default=300, alias="ABDM_TIMESTAMP_TOLERANCE_SECONDS")
    strict_tenant_mode: bool = Field(default=True, alias="STRICT_TENANT_MODE")
    emergency_access_max_minutes: int = Field(default=60, alias="EMERGENCY_ACCESS_MAX_MINUTES")
    emergency_access_min_reason_length: int = Field(default=10, alias="EMERGENCY_ACCESS_MIN_REASON_LENGTH")
    emergency_access_enabled: bool = Field(default=True, alias="EMERGENCY_ACCESS_ENABLED")
    emergency_max_decrypts_per_session: int = Field(
        default=500, alias="EMERGENCY_MAX_DECRYPTS_PER_SESSION"
    )
    emergency_max_export_records_per_request: int = Field(
        default=1000, alias="EMERGENCY_MAX_EXPORT_RECORDS_PER_REQUEST"
    )
    emergency_max_export_records_per_session: int = Field(
        default=5000, alias="EMERGENCY_MAX_EXPORT_RECORDS_PER_SESSION"
    )
    emergency_max_export_payload_bytes_per_session: int = Field(
        default=100 * 1024 * 1024,
        alias="EMERGENCY_MAX_EXPORT_PAYLOAD_BYTES_PER_SESSION",
    )


settings = Settings()
