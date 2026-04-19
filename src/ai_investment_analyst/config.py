from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "")
    finmind_api_token: str = os.getenv("FINMIND_API_TOKEN", "")
    finlab_api_key: str = os.getenv("FINLAB_API_KEY", "")


settings = Settings()
