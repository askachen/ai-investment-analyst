from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable

import yfinance as yf

from ai_investment_analyst.analysis.news import (
    NewsItem,
    classify_news_catalysts,
    fetch_ticker_news,
    rewrite_news_as_analyst_bullets,
    summarize_news_in_traditional_chinese,
)
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


@dataclass(frozen=True)
class StockReportContext:
    ticker: str
    latest: PricePoint | None
    recent_prices: list[PricePoint]
    latest_revenue: RevenuePoint | None
    latest_financial_summary: FinancialSummary | None


@dataclass(frozen=True)
class ReportFacts:
    rating: str
    confidence: str
    summary: str
    key_points: list[str]
    price_observation: str
    fundamental_observation: str
    valuation_observation: str
    valuation_label: str
    valuation_range: str
    news_observation: str
    risk_flags: list[str]
    conclusion: str


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
            SELECT mr.revenue_period, mr.revenue
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
        previous_month_value = revenue_rows[1][1] if len(revenue_rows) >= 2 else None
        previous_year_value = revenue_rows[12][1] if len(revenue_rows) >= 13 else None

        revenue_month_change_percent = None
        revenue_year_change_percent = None
        if latest_value is not None and previous_month_value not in (None, Decimal("0")):
            revenue_month_change_percent = ((latest_value - previous_month_value) / previous_month_value) * Decimal("100")
        if latest_value is not None and previous_year_value not in (None, Decimal("0")):
            revenue_year_change_percent = ((latest_value - previous_year_value) / previous_year_value) * Decimal("100")

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
        )

    return StockReportContext(
        ticker=ticker,
        latest=latest,
        recent_prices=points,
        latest_revenue=latest_revenue,
        latest_financial_summary=latest_financial_summary,
    )


def load_market_context_from_yfinance(ticker: str, limit: int = 10) -> StockReportContext:
    points: list[PricePoint] = []
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
        if any(value is not None for value in [trailing_revenue, trailing_net_income, trailing_eps]):
            latest_financial_summary = FinancialSummary(
                report_date="live-info",
                revenue=Decimal(str(trailing_revenue)) if trailing_revenue is not None else None,
                net_income=Decimal(str(trailing_net_income)) if trailing_net_income is not None else None,
                eps=Decimal(str(trailing_eps)) if trailing_eps is not None else None,
            )
        break

    return StockReportContext(
        ticker=ticker,
        latest=points[0] if points else None,
        recent_prices=points,
        latest_revenue=None,
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


def build_report_facts(context: StockReportContext, news_items: list[NewsItem] | None = None) -> ReportFacts:
    news_items = news_items or []
    if not context.latest:
        return ReportFacts(
            rating="中立",
            confidence="低",
            summary="目前缺少有效價格資料，無法形成可靠判讀。",
            key_points=["尚未取得 canonical 價格資料"],
            price_observation="價格資料不足。",
            fundamental_observation="基本面資料不足。",
            valuation_observation="估值資料不足。",
            valuation_label="合理",
            valuation_range="合理價區間：資料不足。",
            news_observation=_news_observation(news_items),
            risk_flags=["資料完整度不足可能導致誤判"],
            conclusion="待資料補齊後再進行分析。",
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
            f"最近財報 EPS {_fmt_price(context.latest_financial_summary.eps)}、淨利 {_fmt_revenue_in_100m(context.latest_financial_summary.net_income)}。"
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
    trailing_pe = None
    if context.latest and context.latest.close_price is not None and context.latest_financial_summary and context.latest_financial_summary.eps not in (None, Decimal("0")):
        trailing_pe = context.latest.close_price / context.latest_financial_summary.eps
    valuation_observation = (
        f"以最新收盤價與近一期 EPS 粗估，本益比約 {_fmt_price(trailing_pe)} 倍，評價已不算便宜，後續需由獲利成長消化。"
        if trailing_pe is not None
        else "目前缺少足夠每股盈餘或價格資料，估值區間暫時無法完整判讀。"
    )
    lower_bound = context.latest_financial_summary.eps * Decimal('20') if context.latest_financial_summary and context.latest_financial_summary.eps is not None else None
    upper_bound = context.latest_financial_summary.eps * Decimal('25') if context.latest_financial_summary and context.latest_financial_summary.eps is not None else None
    valuation_label = "合理"
    if context.latest and context.latest.close_price is not None and lower_bound is not None and upper_bound is not None:
        if context.latest.close_price > upper_bound:
            valuation_label = "偏高"
        elif context.latest.close_price < lower_bound:
            valuation_label = "偏低"
        else:
            valuation_label = "合理"
    valuation_range = (
        f"合理價區間：約 { _fmt_price(lower_bound) } - { _fmt_price(upper_bound) }，高於區間上緣代表市場已提前反映成長。"
        if lower_bound is not None and upper_bound is not None
        else "合理價區間：資料不足。"
    )
    news_observation = _news_observation(news_items)
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
        summary=summary,
        key_points=key_points,
        price_observation=price_observation,
        fundamental_observation=fundamental_observation,
        valuation_observation=valuation_observation,
        valuation_label=valuation_label,
        valuation_range=valuation_range,
        news_observation=news_observation,
        risk_flags=risk_flags,
        conclusion=conclusion,
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
        "重點摘要",
        facts.summary,
        "",
        "重點摘要（條列）",
        *[f"- {point}" for point in facts.key_points],
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
