"""XiVault configuration and settings."""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    xivault_env: str = "development"
    xivault_api_origin: str = "http://127.0.0.1:8000"
    xivault_jwt_secret: str = "DEV_INSECURE_SECRET_CHANGE_ME_IN_PRODUCTION_MIN_32_BYTES"
    xivault_jwt_issuer: str = "xivault-api"
    xivault_jwt_audience: str = "xivault-extension"

    supabase_url: str = "https://placeholder.supabase.co"
    supabase_service_role_key: str = "placeholder-key"
    database_url: str = "postgresql://localhost:5432/xivault"
    rate_limit_backend_url: str | None = None

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Disallow default insecure secret or short secret in production."""
        if self.xivault_env.lower() == "production":
            if (
                self.xivault_jwt_secret.startswith("DEV_INSECURE_SECRET")
                or len(self.xivault_jwt_secret) < 32
            ):
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: "
                    "Default or insecure JWT secret cannot be used in production. "
                    "Please set XIVAULT_JWT_SECRET to a strong key of at least 32 characters."
                )
        return self


settings = Settings()
