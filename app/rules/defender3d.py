from app.rules.ruleset import rules_basic
from app.adapters.emailrep import score_email
from app.adapters.ipintel import score_ip
from app.adapters.botcheck import score_device

def defender3d(order: dict) -> dict:
    # Rules-based score
    rules_score, reasons = rules_basic(order)

    # Adapter scores
    email_score = score_email(order.get("email"))
    ip_score = score_ip(order.get("ip"))
    device_score = score_device(order.get("device_id"))

    # Aggregate
    final_score = min(100.0, rules_score + email_score + ip_score + device_score)
    verdict = "green"
    if final_score >= 70:
        verdict = "red"
    elif final_score >= 30:
        verdict = "amber"

    # Adapter reasons (stub: add if score > 0)
    if email_score > 0:
        reasons.append("email_adapter")
    if ip_score > 0:
        reasons.append("ip_adapter")
    if device_score > 0:
        reasons.append("device_adapter")

    return {
        "rules_score": rules_score,
        "final_score": final_score,
        "verdict": verdict,
        "reasons": reasons
    }
