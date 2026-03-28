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
        """Convert Render/Fly.io postgres:// URLs to asyncpg format."""
        url = self.database_url
        # Strip sslmode param — asyncpg uses ssl=True/False instead
        if "?" in url:
            base, query = url.split("?", 1)
            params = [p for p in query.split("&") if not p.startswith("sslmode=")]
            url = f"{base}?{'&'.join(params)}" if params else base
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        self.database_url = url
        return self

    @property
    def sync_database_url(self) -> str:
        """Convert async URL to sync for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "").replace("+aiosqlite", "")


def get_settings() -> Settings:
    return Settings()
