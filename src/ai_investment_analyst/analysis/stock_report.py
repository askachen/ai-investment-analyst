from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable

import yfinance as yf

from ai_investment_analyst.analysis.fundamental_factors import (
    FundamentalFactorInputs,
    normalize_fundamental_factors,
)
from ai_investment_analyst.analysis.news import (
    NewsItem,
    classify_news_catalysts,
    fetch_ticker_news,
    rewrite_news_as_analyst_bullets,
    summarize_news_in_traditional_chinese,
)
from ai_investment_analyst.analysis.sector_templates import resolve_sector_template
from ai_investment_analyst.analysis.valuation_model import ValuationInputs, estimate_intrinsic_value
from ai_investment_analyst.db.connection import get_connection


@dataclass(frozen=True)
class PricePoint:
    trading_date: str
    close_price: Decimal | None
    source_code: str | None


@dataclass(frozen=True)
class RevenuePoint:
    revenue_period: str
    revenue: Decimal | None
    revenue_month_change_percent: Decimal | None
    revenue_year_change_percent: Decimal | None


@dataclass(frozen=True)
class FinancialSummary:
    report_date: str
    revenue: Decimal | None
    net_income: Decimal | None
    eps: Decimal | None
    eps_ttm: Decimal | None = None
    eps_ttm_periods: int = 0


@dataclass(frozen=True)
class StockReportContext:
    ticker: str
    latest: PricePoint | None
    recent_prices: list[PricePoint]
    latest_revenue: RevenuePoint | None
    latest_financial_summary: FinancialSummary | None
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None


@dataclass(frozen=True)
class ReportFacts:
    rating: str
    confidence: str
    thesis: str
    summary: str
    key_points: list[str]
    financial_snapshot: list[str]
    price_observation: str
    fundamental_observation: str
    valuation_observation: str
    valuation_label: str
    valuation_range: str
    target_price_summary: str
    news_observation: str
    risk_flags: list[str]
    bull_case: list[str]
    base_case: list[str]
    bear_case: list[str]
    conclusion: str
    research_snapshot: list[str] = field(default_factory=list)
    sector_guidance: list[str] = field(default_factory=list)


def candidate_market_tickers(ticker: str) -> list[str]:
    candidates = [ticker]
    if ticker.isdigit() and f"{ticker}.TW" not in candidates:
        candidates.append(f"{ticker}.TW")
    return candidates


