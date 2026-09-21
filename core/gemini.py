import google.generativeai as genai
import json
from typing import Optional
from core.data_fetcher import get_stock_data, get_stock_info
from core.indicators import add_all_indicators, get_latest_indicators


GEMINI_API_KEY = ""


def configure_gemini(api_key: str):
    global GEMINI_API_KEY
    GEMINI_API_KEY = api_key
    genai.configure(api_key=api_key)


def get_gemini_model():
    if not GEMINI_API_KEY:
        return None
    return genai.GenerativeModel('gemini-2.0-flash')


def analyze_stock_with_gemini(symbol: str) -> dict:
    model = get_gemini_model()
    if not model:
        return {"error": "Gemini API key not configured. Go to AI tab → Settings to add your key."}
    
    try:
        stock_info = get_stock_info(symbol)
        df = get_stock_data(symbol, period="3mo")
        
        technical_data = "No technical data available"
        if df is not None and not df.empty:
            df = add_all_indicators(df)
            latest = df.iloc[-1]
            technical_data = f"""
Price: ₹{latest['Close']:.2f}
RSI: {latest.get('RSI', 'N/A'):.2f if not latest.get('RSI') != latest.get('RSI') else 'N/A'}
MACD: {latest.get('MACD', 'N/A'):.2f if not latest.get('MACD') != latest.get('MACD') else 'N/A'}
SMA20: ₹{latest.get('SMA_20', 'N/A'):.2f if not latest.get('SMA_20') != latest.get('SMA_20') else 'N/A'}
SMA50: ₹{latest.get('SMA_50', 'N/A'):.2f if not latest.get('SMA_50') != latest.get('SMA_50') else 'N/A'}
ATR: {latest.get('ATR', 'N/A'):.2f if not latest.get('ATR') != latest.get('ATR') else 'N/A'}
"""
        
        stock_context = f"""
Stock: {symbol}
Name: {stock_info.get('name', symbol) if stock_info else symbol}
Sector: {stock_info.get('sector', 'Unknown') if stock_info else 'Unknown'}
P/E Ratio: {stock_info.get('pe', 'N/A') if stock_info else 'N/A'}
Market Cap: {stock_info.get('marketCap', 'N/A') if stock_info else 'N/A'}

Technical Data:
{technical_data}
"""
        
        prompt = f"""You are an expert Indian stock market analyst. Analyze this stock and provide:

1. **Recommendation**: BUY / SELL / HOLD (with confidence level: High/Medium/Low)
2. **Target Price**: ₹ (based on technical analysis)
3. **Stop Loss**: ₹ 
4. **Risk Level**: Low / Medium / High
5. **Timeframe**: Short-term (1-2 weeks) / Medium-term (1-3 months) / Long-term (6+ months)
6. **Key Reasons**: 3-5 bullet points for your recommendation
7. **Key Risks**: 2-3 risks to watch
8. **News Sentiment Impact**: How current news affects this stock

Stock Data:
{stock_context}

Provide your analysis in this JSON format:
{{
    "recommendation": "BUY/SELL/HOLD",
    "confidence": "High/Medium/Low",
    "target_price": "₹XXX",
    "stop_loss": "₹XXX",
    "risk_level": "Low/Medium/High",
    "timeframe": "Short/Medium/Long",
    "reasons": ["reason1", "reason2", "reason3"],
    "risks": ["risk1", "risk2"],
    "news_impact": "Brief analysis of news impact",
    "summary": "One paragraph summary"
}}

Be specific with numbers. Analyze based on Indian market conditions. Remember this is for educational purposes only."""

        response = model.generate_content(prompt)
        
        text = response.text
        
        json_start = text.find('{')
        json_end = text.rfind('}') + 1
        
        if json_start != -1 and json_end != -1:
            json_str = text[json_start:json_end]
            result = json.loads(json_str)
            result["symbol"] = symbol
            result["name"] = stock_info.get("name", symbol) if stock_info else symbol
            result["powered_by"] = "Google Gemini AI"
            return result
        else:
            return {
                "symbol": symbol,
                "summary": text,
                "recommendation": "HOLD",
                "confidence": "Medium",
                "powered_by": "Google Gemini AI"
            }
    except Exception as e:
        return {"error": str(e)}


def ai_chat(message: str, context: str = "") -> dict:
    model = get_gemini_model()
    if not model:
        return {"error": "Gemini API key not configured."}
    
    try:
        prompt = f"""You are StockPulse AI, an expert Indian stock market assistant. 
You help users with:
- Stock analysis and recommendations
- Technical analysis explanation
- Market trends and sentiment
- Portfolio advice
- Risk management

Current Indian market context: {context}

User question: {message}

Provide helpful, accurate, and actionable advice. Always mention that this is for educational purposes and not financial advice. Be concise but thorough."""

        response = model.generate_content(prompt)
        
        return {
            "response": response.text,
            "powered_by": "Google Gemini AI"
        }
    except Exception as e:
        return {"error": str(e)}


def get_market_context() -> str:
    try:
        indices = []
        for symbol in ["^NSEI", "^BSESN"]:
            df = get_stock_data(symbol, period="5d")
            if df is not None and not df.empty:
                change = ((df["Close"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2]) * 100
                indices.append(f"{symbol}: {change:.2f}%")
        return ", ".join(indices)
    except:
        return "Market data unavailable"
