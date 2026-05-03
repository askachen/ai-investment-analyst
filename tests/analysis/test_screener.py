from decimal import Decimal

import ai_investment_analyst.analysis.screener as screener_module
from ai_investment_analyst.analysis.screener import (
    ScreeningCandidate,
    ScreeningCriteria,
    get_strategy_profile,
    load_screener_candidates,
    render_screening_results,
    score_candidates,
)
from ai_investment_analyst.analysis.stock_report import (
    FinancialSummary,
    PricePoint,
    RevenuePoint,
    StockReportContext,
)


def make_candidate(
    ticker: str,
    close_price: str,
    price_5d_change_pct: str,
    price_10d_change_pct: str,
    average_volume_5d: int,
    revenue_yoy_pct: str,
    revenue_mom_pct: str,
    eps: str,
    pe_ratio: str,
    pb_ratio: str | None = None,
) -> ScreeningCandidate:
    return ScreeningCandidate(
        ticker=ticker,
        close_price=Decimal(close_price),
        price_5d_change_pct=Decimal(price_5d_change_pct),
        price_10d_change_pct=Decimal(price_10d_change_pct),
        average_volume_5d=average_volume_5d,
        revenue_yoy_pct=Decimal(revenue_yoy_pct),
        revenue_mom_pct=Decimal(revenue_mom_pct),
        eps=Decimal(eps),
        pe_ratio=Decimal(pe_ratio),
        pb_ratio=Decimal(pb_ratio) if pb_ratio is not None else None,
    )


def test_score_candidates_filters_and_ranks_explainably():
    candidates = [
        make_candidate(
            ticker="2330",
            close_price="850",
            price_5d_change_pct="6.25",
            price_10d_change_pct="13.33",
            average_volume_5d=42000000,
            revenue_yoy_pct="22.3",
            revenue_mom_pct="8.5",
            eps="10.25",
            pe_ratio="18.0",
            pb_ratio="4.8",
        ),
        make_candidate(
            ticker="2454",
            close_price="1200",
            price_5d_change_pct="3.8",
            price_10d_change_pct="7.4",
            average_volume_5d=12000000,
            revenue_yoy_pct="14.0",
            revenue_mom_pct="2.0",
            eps="8.8",
            pe_ratio="22.0",
            pb_ratio="5.2",
        ),
        make_candidate(
            ticker="1101",
            close_price="42",
            price_5d_change_pct="-3.4",
            price_10d_change_pct="-8.7",
            average_volume_5d=8000000,
            revenue_yoy_pct="3.1",
            revenue_mom_pct="-1.2",
            eps="2.1",
            pe_ratio="28.0",
            pb_ratio="1.3",
        ),
    ]
    criteria = ScreeningCriteria(
        min_revenue_yoy_pct=Decimal("5"),
        min_eps=Decimal("1"),
        max_pe_ratio=Decimal("25"),
        min_average_volume_5d=10000000,
    )

    ranked = score_candidates(candidates, criteria)

    assert [item.candidate.ticker for item in ranked] == ["2330", "2454"]
    assert ranked[0].total_score > ranked[1].total_score
    assert ranked[0].passed is True
    assert ranked[0].factor_scores["momentum"] > ranked[1].factor_scores["momentum"]
    assert any("月營收年增 22.30%" in reason for reason in ranked[0].reasons)
    assert any("本益比 18.00 倍" in reason for reason in ranked[0].reasons)


def test_score_candidates_keeps_pb_optional_without_blocking_rank():
    candidates = [
        make_candidate(
            ticker="AAPL",
            close_price="190",
            price_5d_change_pct="2.5",
            price_10d_change_pct="5.0",
            average_volume_5d=55000000,
            revenue_yoy_pct="9.0",
            revenue_mom_pct="1.0",
            eps="6.5",
            pe_ratio="21.0",
            pb_ratio=None,
        )
    ]

    ranked = score_candidates(candidates, ScreeningCriteria())

    assert ranked[0].candidate.ticker == "AAPL"
    assert ranked[0].passed is True
    assert ranked[0].factor_scores["valuation"] > Decimal("0")
    assert any("PB 資料尚缺" in reason for reason in ranked[0].reasons)


def test_score_candidates_marks_missing_revenue_mom_and_liquidity_as_unknown():
    ranked = score_candidates(
        [
            ScreeningCandidate(
                ticker="2330",
                close_price=Decimal("850"),
                price_5d_change_pct=Decimal("6.25"),
                price_10d_change_pct=Decimal("13.33"),
                average_volume_5d=None,
                revenue_yoy_pct=Decimal("22.3"),
                revenue_mom_pct=None,
                eps=Decimal("10.25"),
                pe_ratio=Decimal("18.0"),
                pb_ratio=Decimal("4.8"),
            )
        ],
        ScreeningCriteria(),
    )

    assert ranked[0].factor_scores["revenue"] > Decimal("0")
    assert ranked[0].factor_scores["liquidity"] == Decimal("0")
    assert any("月營收 MoM 資料尚缺" in reason for reason in ranked[0].reasons)
    assert any("成交量資料尚缺" in reason for reason in ranked[0].reasons)
    assert not any("月增 0.00%" in reason for reason in ranked[0].reasons)
    assert not any("平均量 0 股" in reason for reason in ranked[0].reasons)


