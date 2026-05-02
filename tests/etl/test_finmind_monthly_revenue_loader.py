from decimal import Decimal

from ai_investment_analyst.etl.finmind_monthly_revenue_loader import enrich_growth_fields


def test_enrich_growth_fields_derives_month_over_month_and_year_over_year_percentages():
    rows = [
        {"revenue_year": 2026, "revenue_month": 3, "revenue": 1200},
        {"revenue_year": 2026, "revenue_month": 2, "revenue": 1000},
        {"revenue_year": 2025, "revenue_month": 3, "revenue": 800},
    ]

    enriched = enrich_growth_fields(rows)

    assert enriched[0]["revenue_month_change_percent"] == Decimal("20.0")
    assert enriched[0]["revenue_year_change_percent"] == Decimal("50.0")
    assert enriched[1]["revenue_month_change_percent"] is None
    assert enriched[1]["revenue_year_change_percent"] is None


def test_enrich_growth_fields_preserves_existing_growth_values():
    rows = [
        {
            "revenue_year": 2026,
            "revenue_month": 3,
            "revenue": 1200,
            "revenue_month_change_percent": 19.8,
            "revenue_year_change_percent": 35.1,
        },
        {"revenue_year": 2026, "revenue_month": 2, "revenue": 1000},
        {"revenue_year": 2025, "revenue_month": 3, "revenue": 900},
    ]

    enriched = enrich_growth_fields(rows)

    assert enriched[0]["revenue_month_change_percent"] == Decimal("19.8")
    assert enriched[0]["revenue_year_change_percent"] == Decimal("35.1")
