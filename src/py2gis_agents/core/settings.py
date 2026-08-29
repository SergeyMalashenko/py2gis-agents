"""Environment-backed configuration for the 2GIS client."""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DgisSettings(BaseSettings):
    """Runtime settings loaded without exposing credentials to MCP clients."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str = Field(
        min_length=1,
        validation_alias=AliasChoices("PY2GIS_API_KEY", "DGIS_API_KEY"),
    )
    api_url: str = Field(
        default="https://catalog.api.2gis.com",
        validation_alias=AliasChoices("PY2GIS_API_URL", "DGIS_SEARCH_API_URL"),
    )
    timeout_s: float = Field(
        default=30.0,
        gt=0,
        validation_alias="PY2GIS_TIMEOUT_S",
    )


@lru_cache(maxsize=1)
def get_settings() -> DgisSettings:
    """Load and cache process-level settings."""

    return DgisSettings()
