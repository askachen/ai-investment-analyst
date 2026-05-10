from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

WatchlistAction = Literal['add_to_watchlist', 'review_before_watchlist', 'do_not_watch']
WatchlistPriority = Literal['high', 'medium', 'low']
AlertKind = Literal['price_reaches_target', 'price_drawdown', 'data_stale', 'data_quality_review']

POSITIVE_RATINGS = {'買進', '加碼', '偏多'}
NEUTRAL_RATINGS = {'中立', '觀察', '持有'}
STALE_OR_INCOMPLETE_STATUSES = {'partial', 'stale', 'missing', 'unknown'}


@dataclass(frozen=True)
class AlertRule:
    kind: AlertKind
    label: str
    threshold: float | None = None
    message: str = ''


@dataclass(frozen=True)
class WatchlistAlertPlan:
    ticker: str
    action: WatchlistAction
    priority: WatchlistPriority
    summary: str
    rationale: list[str] = field(default_factory=list)
    alert_rules: list[AlertRule] = field(default_factory=list)


def _round_money(value: Decimal) -> float:
    return float(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _to_decimal(value: float | int | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _price_alert_rules(close_price: float | int | Decimal | None, target_price: float | int | Decimal | None) -> list[AlertRule]:
    close = _to_decimal(close_price)
    target = _to_decimal(target_price)
    rules: list[AlertRule] = []
    if target is not None:
        rules.append(
            AlertRule(
                kind='price_reaches_target',
                label='目標價提醒',
                threshold=_round_money(target),
                message='股價接近或達到目標價時提醒重新評估。',
            )
        )
    if close is not None and close > 0:
        drawdown = close * Decimal('0.95')
        rules.append(
            AlertRule(
                kind='price_drawdown',
                label='跌破觀察價提醒',
                threshold=_round_money(drawdown),
                message='較加入觀察時下跌 5% 時提醒檢查假設是否失效。',
            )
        )
    return rules


def plan_watchlist_alert_workflow(
    *,
    ticker: str,
    rating: str,
    confidence_score: int,
    data_quality_status: str,
    close_price: float | int | Decimal | None = None,
    target_price: float | int | Decimal | None = None,
) -> WatchlistAlertPlan:
    """Plan the watchlist and alert workflow for a stock decision.

    This is intentionally pure and persistence-free: it defines what the product
    should do before database tables, UI buttons, or external notifications are
    wired in.
    """
    normalized_rating = rating.strip()
    normalized_status = (data_quality_status or 'unknown').strip().lower()
    rationale: list[str] = []

    if normalized_rating not in POSITIVE_RATINGS and normalized_rating not in NEUTRAL_RATINGS:
        return WatchlistAlertPlan(
            ticker=ticker,
            action='do_not_watch',
            priority='low',
            summary='不加入觀察清單：評級或信心不足。',
            rationale=['評級不支持追蹤，應避免把弱訊號推進日常提醒。'],
            alert_rules=[],
        )

    if confidence_score < 50:
        return WatchlistAlertPlan(
            ticker=ticker,
            action='do_not_watch',
            priority='low',
            summary='不加入觀察清單：推薦信心過低。',
            rationale=['推薦信心低於 50，暫不建立提醒以避免噪音。'],
            alert_rules=[],
        )

    if normalized_status in STALE_OR_INCOMPLETE_STATUSES:
        rules = [
            AlertRule(
                kind='data_quality_review',
                label='資料品質複核',
                message='資料不完整或過期時，先複核再加入正式觀察清單。',
            )
        ]
        rules.extend(_price_alert_rules(close_price, target_price))
        return WatchlistAlertPlan(
            ticker=ticker,
            action='review_before_watchlist',
            priority='medium',
            summary='先複核再加入觀察清單：資料品質不足。',
            rationale=['資料品質不足，需先確認 freshness / completeness 再啟用提醒。'],
            alert_rules=rules,
        )

    if normalized_rating in POSITIVE_RATINGS and confidence_score >= 70:
        rules = _price_alert_rules(close_price, target_price)
        rules.append(
            AlertRule(
                kind='data_stale',
                label='資料過期提醒',
                message='若價格、營收或財報資料過期，提醒重新產生報告。',
            )
        )
        return WatchlistAlertPlan(
            ticker=ticker,
            action='add_to_watchlist',
            priority='high',
            summary='加入觀察清單：買進評級且信心足夠。',
            rationale=['正向評級、信心分數達門檻，且資料狀態可支撐追蹤。'],
            alert_rules=rules,
        )

    return WatchlistAlertPlan(
        ticker=ticker,
        action='review_before_watchlist',
        priority='medium',
        summary='列入人工複核：訊號尚未強到直接追蹤。',
        rationale=['評級或信心未達直接加入觀察清單門檻。'],
        alert_rules=_price_alert_rules(close_price, target_price),
    )
