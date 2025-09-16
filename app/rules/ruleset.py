# app/rules/ruleset.py
from typing import Dict, List, Tuple

def rules_basic(order: Dict) -> Tuple[float, List[str]]:
    """Return (rules_score 0..100, reasons)"""
    score = 0.0
    reasons = []

    # examples (tune thresholds as needed)
    if order.get("billing_country") and order.get("shipping_country"):
        if order["billing_country"] != order["shipping_country"]:
            score += 25; reasons.append("Country mismatch (billing vs shipping)")

    if (order.get("total_price") or 0) > 500:
        score += 15; reasons.append("High-value order")

    email = (order.get("email") or "").lower()
    if email.endswith(".ru") or email.endswith(".cn"):
        score += 10; reasons.append("Suspicious email TLD")

    ip = order.get("ip")
    if ip in {"0.0.0.0", "127.0.0.1"}:
        score += 20; reasons.append("Bogus IP")

    # velocity: provided by vault/adapters—assume order["repeat_email"] added upstream
    if order.get("repeat_email", 0) > 3:
        score += 20; reasons.append("Email seen high velocity")

    return min(score, 100.0), reasons
