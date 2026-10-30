
import secrets
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "NGO Donation Volunteer Community Management API"
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/"
        "ngo_management_system"
    )
    TEST_DATABASE_URL: str = (
        "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/"
        "ngo_management_system_test"
    )

    JWT_SECRET_KEY: SecretStr = Field(
        default=SecretStr(""),
        min_length=32,
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, gt=0)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, gt=0)
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = Field(default=30, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()

        if len(secret) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must contain at least 32 characters."
            )

        if secret == "REPLACE_WITH_A_RANDOM_SECRET_AT_LEAST_32_BYTES_LONG":
            raise ValueError("Replace the example JWT secret in .env.")

        return value

    @field_validator("JWT_ALGORITHM")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        if value != "HS256":
            raise ValueError("Only HS256 is supported by this configuration.")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
