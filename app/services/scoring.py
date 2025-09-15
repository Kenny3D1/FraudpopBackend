# scoring.py
from __future__ import annotations
from typing import Dict, List, Tuple, Any

# -----------------------------
# Tunables (Week 2 defaults)
# -----------------------------
MAX_SCORE = 100
THRESHOLDS = {
    "red": 70,     # >= 70 → red
    "amber": 30,   # >= 30 → amber, else green
}

WEIGHTS = {
    "country_mismatch": 30,
    "high_item_count": 10,
    "high_value": 15,
}

HIGH_ITEM_COUNT_N = 5
HIGH_VALUE_AMOUNT = 500.0

# Optional caps for external adapters so they don't dominate
ADAPTER_CAPS = {
    "ip": 30,      # cap IP intel contribution
    "email": 20,   # cap email intel contribution
}

# -----------------------------
# Helpers
# -----------------------------
def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def verdict_for(score: int) -> str:
    if score >= THRESHOLDS["red"]:
        return "red"
    if score >= THRESHOLDS["amber"]:
        return "amber"
    return "green"

def _clean_reason(reason: str | None) -> str | None:
    if not reason:
        return None
    return reason.strip().lower().replace(" ", "_")

# -----------------------------
# Rule-based signals
# -----------------------------
def rules_engine(order: Dict[str, Any]) -> Tuple[int, List[str], Dict[str, Any]]:
    """
    Returns (score, reasons, evidence)
    - evidence contains lightweight facts useful for UI/debug
    """
    reasons: List[str] = []
    total = 0

    b = (order.get("billing_address") or {}) or {}
    s = (order.get("shipping_address") or {}) or {}

    # Country mismatch
    bcc = (b.get("country_code") or b.get("country_code_v2") or "").upper()
    scc = (s.get("country_code") or s.get("country_code_v2") or "").upper()
    if bcc and scc and bcc != scc:
        reasons.append("country_mismatch"); total += WEIGHTS["country_mismatch"]

    # High item count
    li = order.get("line_items") or []
    if len(li) >= HIGH_ITEM_COUNT_N:
        reasons.append("high_item_count"); total += WEIGHTS["high_item_count"]

    # High value
    try:
        tp = float(order.get("total_price") or order.get("total_price_set", {}).get("shop_money", {}).get("amount") or 0.0)
    except Exception:
        tp = 0.0
    if tp > HIGH_VALUE_AMOUNT:
        reasons.append("high_value"); total += WEIGHTS["high_value"]

    evidence = {
        "billing_country": bcc or None,
        "shipping_country": scc or None,
        "line_item_count": len(li),
        "total_price": tp,
    }
    return total, reasons, evidence

# -----------------------------
# External adapters (stubs)
# Normalize to 0..N, return (score, reason, evidence)
# -----------------------------
def call_ip_intel(ip: str | None) -> Tuple[int, str | None, Dict[str, Any]]:
    if not ip:
        return 0, "ip_missing", {"ip": None}
    # TODO: integrate real providers, normalize to 0..ADAPTER_CAPS["ip"]
    score = clamp(20, 0, ADAPTER_CAPS["ip"])  # example
    return int(score), "ip_proxy_or_dc", {"ip": ip, "provider": "stub"}

def call_email_intel(email: str | None) -> Tuple[int, str | None, Dict[str, Any]]:
    if not email:
        return 0, "email_missing", {"email": None}
    # TODO: integrate real providers, normalize to 0..ADAPTER_CAPS["email"]
    score = clamp(10, 0, ADAPTER_CAPS["email"])  # example
    return int(score), "email_disposable_domain", {"email_domain": (email.split("@")[1] if "@" in email else None), "provider": "stub"}

# -----------------------------
# Main entry
# -----------------------------
def compute_risk(
    order_payload: Dict[str, Any],
    vault: Dict[str, Any] | None = None,
    context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Returns:
      {
        "score": int (0..100),
        "verdict": "green"|"amber"|"red",
        "reasons": [str],
        "evidence": { ... }   # lightweight, safe-to-expose
      }
    Notes:
      - `vault` can include repeat counts, chargeback history, etc. (hook for Week 2+)
      - `context` can pass aux info like source_ip, currency, totals, etc.
    """
    order = order_payload or {}
    ctx = context or {}

    # ---- Rules
    base_score, base_reasons, base_evidence = rules_engine(order)

    # ---- External adapters
    email = (order.get("customer") or {}).get("email") or order.get("email")
    ip = (order.get("client_details") or {}).get("browser_ip") or ctx.get("source_ip")

    ip_score, ip_reason, ip_evd = call_ip_intel(ip)
    em_score, em_reason, em_evd = call_email_intel(email)

    # ---- Vault (stub normalization)
    # Example: add 5 if device/email/ip seen in chargebacks > 0, add 2 if high repeat velocity, etc.
    vault_score = 0
    vault_reasons: List[str] = []
    vault_evidence: Dict[str, Any] = {}
    if vault:
        # simple example signals (customize once vault schema is finalized)
        outcomes = (vault or {}).get("outcomes") or {}
        chargebacks = int(outcomes.get("chargeback", 0))
        if chargebacks > 0:
            vault_score += 5
            vault_reasons.append("vault_chargeback_history")
        vault_evidence = {"vault_outcomes": outcomes, "vault_score": vault_score}

    # ---- Aggregate
    raw_score = base_score + ip_score + em_score + vault_score
    score = int(clamp(raw_score, 0, MAX_SCORE))

    # ---- Reasons & Evidence
    reasons: List[str] = []
    reasons.extend(base_reasons)
    if ip_reason: reasons.append(_clean_reason(ip_reason))
    if em_reason: reasons.append(_clean_reason(em_reason))
    reasons.extend(vault_reasons)
    # dedupe while preserving order
    seen = set()
    reasons = [r for r in reasons if r and (r not in seen and not seen.add(r))]

    evidence = {
        "rules": base_evidence,
        "ip": ip_evd,
        "email": em_evd,
        "vault": vault_evidence or None,
        "context": ctx or None,
    }

    return {
        "score": score,
        "verdict": verdict_for(score),
        "reasons": reasons,
        "evidence": evidence,
    }
