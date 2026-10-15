from enum import StrEnum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMBackend(StrEnum):
    AGY_CLI = "agy_cli"
    CLAUDE_CLI = "claude_cli"
    CODEX_CLI = "codex_cli"
    OPENHANDS = "openhands"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="LEARNUP_", extra="ignore"
    )

    database_url: str = "duckdb:///learn_up.duckdb"
    db_schema: str = "learn"
    frontend_port: int = 5173
    backend_port: int = 8011
    api_token: str | None = None
    llm_backend: LLMBackend = LLMBackend.AGY_CLI
    agy_cli_model: str | None = None
    claude_cli_model: str = "sonnet"
    llm_model: str = "anthropic/claude-sonnet-4-5"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    notebooklm_profile: str = "default"


@lru_cache
def get_settings() -> Settings:
    return Settings()
