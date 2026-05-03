from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

DEFAULT_SCREENING_TICKERS = (
    '1101',
    '1216',
    '1303',
    '2303',
    '2308',
    '2317',
    '2330',
    '2382',
    '2412',
    '2454',
    '2603',
    '2881',
    '2882',
    '3034',
    '3711',
    '6505',
)
SCREENING_TICKERS_RAW = os.getenv('SCREENING_TICKERS', '').strip()


def _screening_tickers() -> tuple[str, ...]:
    raw = SCREENING_TICKERS_RAW
    if not raw:
        return DEFAULT_SCREENING_TICKERS
    return tuple(part.strip().upper() for part in raw.split(',') if part.strip())


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "")
    finmind_api_token: str = os.getenv("FINMIND_API_TOKEN", "")
    finlab_api_key: str = os.getenv("FINLAB_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    screening_tickers: tuple[str, ...] = _screening_tickers()
    screening_tickers_overridden: bool = bool(SCREENING_TICKERS_RAW)


settings = Settings()