def make_context(
    ticker: str,
    close_price: str,
    recent_prices: list[str],
    revenue_yoy_pct: str,
    revenue_mom_pct: str,
    eps: str,
    average_volume_5d: int,
) -> StockReportContext:
    del average_volume_5d
    return StockReportContext(
        ticker=ticker,
        latest=PricePoint(trading_date="2026-04-21", close_price=Decimal(close_price), source_code="test"),
        recent_prices=[
            PricePoint(trading_date=f"2026-04-{21-index:02d}", close_price=Decimal(value), source_code="test")
            for index, value in enumerate(recent_prices)
        ],
        latest_revenue=RevenuePoint(
            revenue_period="2026-03-01",
            revenue=Decimal("1000000000"),
            revenue_month_change_percent=Decimal(revenue_mom_pct),
            revenue_year_change_percent=Decimal(revenue_yoy_pct),
        ),
        latest_financial_summary=FinancialSummary(
            report_date="2025-12-31",
            revenue=Decimal("3000000000"),
            net_income=Decimal("500000000"),
            eps=Decimal(eps),
        ),
    )


def test_load_screener_candidates_derives_metrics_from_contexts():
    contexts = {
        "2330": make_context(
            ticker="2330",
            close_price="850",
            recent_prices=["850", "840", "830", "820", "800", "790", "780", "770", "760", "750"],
            revenue_yoy_pct="22.3",
            revenue_mom_pct="8.5",
            eps="10.25",
            average_volume_5d=42000000,
        ),
        "1101": make_context(
            ticker="1101",
            close_price="42",
            recent_prices=["42", "42.5", "43", "43.2", "43.5", "44", "44.5", "45", "45.5", "46"],
            revenue_yoy_pct="3.1",
            revenue_mom_pct="-1.2",
            eps="2.1",
            average_volume_5d=8000000,
        ),
    }

    candidates = load_screener_candidates(
        ["2330", "1101"],
        context_loader=lambda ticker: contexts[ticker],
        volume_loader=lambda ticker: {"2330": 42000000, "1101": 8000000}[ticker],
        pb_ratio_loader=lambda ticker: {"2330": Decimal("4.8"), "1101": Decimal("1.3")}[ticker],
    )

    assert [candidate.ticker for candidate in candidates] == ["2330", "1101"]
    assert candidates[0].price_5d_change_pct == Decimal("6.25")
    assert candidates[0].price_10d_change_pct == Decimal("13.33")
    assert candidates[0].pb_ratio == Decimal("4.8")
    assert candidates[1].revenue_mom_pct == Decimal("-1.2")


def test_latest_average_volume_5d_from_db_returns_none_when_no_volume_rows(monkeypatch):
    class FakeCursor:
        def execute(self, *_args, **_kwargs):
            return None

        def fetchone(self):
            return (None,)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(screener_module, 'get_connection', lambda: FakeConnection())

    assert screener_module._latest_average_volume_5d_from_db('2330') is None


def test_render_screening_results_formats_ranked_candidates_with_reasons():
    ranked = score_candidates(
        [
            make_candidate(
                ticker="2330",
                close_price="850",
                price_5d_change_pct="6.25",
                price_10d_change_pct="13.33",
                average_volume_5d=42000000,
                revenue_yoy_pct="22.3",
                revenue_mom_pct="8.5",
                eps="10.25",
                pe_ratio="18.0",
                pb_ratio="4.8",
            ),
            make_candidate(
                ticker="2454",
                close_price="1200",
                price_5d_change_pct="3.8",
                price_10d_change_pct="7.4",
                average_volume_5d=12000000,
                revenue_yoy_pct="14.0",
                revenue_mom_pct="2.0",
                eps="8.8",
                pe_ratio="22.0",
                pb_ratio="5.2",
            ),
        ],
        ScreeningCriteria(),
    )

    report = render_screening_results(ranked)

    assert "AI Investment Analyst Screener" in report
    assert "1. 2330" in report
    assert "總分" in report
    assert "動能" in report
    assert "月營收年增 22.30%" in report
    assert "2. 2454" in report


def test_score_candidates_supports_strategy_presets_for_reranking():
    candidates = [
        make_candidate(
            ticker="GROWTH",
            close_price="120",
            price_5d_change_pct="4.0",
            price_10d_change_pct="9.0",
            average_volume_5d=1200000,
            revenue_yoy_pct="30.0",
            revenue_mom_pct="12.0",
            eps="4.0",
            pe_ratio="35.0",
            pb_ratio="6.0",
        ),
        make_candidate(
            ticker="VALUE",
            close_price="85",
            price_5d_change_pct="1.0",
            price_10d_change_pct="2.0",
            average_volume_5d=600000,
            revenue_yoy_pct="8.0",
            revenue_mom_pct="1.0",
            eps="8.0",
            pe_ratio="9.0",
            pb_ratio="1.1",
        ),
    ]

    growth_ranked = score_candidates(candidates, strategy=get_strategy_profile("growth"))
    value_ranked = score_candidates(candidates, strategy=get_strategy_profile("value"))

    assert growth_ranked[0].candidate.ticker == "GROWTH"
    assert value_ranked[0].candidate.ticker == "VALUE"
