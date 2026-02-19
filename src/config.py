from enum import Enum
from pathlib import Path

from pydantic_settings import BaseSettings


class AppMode(str, Enum):
    SIMPLE = "simple"
    EXTENDED = "extended"


class Settings(BaseSettings):
    mode: AppMode = AppMode.SIMPLE

    klaviyo_api_key: str = ""
    klaviyo_list_id: str = ""
    klaviyo_api_revision: str = "2024-10-15"

    webhook_secret: str = ""

    database_url: str = "sqlite:///./data/intentions.db"

    log_level: str = "INFO"

    # Scheduler: uur waarop dagelijkse sync draait (0 = middernacht)
    daily_sync_hour: int = 0

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    @property
    def db_path(self) -> Path:
        """Geeft het SQLite bestandspad terug."""
        url = self.database_url.replace("sqlite:///", "")
        return Path(url)


settings = Settings()
