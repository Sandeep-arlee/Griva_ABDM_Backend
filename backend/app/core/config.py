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

    admin_email: str | None = Field(default=None, alias="ADMIN_EMAIL")
    admin_password: str | None = Field(default=None, alias="ADMIN_PASSWORD")
    admin_role: str = Field(default="SUPERADMIN", alias="ADMIN_ROLE")

    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")


settings = Settings()
