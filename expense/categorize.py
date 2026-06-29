"""Merchant-name -> category inference.

Pure data + functions so it can be unit-tested without Kivy. The keyword map
is intentionally simple and extensible; in a real build users could edit it,
mirroring Cashew's editable categories.
"""

# Ordered so more specific keywords win where they overlap.
MERCHANT_KEYWORDS = {
    "Food": [
        "swiggy", "zomato", "dominos", "mcdonald", "kfc", "starbucks",
        "cafe", "restaurant", "eatfit", "biryani", "pizza", "dunkin",
    ],
    "Groceries": [
        "bigbasket", "blinkit", "zepto", "dmart", "grofers", "instamart",
        "reliance fresh", "more retail", "supermarket", "kirana",
    ],
    "Shopping": [
        "amazon", "amzn", "flipkart", "myntra", "ajio", "meesho", "nykaa",
        "tatacliq", "lifestyle", "decathlon", "ikea", "croma",
    ],
    "Transport": [
        "uber", "ola", "rapido", "irctc", "redbus", "metro", "indianoil",
        "iocl", "hpcl", "bpcl", "fuel", "petrol", "fastag", "namma",
    ],
    "Bills": [
        "electricity", "recharge", "airtel", "jio", "vodafone", "bescom",
        "gas", "water board", "broadband", "postpaid", "bill pay", "lic",
    ],
    "Entertainment": [
        "netflix", "spotify", "hotstar", "prime video", "bookmyshow",
        "pvr", "inox", "youtube", "gaming", "playstation",
    ],
    "Health": [
        "pharmacy", "apollo", "1mg", "pharmeasy", "hospital", "clinic",
        "medical", "diagnostic", "practo", "cult.fit",
    ],
}


def categorize(merchant, direction=None):
    """Return a best-guess category for a merchant string.

    Credits default to 'Income'; unknown debits to 'Uncategorized'.
    """
    if direction == "credit":
        # Salary/refund/transfer-in all bucket to Income unless merchant hints
        text = (merchant or "").lower()
        if any(k in text for k in ("refund", "reversal", "cashback")):
            return "Income"
        return "Income"

    text = (merchant or "").lower()
    for category, keywords in MERCHANT_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return category
    return "Uncategorized"
