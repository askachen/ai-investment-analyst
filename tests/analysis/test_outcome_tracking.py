from decimal import Decimal

from ai_investment_analyst.analysis.outcome_tracking import (
    PriceObservation,
    ScreeningPick,
    evaluate_strategy_outcomes,
)


def test_evaluate_strategy_outcomes_computes_forward_returns_and_hit_rate():
    picks = [
        ScreeningPick(strategy_key='growth', run_date='2026-05-01', ticker='2330', rank=1, entry_price=Decimal('100')),
        ScreeningPick(strategy_key='growth', run_date='2026-05-01', ticker='2454', rank=2, entry_price=Decimal('200')),
        ScreeningPick(strategy_key='value', run_date='2026-05-01', ticker='1101', rank=1, entry_price=Decimal('50')),
    ]
    prices = {
        '2330': [PriceObservation(trading_date='2026-05-08', close_price=Decimal('108'))],
        '2454': [PriceObservation(trading_date='2026-05-08', close_price=Decimal('196'))],
        '1101': [PriceObservation(trading_date='2026-05-08', close_price=Decimal('52.5'))],
    }

    summary = evaluate_strategy_outcomes(picks, prices, horizon_days=7, hit_threshold_pct=Decimal('5'))

    assert summary.horizon_days == 7
    assert summary.strategy_key == 'growth'
    assert summary.evaluated_count == 2
    assert summary.missing_count == 0
    assert summary.hit_count == 1
    assert summary.hit_rate_pct == Decimal('50.00')
    assert summary.average_return_pct == Decimal('3.00')
    assert summary.results[0].forward_return_pct == Decimal('8.00')
    assert summary.results[0].is_hit is True
    assert summary.results[1].forward_return_pct == Decimal('-2.00')
    assert summary.results[1].is_hit is False


def test_evaluate_strategy_outcomes_marks_missing_forward_prices():
    picks = [
        ScreeningPick(strategy_key='balanced', run_date='2026-05-01', ticker='2330', rank=1, entry_price=Decimal('100')),
        ScreeningPick(strategy_key='balanced', run_date='2026-05-01', ticker='2454', rank=2, entry_price=Decimal('200')),
    ]
    prices = {
        '2330': [PriceObservation(trading_date='2026-05-08', close_price=Decimal('103'))],
    }

    summary = evaluate_strategy_outcomes(picks, prices, horizon_days=7, hit_threshold_pct=Decimal('0'))

    assert summary.evaluated_count == 1
    assert summary.missing_count == 1
    assert summary.hit_count == 1
    assert summary.hit_rate_pct == Decimal('100.00')
    assert summary.results[1].forward_close is None
    assert summary.results[1].forward_return_pct is None
    assert summary.results[1].is_hit is None


def test_evaluate_strategy_outcomes_respects_top_n():
    picks = [
        ScreeningPick(strategy_key='flow', run_date='2026-05-01', ticker='A', rank=1, entry_price=Decimal('10')),
        ScreeningPick(strategy_key='flow', run_date='2026-05-01', ticker='B', rank=2, entry_price=Decimal('10')),
    ]
    prices = {
        'A': [PriceObservation(trading_date='2026-05-08', close_price=Decimal('11'))],
        'B': [PriceObservation(trading_date='2026-05-08', close_price=Decimal('20'))],
    }

    summary = evaluate_strategy_outcomes(picks, prices, horizon_days=7, top_n=1)

    assert [result.ticker for result in summary.results] == ['A']
    assert summary.evaluated_count == 1
    assert summary.average_return_pct == Decimal('10.00')
