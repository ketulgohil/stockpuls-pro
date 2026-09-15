import yfinance as yf
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


def get_exchange_rate(from_currency: str, to_currency: str = "INR") -> Optional[dict]:
    try:
        symbol = f"{from_currency}{to_currency}=X"
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")
        
        if hist.empty:
            return None
        
        current_rate = hist['Close'].iloc[-1]
        prev_rate = hist['Close'].iloc[-2] if len(hist) > 1 else current_rate
        
        # Get 52 week high/low
        week_data = ticker.history(period="1y")
        high_52w = week_data['High'].max() if not week_data.empty else current_rate
        low_52w = week_data['Low'].min() if not week_data.empty else current_rate
        
        return {
            "from": from_currency,
            "to": to_currency,
            "rate": round(current_rate, 4),
            "change": round(current_rate - prev_rate, 4),
            "changePct": round(((current_rate - prev_rate) / prev_rate) * 100, 2),
            "high52w": round(high_52w, 4),
            "low52w": round(low_52w, 4),
            "inverseRate": round(1 / current_rate, 6) if current_rate > 0 else 0,
            "currencies": CURRENCIES
        }
    except Exception as e:
        return None


def convert(amount: float, from_currency: str, to_currency: str = "INR") -> dict:
    rate_data = get_exchange_rate(from_currency, to_currency)
    if not rate_data:
        return {"error": "Could not fetch exchange rate"}
    
    converted = amount * rate_data["rate"]
    
    return {
        "amount": amount,
        "from": from_currency,
        "to": to_currency,
        "rate": rate_data["rate"],
        "convertedAmount": round(converted, 2)
    }
