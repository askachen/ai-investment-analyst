from __future__ import annotations

import psycopg

from ai_investment_analyst.config import settings


def get_connection() -> psycopg.Connection:
    if not settings.database_url:
        raise ValueError("DATABASE_URL is not set")
    return psycopg.connect(settings.database_url)
