from ai_investment_analyst.analysis.watchlist_alerts import plan_watchlist_alert_workflow


def test_plan_watchlist_alert_workflow_adds_high_confidence_buy_to_watchlist():
    plan = plan_watchlist_alert_workflow(
        ticker='2330',
        rating='買進',
        confidence_score=82,
        data_quality_status='fresh',
        close_price=950,
        target_price=1050,
    )

    assert plan.action == 'add_to_watchlist'
    assert plan.priority == 'high'
    assert plan.summary == '加入觀察清單：買進評級且信心足夠。'
    assert [rule.kind for rule in plan.alert_rules] == ['price_reaches_target', 'price_drawdown', 'data_stale']
    assert plan.alert_rules[0].threshold == 1050
    assert plan.alert_rules[1].threshold == 902.5


def test_plan_watchlist_alert_workflow_requires_review_when_data_is_incomplete():
    plan = plan_watchlist_alert_workflow(
        ticker='2454',
        rating='買進',
        confidence_score=76,
        data_quality_status='partial',
        close_price=1200,
        target_price=1300,
    )

    assert plan.action == 'review_before_watchlist'
    assert plan.priority == 'medium'
    assert any(rule.kind == 'data_quality_review' for rule in plan.alert_rules)
    assert '資料品質不足' in plan.rationale[0]


def test_plan_watchlist_alert_workflow_skips_low_confidence_or_negative_rating():
    plan = plan_watchlist_alert_workflow(
        ticker='9999',
        rating='賣出',
        confidence_score=38,
        data_quality_status='fresh',
        close_price=80,
        target_price=70,
    )

    assert plan.action == 'do_not_watch'
    assert plan.priority == 'low'
    assert plan.alert_rules == []
    assert any('評級不支持追蹤' in reason for reason in plan.rationale)
