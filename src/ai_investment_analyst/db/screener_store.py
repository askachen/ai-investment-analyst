from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from ai_investment_analyst.analysis.screener import get_strategy_profile, list_strategy_profiles
from ai_investment_analyst.config import settings
from ai_investment_analyst.db.connection import get_connection

if TYPE_CHECKING:
    from ai_investment_analyst.analysis.daily_screener import DailyScreeningSnapshot


def list_default_screening_tickers() -> list[str]:
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.ticker
                FROM symbols s
                JOIN markets m ON m.id = s.market_id
                WHERE s.is_active = TRUE
                  AND s.instrument_type = 'stock'
                  AND m.code IN ('TW', 'US')
                ORDER BY m.code, s.ticker
                """
            )
            rows = [row[0] for row in cur.fetchall()]
            if rows:
                return rows
    except Exception:
        pass
    return list(settings.screening_tickers)


def _json_default(value: Any):
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f'Unsupported JSON value: {type(value)!r}')


def _serialize_strategy(strategy_key: str) -> dict[str, str]:
    strategy = get_strategy_profile(strategy_key)
    return {
        'key': strategy.key,
        'label': strategy.label,
        'description': strategy.description,
    }


def _list_serialized_strategies() -> list[dict[str, str]]:
    return [
        {
            'key': strategy.key,
            'label': strategy.label,
            'description': strategy.description,
        }
        for strategy in list_strategy_profiles()
    ]


def save_screening_snapshot(snapshot: DailyScreeningSnapshot) -> str:
    criteria = {
        'strategy_key': snapshot.strategy_key,
        'strategy': _serialize_strategy(snapshot.strategy_key),
    }
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO screening_runs (
                run_date, generated_at, universe_size, candidate_count, status, criteria
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                snapshot.run_date,
                snapshot.generated_at,
                snapshot.universe_size,
                snapshot.candidate_count,
                'completed',
                json.dumps(criteria, ensure_ascii=False),
            ),
        )
        run_id = cur.fetchone()[0]
        for result in snapshot.results:
            cur.execute(
                """
                INSERT INTO screening_results (
                    screening_run_id, rank, ticker, total_score, close_price, factor_scores, reasons
                )
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                """,
                (
                    run_id,
                    result.rank,
                    result.ticker,
                    result.total_score,
                    result.close_price,
                    json.dumps(result.factor_scores, ensure_ascii=False, default=_json_default),
                    json.dumps(result.reasons, ensure_ascii=False),
                ),
            )
        conn.commit()
    return run_id


def load_latest_screener_snapshot(strategy: str = 'balanced') -> dict[str, Any] | None:
    strategy_profile = get_strategy_profile(strategy)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, run_date, generated_at, universe_size, candidate_count, criteria
            FROM screening_runs
            WHERE status = 'completed'
              AND COALESCE(criteria->>'strategy_key', 'balanced') = %s
            ORDER BY generated_at DESC
            LIMIT 1
            """,
            (strategy_profile.key,),
        )
        run_row = cur.fetchone()
        if not run_row:
            return None
        run_id, run_date, generated_at, universe_size, candidate_count, criteria = run_row
        cur.execute(
            """
            SELECT rank, ticker, total_score, close_price, factor_scores, reasons
            FROM screening_results
            WHERE screening_run_id = %s
            ORDER BY rank ASC
            """,
            (run_id,),
        )
        rows = cur.fetchall()

    results = [
        {
            'rank': row[0],
            'ticker': row[1],
            'total_score': str(row[2]),
            'close_price': str(row[3]) if row[3] is not None else None,
            'factor_scores': {key: str(value) for key, value in (row[4] or {}).items()},
            'reasons': list(row[5] or []),
        }
        for row in rows
    ]
    strategy_payload = dict((criteria or {}).get('strategy') or _serialize_strategy(strategy_profile.key))
    return {
        'run_date': run_date.isoformat() if hasattr(run_date, 'isoformat') else str(run_date),
        'generated_at': generated_at.isoformat() if hasattr(generated_at, 'isoformat') else str(generated_at),
        'universe_size': universe_size,
        'candidate_count': candidate_count,
        'strategy': strategy_payload,
        'strategies': _list_serialized_strategies(),
        'results': results,
    }
