from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/clinical_trials"
    ct_gov_base_url: str = "https://clinicaltrials.gov/api/v2/studies"
    batch_size: int = 500
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def normalize_database_url(self) -> "Settings":
        """Convert Render/standard postgres:// URLs to asyncpg format."""
        url = self.database_url
        if url.startswith("postgres://"):
            self.database_url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            self.database_url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self

    @property
    def sync_database_url(self) -> str:
        """Convert async URL to sync for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "").replace("+aiosqlite", "")


def get_settings() -> Settings:
    return Settings()
