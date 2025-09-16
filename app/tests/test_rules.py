# tests/test_rules.py
from app.rules.ruleset import rules_basic

def test_rules_basic_country_mismatch():
    o = {"billing_country":"US","shipping_country":"CA","total_price":100}
    score, reasons = rules_basic(o)
    assert score >= 25
    assert any("Country mismatch" in r for r in reasons)

