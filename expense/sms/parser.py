"""SMS -> transaction parsing engine for Indian bank / UPI / card alerts.

Design goals:
  * Pure-Python, no Kivy import, fully unit-testable.
  * Rule-driven: each rule has a sender match + an optional bank label. The
    generic extractors (amount/direction/merchant/account/ref) then do the
    heavy lifting, so adding a bank usually needs no new regex.
  * Returns a ParsedSms dataclass; None when the text is not a transaction.

Real Indian alert samples this handles (see data/sample_sms.json):
  HDFC : "Sent Rs.1,249.00 From HDFC Bank A/C *1234 To SWIGGY On 28-06 Ref 418876534521"
  ICICI: "ICICI Bank Acct XX123 debited for Rs 2,000.00 on 28-Jun-24; AMAZON. UPI:4188..."
  SBI  : "Dear Customer, Rs.45000 credited to A/c XX1234 on 28/06/24-SBI"
  AXIS : "Spent Card no. XX1234 INR 750 28-06-24 ZOMATO Avl Lmt INR 24,250"
"""

import re
from dataclasses import dataclass, field, asdict
from typing import Optional


DEBIT_WORDS = ("debited", "spent", "sent", "paid", "withdrawn", "purchase",
               "debit", "deducted")
CREDIT_WORDS = ("credited", "received", "deposited", "credit", "refund",
                "reversed", "added")

# Money like "Rs.1,249.00", "INR 750", "Rs 2,000", "₹500"
AMOUNT_RE = re.compile(
    r"(?:rs|inr|₹)\.?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.IGNORECASE)

# Masked account / card tail: A/C *1234, Acct XX123, Card no. XX1234, a/c ..1234
ACCOUNT_RE = re.compile(
    r"(?:a/?c|acct|account|card)\s*(?:no\.?)?\s*[xX\*\.]+\s*(\d{3,6})",
    re.IGNORECASE)

# Reference: Ref 418..., UPI:418..., txn no 418..., RRN 4188
REF_RE = re.compile(
    r"(?:ref(?:erence)?|upi|txn|rrn|imps|neft)\s*(?:no\.?|id|:)?\s*[:#]?\s*"
    r"([A-Za-z0-9]{6,})", re.IGNORECASE)

# Merchant after To/At/VPA up to a stop word. Deliberately excludes "for",
# because "debited for Rs 2,000" would otherwise capture the amount as merchant.
MERCHANT_RE = re.compile(
    r"\b(?:to|at|towards|vpa)\s+"
    r"([A-Za-z0-9][A-Za-z0-9 &.\-_@]{1,40}?)"
    r"(?=\s+(?:on|ref|upi|rs|inr|avl|bal|not|txn|dt|date|info)\b|[.;,]|$)",
    re.IGNORECASE)

# Reject "merchants" that are really just an amount fragment (Rs 2, INR 750…)
_AMOUNT_LIKE_RE = re.compile(r"^(?:rs|inr|₹)\b|^\d", re.IGNORECASE)


@dataclass
class ParsedSms:
    raw: str
    sender: str
    bank: str = "OTHER"
    amount: float = 0.0
    direction: str = "debit"          # 'debit' | 'credit'
    merchant: str = ""
    account_last4: str = ""
    ref: str = ""
    confidence: float = 0.0           # 0..1 heuristic
    is_transaction: bool = True
    matched_rule: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class Rule:
    name: str
    bank: str
    sender_match: str                 # substring/regex matched against sender id
    enabled: bool = True
    keywords: tuple = field(default_factory=tuple)  # extra must-contain hints


# Default per-bank rules. `sender_match` is matched case-insensitively against
# the SMS sender id (e.g. "VM-HDFCBK", "AD-ICICIB"). Editable in the app.
DEFAULT_RULES = [
    Rule("HDFC Bank", "HDFC", r"hdfc"),
    Rule("ICICI Bank", "ICICI", r"icici"),
    Rule("State Bank of India", "SBI", r"sbi|sbiinb|sbipsg"),
    Rule("Axis Bank", "AXIS", r"axis|axisbk"),
    Rule("Kotak Bank", "KOTAK", r"kotak|kmbl"),
]


def _clean_amount(text):
    try:
        return float(text.replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _detect_direction(text):
    low = text.lower()
    debit_hit = any(w in low for w in DEBIT_WORDS)
    credit_hit = any(w in low for w in CREDIT_WORDS)
    if credit_hit and not debit_hit:
        return "credit"
    if debit_hit and not credit_hit:
        return "debit"
    # Both/neither: bias by the earliest-occurring keyword
    first_debit = min((low.find(w) for w in DEBIT_WORDS if w in low), default=10**9)
    first_credit = min((low.find(w) for w in CREDIT_WORDS if w in low), default=10**9)
    return "credit" if first_credit < first_debit else "debit"


def _detect_bank(sender, rules):
    for rule in rules:
        if not rule.enabled:
            continue
        if re.search(rule.sender_match, sender or "", re.IGNORECASE):
            return rule.bank, rule.name
    return "OTHER", ""


def _looks_like_transaction(text):
    low = text.lower()
    has_money = bool(AMOUNT_RE.search(text))
    has_action = any(w in low for w in DEBIT_WORDS + CREDIT_WORDS)
    # OTP / promo guards
    if "otp" in low or "one time password" in low:
        return False
    return has_money and has_action


def parse_sms(text, sender="", rules=None):
    """Parse a single SMS. Returns ParsedSms, or None if not a transaction."""
    if rules is None:
        rules = DEFAULT_RULES
    if not text or not _looks_like_transaction(text):
        return None

    bank, rule_name = _detect_bank(sender, rules)

    amount_match = AMOUNT_RE.search(text)
    amount = _clean_amount(amount_match.group(1)) if amount_match else 0.0
    direction = _detect_direction(text)

    merchant_match = MERCHANT_RE.search(text)
    merchant = merchant_match.group(1).strip(" .-_") if merchant_match else ""
    merchant = re.sub(r"\s{2,}", " ", merchant)
    # Guard: if we accidentally grabbed an amount fragment, drop it
    if merchant and _AMOUNT_LIKE_RE.search(merchant):
        merchant = ""

    acc_match = ACCOUNT_RE.search(text)
    account_last4 = acc_match.group(1)[-4:] if acc_match else ""

    ref_match = REF_RE.search(text)
    ref = ref_match.group(1) if ref_match else ""

    # Confidence: reward each cleanly-extracted field
    confidence = 0.4
    if amount:
        confidence += 0.25
    if bank != "OTHER":
        confidence += 0.15
    if merchant:
        confidence += 0.1
    if account_last4:
        confidence += 0.05
    if ref:
        confidence += 0.05
    confidence = round(min(confidence, 1.0), 2)

    return ParsedSms(
        raw=text,
        sender=sender,
        bank=bank,
        amount=amount,
        direction=direction,
        merchant=merchant,
        account_last4=account_last4,
        ref=ref,
        confidence=confidence,
        is_transaction=True,
        matched_rule=rule_name,
    )
