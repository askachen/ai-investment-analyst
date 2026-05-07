from ai_investment_analyst.db.price_store import _priority_rank


def test_taiwan_stock_price_priority_prefers_official_exchange_sources():
    assert _priority_rank("TW", "stock", "twse") < _priority_rank("TW", "stock", "finmind")
    assert _priority_rank("TW", "stock", "tpex") < _priority_rank("TW", "stock", "finmind")
