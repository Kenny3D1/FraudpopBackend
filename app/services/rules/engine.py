# app/services/rules/engine.py
from .rulesets import DEFAULT_RULES

def score_order(order_raw: dict, joins: dict, vault_facts: dict) -> dict:
    reasons = []
    score = 0
    for rule in DEFAULT_RULES:
        hit, inc, why = rule(order_raw, joins, vault_facts)
        if hit:
            score += inc; reasons.append(why)
    verdict = "green" if score < 30 else "amber" if score < 70 else "red"
    return {"score": score, "verdict": verdict, "reasons": reasons}