def load_stock_report_context(ticker: str, limit: int = 10) -> StockReportContext:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.ticker, pdc.trading_date, pdc.close_price, ds.code AS source_code
            FROM price_daily_canonical pdc
            JOIN symbols s ON s.id = pdc.symbol_id
            JOIN data_sources ds ON ds.id = pdc.data_source_id
            WHERE s.ticker = %s
            ORDER BY pdc.trading_date DESC
            LIMIT %s
            """,
            (ticker, limit),
        )
        price_rows = cur.fetchall()

        cur.execute(
            """
            SELECT s.name, s.local_name, s.sector, s.industry
            FROM symbols s
            WHERE s.ticker = %s
            LIMIT 1
            """,
            (ticker,),
        )
        symbol_row = cur.fetchone()

        cur.execute(
            """
            SELECT mr.revenue_period, mr.revenue, mr.revenue_month_change_percent, mr.revenue_year_change_percent
            FROM monthly_revenues mr
            JOIN symbols s ON s.id = mr.symbol_id
            WHERE s.ticker = %s
            ORDER BY mr.revenue_period DESC
            LIMIT 13
            """,
            (ticker,),
        )
        revenue_rows = cur.fetchall()

        cur.execute(
            """
            SELECT fsi.report_date, fsi.statement_type, fsi.item_name, fsi.item_value
            FROM financial_statement_items fsi
            JOIN symbols s ON s.id = fsi.symbol_id
            WHERE s.ticker = %s
            ORDER BY fsi.report_date DESC
            """,
            (ticker,),
        )
        financial_rows = cur.fetchall()

    points = [
        PricePoint(
            trading_date=row[1].isoformat(),
            close_price=row[2],
            source_code=row[3],
        )
        for row in price_rows
    ]
    latest = points[0] if points else None

    latest_revenue = None
    if revenue_rows:
        latest_period = revenue_rows[0][0].isoformat()
        latest_value = revenue_rows[0][1]
        revenue_by_period = {row[0]: row[1] for row in revenue_rows}
        latest_period_date = revenue_rows[0][0]
        previous_month_period = date(latest_period_date.year - 1, 12, 1) if latest_period_date.month == 1 else date(latest_period_date.year, latest_period_date.month - 1, 1)
        previous_year_period = date(latest_period_date.year - 1, latest_period_date.month, 1)
        previous_month_value = revenue_by_period.get(previous_month_period)
        previous_year_value = revenue_by_period.get(previous_year_period)

        revenue_month_change_percent = revenue_rows[0][2]
        revenue_year_change_percent = revenue_rows[0][3]
        if latest_value is not None and previous_month_value not in (None, Decimal("0")):
            revenue_month_change_percent = revenue_month_change_percent or ((latest_value - previous_month_value) / previous_month_value) * Decimal("100")
        if latest_value is not None and previous_year_value not in (None, Decimal("0")):
            revenue_year_change_percent = revenue_year_change_percent or ((latest_value - previous_year_value) / previous_year_value) * Decimal("100")

        latest_revenue = RevenuePoint(
            revenue_period=latest_period,
            revenue=latest_value,
            revenue_month_change_percent=revenue_month_change_percent,
            revenue_year_change_percent=revenue_year_change_percent,
        )

    latest_financial_summary = None
    if financial_rows:
        latest_report_date = financial_rows[0][0]
        latest_rows = [row for row in financial_rows if row[0] == latest_report_date]

        eps_by_report_date: dict[object, Decimal] = {}
        for report_date, _, item_name, item_value in financial_rows:
            normalized = (item_name or "").lower()
            if item_value is not None and ("每股盈餘" in item_name or "eps" in normalized):
                eps_by_report_date.setdefault(report_date, item_value)
        recent_eps_values = [eps_by_report_date[key] for key in sorted(eps_by_report_date.keys(), reverse=True)[:4]]
        eps_ttm = sum(recent_eps_values, Decimal("0")) if len(recent_eps_values) == 4 else None

        revenue = None
        net_income = None
        eps = None
        for _, _, item_name, item_value in latest_rows:
            normalized = (item_name or "").lower()
            if revenue is None and ("營業收入" in item_name or "revenue" in normalized):
                revenue = item_value
            if net_income is None and (
                "本期淨利" in item_name or "本期稅後淨利" in item_name or "net income" in normalized
            ):
                net_income = item_value
            if eps is None and ("每股盈餘" in item_name or "eps" in normalized):
                eps = item_value

        latest_financial_summary = FinancialSummary(
            report_date=latest_report_date.isoformat(),
            revenue=revenue,
            net_income=net_income,
            eps=eps,
            eps_ttm=eps_ttm,
            eps_ttm_periods=len(recent_eps_values),
        )

    company_name = None
    sector = None
    industry = None
    if symbol_row:
        company_name = symbol_row[1] or symbol_row[0]
        sector = symbol_row[2]
        industry = symbol_row[3]

    return StockReportContext(
        ticker=ticker,
        latest=latest,
        recent_prices=points,
        latest_revenue=latest_revenue,
        latest_financial_summary=latest_financial_summary,
        company_name=company_name,
        sector=sector,
        industry=industry,
    )


def load_market_context_from_yfinance(ticker: str, limit: int = 10) -> StockReportContext:
    points: list[PricePoint] = []
    latest_revenue = None
    latest_financial_summary = None
    for candidate in candidate_market_tickers(ticker):
        yf_ticker = yf.Ticker(candidate)
        history = yf_ticker.history(period="1mo", interval="1d", auto_adjust=False)
        if history.empty:
            continue

        recent = history.tail(limit)
        points = [
            PricePoint(
                trading_date=index.date().isoformat(),
                close_price=Decimal(str(row.get("Close"))) if row.get("Close") == row.get("Close") else None,
                source_code="yfinance-live",
            )
            for index, row in recent.iloc[::-1].iterrows()
        ]
        info = yf_ticker.info or {}
        trailing_revenue = info.get("totalRevenue")
        trailing_net_income = info.get("netIncomeToCommon")
        trailing_eps = info.get("trailingEps")
        revenue_growth = info.get("revenueGrowth")
        if revenue_growth is None:
            revenue_growth = info.get("quarterlyRevenueGrowth")
        if trailing_revenue is not None or revenue_growth is not None:
            latest_revenue = RevenuePoint(
                revenue_period="live-info",
                revenue=Decimal(str(trailing_revenue)) if trailing_revenue is not None else None,
                revenue_month_change_percent=None,
                revenue_year_change_percent=Decimal(str(revenue_growth)) * Decimal("100") if revenue_growth is not None else None,
            )
        if any(value is not None for value in [trailing_revenue, trailing_net_income, trailing_eps]):
            latest_financial_summary = FinancialSummary(
                report_date="live-info",
                revenue=Decimal(str(trailing_revenue)) if trailing_revenue is not None else None,
                net_income=Decimal(str(trailing_net_income)) if trailing_net_income is not None else None,
                eps=Decimal(str(trailing_eps)) if trailing_eps is not None else None,
                eps_ttm=Decimal(str(trailing_eps)) if trailing_eps is not None else None,
                eps_ttm_periods=4 if trailing_eps is not None else 0,
            )
        break

    return StockReportContext(
        ticker=ticker,
        latest=points[0] if points else None,
        recent_prices=points,
        latest_revenue=latest_revenue,
        latest_financial_summary=latest_financial_summary,
    )


def _quantize_2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _pct_value(new: Decimal | None, old: Decimal | None) -> Decimal | None:
    if new is None or old in (None, Decimal("0")):
        return None
    return ((new - old) / old) * Decimal("100")


def _fmt_price(value: Decimal | None) -> str:
    return "N/A" if value is None else f"{_quantize_2(value)}"


def _fmt_percent(value: Decimal | None) -> str:
    return "N/A" if value is None else f"{_quantize_2(value)}%"


def _fmt_revenue_in_100m(value: Decimal | None) -> str:
    if value is None:
        return "N/A"
    amount = value / Decimal("100000000")
    return f"{_quantize_2(amount)} 億元"


def _fmt_eps_basis(summary: FinancialSummary | None) -> str:
    if not summary:
        return "EPS：N/A"
    if summary.eps_ttm is not None:
        return f"TTM EPS：{_fmt_price(summary.eps_ttm)}"
    return f"近一期 EPS：{_fmt_price(summary.eps)}"


def _valuation_eps_ttm(summary: FinancialSummary | None) -> Decimal | None:
    """Return the EPS basis suitable for PE/valuation calculations.

    Database financial rows are quarterly observations, so PE and target-price
    math must prefer a trailing-twelve-month EPS aggregated from the latest four
    quarters. Market fallback providers such as yfinance already expose
    trailingEps; those are stored in eps_ttm as well.
    """
    if summary is None:
        return None
    if summary.eps_ttm is not None and summary.eps_ttm > Decimal("0"):
        return summary.eps_ttm
    if summary.report_date == "live-info" and summary.eps not in (None, Decimal("0")):
        return summary.eps
    return None


def _trend_label(prices: list[PricePoint]) -> str:
    closes = [p.close_price for p in prices[:3] if p.close_price is not None]
    if len(closes) < 3:
        return "資料不足"
    if closes[0] >= closes[1] >= closes[2]:
        return "短線偏強"
    if closes[0] <= closes[1] <= closes[2]:
        return "短線偏弱"
    return "區間震盪"


def _confidence_from_data(context: StockReportContext) -> str:
    available = int(context.latest is not None) + int(context.latest_revenue is not None) + int(context.latest_financial_summary is not None)
    return "高" if available == 3 else "中" if available == 2 else "低"


def _news_observation(news_items: list[NewsItem]) -> str:
    if not news_items:
        return "近期未取得足夠新聞樣本，市場催化判讀保守。"
    publishers = ", ".join(dict.fromkeys(item.publisher for item in news_items if item.publisher))
    return f"近期共有 {len(news_items)} 則可用新聞，來源包含 {publishers}，可作為短期催化與情緒觀察依據。"


def _net_margin_pct(summary: FinancialSummary | None) -> Decimal | None:
    if not summary or summary.revenue in (None, Decimal("0")) or summary.net_income is None:
        return None
    return (summary.net_income / summary.revenue) * Decimal("100")


def _build_research_snapshot(context: StockReportContext) -> tuple[list[str], list[str]]:
    revenue_growth = context.latest_revenue.revenue_year_change_percent if context.latest_revenue else None
    net_margin = _net_margin_pct(context.latest_financial_summary)
    factor_result = normalize_fundamental_factors(
        FundamentalFactorInputs(
            net_margin_pct=net_margin,
            revenue_growth_yoy_pct=revenue_growth,
        )
    )
    valuation = estimate_intrinsic_value(
        ValuationInputs(
            current_price=context.latest.close_price if context.latest else None,
            eps_ttm=_valuation_eps_ttm(context.latest_financial_summary),
            revenue_growth_yoy_pct=revenue_growth,
            market_pe_median=Decimal("18"),
        )
    )
    template = resolve_sector_template(company_name=context.company_name, industry=context.industry or context.sector)

    fair_range = "資料不足"
    if valuation.fair_value_range:
        fair_range = f"{_fmt_price(valuation.fair_value_range[0])} - {_fmt_price(valuation.fair_value_range[1])}"
    target = _fmt_price(valuation.blended_target_price)
    margin = _fmt_percent(valuation.margin_of_safety_pct)
    research_snapshot = [
        f"基本面因子：綜合分數 {factor_result.composite_score}，缺漏 {len(factor_result.missing_factors)} 項；{factor_result.evidence_summary[0]}",
        f"多錨估值：目標價 {target}，合理區間 {fair_range}，安全邊際 {margin}，信心 {valuation.confidence_label}。",
        f"估值方法：已納入 {', '.join(valuation.method_prices.keys()) or '無'}；缺漏 {', '.join(valuation.missing_methods) or '無'}。",
    ]
    sector_guidance = [
        f"產業模板：{template.label}",
        f"核心檢查：{'、'.join(template.core_metrics[:4])}",
        f"催化/風險：{'、'.join(template.catalyst_prompts[:2])}；{'、'.join(template.risk_prompts[:2])}",
    ]
    return research_snapshot, sector_guidance


def build_report_facts(context: StockReportContext, news_items: list[NewsItem] | None = None) -> ReportFacts:
    news_items = news_items or []
    if not context.latest:
        return ReportFacts(
            rating="中立",
            confidence="低",
            thesis="資料不足，暫時無法建立明確投資主軸。",
            summary="目前缺少有效價格資料，無法形成可靠判讀。",
            key_points=["尚未取得 canonical 價格資料"],
            financial_snapshot=["營收：N/A", "EPS：N/A", "淨利：N/A"],
            price_observation="價格資料不足。",
            fundamental_observation="基本面資料不足。",
            valuation_observation="估值資料不足。",
            valuation_label="合理",
            valuation_range="合理價區間：資料不足。",
            target_price_summary="目標價：資料不足。",
            news_observation=_news_observation(news_items),
            risk_flags=["資料完整度不足可能導致誤判"],
            bull_case=["缺乏足夠資料，無法建立 Bull Case。"],
            base_case=["待資料補齊後再建構 Base Case。"],
            bear_case=["資料不足本身即為主要風險。"],
            conclusion="待資料補齊後再進行分析。",
            research_snapshot=["基本面因子：資料不足。", "多錨估值：資料不足。"],
            sector_guidance=["產業模板：通用", "核心檢查：先補齊價格、營收與財報資料。"],
        )

    latest = context.latest
    previous_5 = context.recent_prices[4] if len(context.recent_prices) >= 5 else None
    previous_10 = context.recent_prices[9] if len(context.recent_prices) >= 10 else None
    pct_5 = _pct_value(latest.close_price, previous_5.close_price if previous_5 else None)
    pct_10 = _pct_value(latest.close_price, previous_10.close_price if previous_10 else None)

    positive_price = sum(value is not None and value > 0 for value in [pct_5, pct_10])
    positive_fundamental = sum(
        value is not None and value > 0
        for value in [
            context.latest_revenue.revenue_month_change_percent if context.latest_revenue else None,
            context.latest_revenue.revenue_year_change_percent if context.latest_revenue else None,
            context.latest_financial_summary.net_income if context.latest_financial_summary else None,
        ]
    )
    score = positive_price + positive_fundamental
    rating = "偏多" if score >= 3 else "中立" if score >= 1 else "偏空"

    key_points = [
        f"最新收盤價 {_fmt_price(latest.close_price)}，資料日期 {latest.trading_date}。",
        f"近 5 日漲跌幅 {_fmt_percent(pct_5)}，近 10 日漲跌幅 {_fmt_percent(pct_10)}。",
        f"近三日價格節奏屬於{_trend_label(context.recent_prices)}。",
    ]

    fundamental_bits: list[str] = []
    if context.latest_revenue:
        fundamental_bits.append(
            f"月營收年增 {_fmt_percent(context.latest_revenue.revenue_year_change_percent)}、月增 {_fmt_percent(context.latest_revenue.revenue_month_change_percent)}。"
        )
    if context.latest_financial_summary:
        fundamental_bits.append(
            f"最近財報近一期 EPS {_fmt_price(context.latest_financial_summary.eps)}、{_fmt_eps_basis(context.latest_financial_summary)}、淨利 {_fmt_revenue_in_100m(context.latest_financial_summary.net_income)}。"
        )
    if not fundamental_bits:
        fundamental_bits.append("尚無完整財報與月營收可供交叉驗證。")

    risk_flags: list[str] = []
    if pct_5 is not None and pct_5 > Decimal("10"):
        risk_flags.append("短線漲幅偏大，需留意追價後震盪。")
    else:
        risk_flags.append("市場仍可能受總體與法說展望影響而波動。")
    if context.latest_revenue and context.latest_revenue.revenue_month_change_percent is not None and context.latest_revenue.revenue_month_change_percent < 0:
        risk_flags.append("月營收月減，短期拉貨動能可能轉弱。")
    else:
        risk_flags.append("若後續營收或 AI 需求不如預期，評價可能修正。")

    summary = "價格動能與基本面訊號大致同向，整體評估維持偏正向。" if rating == "偏多" else "目前多空訊號分歧，建議以中性角度追蹤。" if rating == "中立" else "價格與基本面轉弱，宜保守看待。"
    price_observation = f"近 5 日漲幅 {_fmt_percent(pct_5)}，近 10 日漲幅 {_fmt_percent(pct_10)}，短線結構顯示{_trend_label(context.recent_prices)}。"
    fundamental_observation = " ".join(fundamental_bits)
    base_eps = _valuation_eps_ttm(context.latest_financial_summary)
    trailing_pe = None
    if context.latest and context.latest.close_price is not None and base_eps not in (None, Decimal("0")):
        trailing_pe = context.latest.close_price / base_eps
    valuation_observation = (
        f"以最新收盤價與 TTM EPS 粗估，本益比約 {_fmt_price(trailing_pe)} 倍，評價已不算便宜，後續需由獲利成長消化。"
        if trailing_pe is not None
        else "目前缺少足夠 TTM EPS 或價格資料，估值區間暫時無法完整判讀。"
    )
    lower_bound = base_eps * Decimal('20') if base_eps is not None else None
    upper_bound = base_eps * Decimal('25') if base_eps is not None else None
    valuation_label = "合理"
    if context.latest and context.latest.close_price is not None and lower_bound is not None and upper_bound is not None:
        if context.latest.close_price > upper_bound:
            valuation_label = "偏高"
        elif context.latest.close_price < lower_bound:
            valuation_label = "偏低"
        else:
            valuation_label = "合理"
    valuation_range = (
        f"合理價區間：約 { _fmt_price(lower_bound) } - { _fmt_price(upper_bound) }，以 TTM EPS 為基準；高於區間上緣代表市場已提前反映成長。"
        if lower_bound is not None and upper_bound is not None
        else "合理價區間：資料不足。"
    )
    target_price = base_eps * Decimal('22') if base_eps is not None else None
    trend_label = _trend_label(context.recent_prices)
    revenue_yoy = context.latest_revenue.revenue_year_change_percent if context.latest_revenue else None
    revenue_mom = context.latest_revenue.revenue_month_change_percent if context.latest_revenue else None
    thesis_bits: list[str] = []
    if rating == "偏空":
        thesis = "需求與價格動能轉弱，現階段投資主軸偏向風險控管與等待基本面止穩。"
    else:
        if revenue_yoy is not None and revenue_yoy > 0:
            thesis_bits.append(f"月營收年增 {_fmt_percent(revenue_yoy)} 顯示基本面仍有支撐")
        elif revenue_yoy is not None and revenue_yoy < 0:
            thesis_bits.append(f"月營收年減 {_fmt_percent(abs(revenue_yoy))} 反映需求修正壓力")
        else:
            thesis_bits.append("基本面仍待更多營收與財報資料確認")

        if revenue_mom is not None and revenue_mom < 0:
            thesis_bits.append(f"但月增 {_fmt_percent(revenue_mom)} 顯示短期拉貨力道放緩")
        if trend_label != "資料不足":
            thesis_bits.append(f"短線走勢呈現{trend_label}")

        thesis_bits.append(f"目前評價{valuation_label}，操作上宜留意切入節奏")
        thesis = "，".join(thesis_bits) + "。"
    financial_snapshot = [
        f"營收：{_fmt_revenue_in_100m(context.latest_financial_summary.revenue) if context.latest_financial_summary else 'N/A'}",
        f"淨利：{_fmt_revenue_in_100m(context.latest_financial_summary.net_income) if context.latest_financial_summary else 'N/A'}",
        f"近一期 EPS：{_fmt_price(context.latest_financial_summary.eps) if context.latest_financial_summary else 'N/A'}",
        _fmt_eps_basis(context.latest_financial_summary),
        f"月營收 YoY：{_fmt_percent(context.latest_revenue.revenue_year_change_percent) if context.latest_revenue else 'N/A'}",
        f"月營收 MoM：{_fmt_percent(context.latest_revenue.revenue_month_change_percent) if context.latest_revenue else 'N/A'}",
    ]
    research_snapshot, sector_guidance = _build_research_snapshot(context)
    target_price_summary = (
        f"以 Base Case {_fmt_price(base_eps)} 元 TTM EPS 與 22 倍本益比推估，目標價約 {_fmt_price(target_price)} 元；若市場願意給到 25 倍，Bull Case 可上看 {_fmt_price(base_eps * Decimal('25'))} 元。"
        if base_eps is not None
        else "目標價：缺乏足夠 TTM EPS 資料，暫時無法推導。"
    )
    news_observation = _news_observation(news_items)
    bull_case = [
        "AI 需求與先進製程報價同步上行，帶動獲利優於市場預期。",
        "法人持續上修資本支出效率與中長期成長能見度。",
    ]
    base_case = [
        "主要客戶需求維持穩健，營收與獲利大致符合目前市場共識。",
        f"評價維持在{valuation_label}附近，股價以基本面消化為主。",
    ]
    bear_case = [
        "終端需求或雲端資本支出放緩，導致營收與毛利率低於預期。",
        "若市場風險偏好下降，高評價族群可能面臨本益比修正。",
    ]
    conclusion = (
        f"短線評價{valuation_label}，現階段宜等待營運動能或新催化進一步確認；若 AI 需求延續，中期基本面仍具支撐。"
        if rating == "中立"
        else f"雖然基本面趨勢偏正向，但目前評價{valuation_label}，操作上不宜過度追價。"
        if rating == "偏多"
        else "在價格與基本面未見止穩前，建議以保守策略為主，等待風險因素鈍化。"
    )

    return ReportFacts(
        rating=rating,
        confidence=_confidence_from_data(context),
        thesis=thesis,
        summary=summary,
        key_points=key_points,
        financial_snapshot=financial_snapshot,
        price_observation=price_observation,
        fundamental_observation=fundamental_observation,
        valuation_observation=valuation_observation,
        valuation_label=valuation_label,
        valuation_range=valuation_range,
        target_price_summary=target_price_summary,
        news_observation=news_observation,
        risk_flags=risk_flags,
        bull_case=bull_case,
        base_case=base_case,
        bear_case=bear_case,
        conclusion=conclusion,
        research_snapshot=research_snapshot,
        sector_guidance=sector_guidance,
    )


def render_fallback_report(ticker: str, facts: ReportFacts, news_items: list[NewsItem]) -> str:
    grouped_news = classify_news_catalysts(news_items)
    if not any(grouped_news.values()):
        grouped_news = {"positive": ["- 近期尚未取得足夠新聞資料。"], "neutral": [], "risk": []}

    lines = [
        f"【個股分析報告】{ticker}",
        f"投資評級：{facts.rating}",
        f"信心等級：{facts.confidence}",
        "",
        "一句話投資主軸",
        facts.thesis,
        "",
        "重點摘要",
        facts.summary,
        "",
        "重點摘要（條列）",
        *[f"- {point}" for point in facts.key_points],
        "",
        "財務摘要表",
        *[f"- {item}" for item in facts.financial_snapshot],
        "",
        "研究引擎摘要",
        *[f"- {item}" for item in facts.research_snapshot],
        *[f"- {item}" for item in facts.sector_guidance],
        "",
        "價格與技術面觀察",
        facts.price_observation,
        "",
        "基本面觀察",
        facts.fundamental_observation,
        "",
        "估值觀察",
        facts.valuation_observation,
        f"評價標籤：{facts.valuation_label}",
        facts.valuation_range,
        "",
        "目標價推導",
        facts.target_price_summary,
        "",
        "新聞與市場催化",
        facts.news_observation,
        "利多催化",
        *(grouped_news["positive"] or ["- 目前未觀察到明確利多催化。"]),
        "",
        "中性觀察",
        *(grouped_news["neutral"] or ["- 目前中性訊息有限。"]),
        "",
        "潛在風險",
        *(grouped_news["risk"] or ["- 目前新聞面未見新增顯著風險，但仍需留意外部變數。"]),
        "",
        "分析師觀點",
        f"- 就現階段資料來看，股價與基本面尚未形成明確單邊共振，因此維持{facts.rating}看法。",
        f"- 若後續營運動能、法說指引與市場催化同步改善，評級才有上修空間；目前信心等級為{facts.confidence}。",
        "",
        "風險提示",
        *[f"- {risk}" for risk in facts.risk_flags],
        "",
        "投資建議",
        f"- 對中長線投資人而言，現階段宜以分批布局 / 逢回觀察的節奏應對，而非追價。" if facts.rating != "偏空" else "- 建議先觀望，等待基本面與價格訊號重新同步。",
        "",
        "Bull Case",
        *[f"- {item}" for item in facts.bull_case],
        "",
        "Base Case",
        *[f"- {item}" for item in facts.base_case],
        "",
        "Bear Case",
        *[f"- {item}" for item in facts.bear_case],
        "",
        "結論",
        facts.conclusion,
    ]
    return "\n".join(lines)


def generate_stock_report(
    ticker: str,
    context_loader: Callable[[str], StockReportContext] = load_stock_report_context,
    news_fetcher: Callable[[str, int], list[NewsItem]] = fetch_ticker_news,
    report_client=None,
    market_context_loader: Callable[[str], StockReportContext] = load_market_context_from_yfinance,
    news_translator: Callable[[list[NewsItem]], list[NewsItem]] = summarize_news_in_traditional_chinese,
) -> str:
    try:
        context = context_loader(ticker)
    except Exception:
        context = market_context_loader(ticker)
    if not context.latest:
        return f"找不到 {ticker} 的可用價格資料。"

    news_items = news_fetcher(ticker, count=3)
    news_items = news_translator(news_items)
    facts = build_report_facts(context, news_items)

    if report_client is not None:
        try:
            return report_client.generate_report(ticker, facts, news_items)
        except Exception:
            return render_fallback_report(ticker, facts, news_items)

    from ai_investment_analyst.analysis.llm import generate_analyst_report

    result = generate_analyst_report(ticker=ticker, facts=facts, news_items=news_items)
    return result.report
