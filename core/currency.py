from typing import Optional

CURRENCIES = {
    "USD": {"name": "US Dollar", "symbol": "$"},
    "EUR": {"name": "Euro", "symbol": "€"},
    "GBP": {"name": "British Pound", "symbol": "£"},
    "JPY": {"name": "Japanese Yen", "symbol": "¥"},
    "CNY": {"name": "Chinese Yuan", "symbol": "¥"},
    "AED": {"name": "UAE Dirham", "symbol": "د.إ"},
    "SGD": {"name": "Singapore Dollar", "symbol": "S$"},
    "HKD": {"name": "Hong Kong Dollar", "symbol": "HK$"},
    "AUD": {"name": "Australian Dollar", "symbol": "A$"},
    "CAD": {"name": "Canadian Dollar", "symbol": "C$"},
    "CHF": {"name": "Swiss Franc", "symbol": "Fr"},
    "KRW": {"name": "South Korean Won", "symbol": "₩"},
}

UNAVAILABLE_ERROR = "Currency data is not available with the current data provider."


def _unavailable(**extra) -> dict:
    return {
        "available": False,
        "error": UNAVAILABLE_ERROR,
        **extra,
    }


def get_exchange_rate(from_currency: str, to_currency: str = "INR") -> Optional[dict]:
    return _unavailable(
        **{
            "from": from_currency,
            "to": to_currency,
            "currencies": CURRENCIES,
        }
    )


def convert(amount: float, from_currency: str, to_currency: str = "INR") -> dict:
    return _unavailable(
        **{
            "amount": amount,
            "from": from_currency,
            "to": to_currency,
        }
    )
