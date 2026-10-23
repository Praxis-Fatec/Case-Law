from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/caselaw"
    environment: str = "development"
    root_path: str = ""
    database_pool_size: int = 10
    search_max_page_size: int = 100
    # The PDF spike measured up to 1,000 decisions. Allow a lower deployment
    # limit, but require another measurement before increasing this ceiling.
    export_max_decisions: int = Field(default=1000, ge=1, le=1000)
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_comma_separated(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()
