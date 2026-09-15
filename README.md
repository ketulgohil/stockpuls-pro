# 📈 StockPulse Pro v5.0

A full-featured **Indian Stock Market Analytics Platform** built with FastAPI, featuring real-time WebSocket streaming, technical analysis, AI-powered insights, and 20+ modules.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## ✨ Features

### 🔴 Live Market Features
- **WebSocket Live Prices** — Real-time streaming for NIFTY 50, SENSEX, BANKNIFTY, NIFTY IT, MIDCAP 100
- **Market Status Bar** — Auto-detect market OPEN/CLOSED/PRE-OPEN with live clock
- **Market Pulse Gauge** — Visual sentiment indicator (-100 to +100)
- **Volume Alerts** — Unusual volume detection with BUY/SELL/WATCH signals
- **Option Chain** — NIFTY calls/puts with OI, IV, PCR ratio
- **Market Depth** — 5-level order book simulation

### 📊 Dashboard & Analysis
- Interactive **candlestick charts** (TradingView Lightweight Charts)
- **20+ Technical Indicators** — RSI, MACD, SMA, EMA, Bollinger Bands, ATR, ADX, VWAP, Ichimoku, Fibonacci
- **Stock Screener** — Custom filters + pre-built strategies
- **Trading Signals** — Automated BUY/SELL from RSI, MACD, Bollinger, MFI crossovers
- **Sector Analysis** — Performance breakdown by sector
- **Stock Comparison** — Side-by-side comparison of up to 3 stocks

### 🤖 AI-Powered Features
- **Gemini AI Analysis** — Deep stock analysis with target prices & stop losses
- **AI Chat Assistant** — Ask anything about stocks
- **Market Mood** — Rule-based sentiment analysis
- **Trending Stocks** — AI-driven trending detection

### 💰 Portfolio & Tracking
- **Portfolio Tracking** — Live P&L with portfolio analytics
- **Watchlist** — Track favorite stocks with live prices
- **Price Alerts** — Price, RSI, and multi-condition Smart Alerts
- **Telegram Integration** — Get alerts on Telegram

### 📈 Advanced Features
- **Backtesting** — Test RSI, MACD, SMA strategies on historical data
- **Correlation Matrix** — Cross-stock correlation analysis
- **Market Breadth** — A/D ratio, SMA breadth indicators
- **Global Markets** — US, Asian, European indices + commodities
- **IPO Dashboard** — Upcoming IPOs with GMP data
- **Financial Calculators** — SIP, Tax, Position Size, Fibonacci, Gold Value

### 📊 Market Data
- **Top Gainers/Losers** — Auto-refresh every 60 seconds
- **FII/DII Activity** — Institutional money flow
- **Block Deals** — Bulk/block deal tracking
- **Earnings Calendar** — Quarterly results tracker
- **Mutual Funds** — Top Indian mutual funds with returns

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/ketulgohil/stockpuls-pro.git
cd stockpuls-pro

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Access the App
Open your browser and go to:
```
http://localhost:8000
```

---

## 🐳 Docker Deployment

```bash
# Build the image
docker build -t stockpulse .

# Run the container
docker run -p 8000:8000 stockpulse
```

---

## 📁 Project Structure

```
stockpuls-pro/
├── api/                    # API route handlers
│   ├── stocks.py          # Stock data endpoints
│   ├── market.py          # Market overview endpoints
│   ├── screener.py        # Stock screener
│   ├── signals.py         # Trading signals
│   ├── sector.py          # Sector analysis
│   ├── portfolio.py       # Portfolio management
│   ├── alerts.py          # Price alerts
│   ├── gemini.py          # Gemini AI integration
│   └── ...
├── core/                   # Business logic
│   ├── data_fetcher.py    # Yahoo Finance data fetching
│   ├── indicators.py      # Technical indicator calculations
│   ├── cache.py           # In-memory caching
│   ├── signals.py         # Signal generation logic
│   └── ...
├── db/                     # Database layer
│   └── database.py        # SQLite database
├── data/                   # Data storage
│   ├── portfolio.json     # Portfolio holdings
│   ├── watchlist.json     # Watchlist stocks
│   └── alerts.json        # Price alerts
├── static/                 # Frontend files
│   ├── index.html         # Main HTML (SPA)
│   ├── js/app.js          # JavaScript application
│   ├── css/style.css      # Styling
│   ├── manifest.json      # PWA manifest
│   └── sw.js              # Service worker
├── main.py                 # FastAPI application entry
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker configuration
├── fly.toml               # Fly.io deployment config
└── run.sh                 # Quick start script
```

---

## 🔌 API Endpoints

### Market Data
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/market/overview` | GET | Market overview with indices |
| `/api/market/top-gainers` | GET | Top gaining stocks |
| `/api/market/top-losers` | GET | Top losing stocks |
| `/api/market/status` | GET | Market open/closed status |
| `/api/market/pulse` | GET | Market sentiment score |
| `/api/market/volume-alerts` | GET | Unusual volume stocks |
| `/api/market/depth/{symbol}` | GET | Order book simulation |

### Stock Data
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stocks` | GET | List all stocks |
| `/api/stocks/{symbol}` | GET | Stock details |
| `/api/stocks/{symbol}/history` | GET | Historical price data |
| `/api/stocks/{symbol}/live` | GET | Live price |
| `/api/stocks/{symbol}/analyze` | GET | AI analysis |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `ws://host:8000/ws/live-prices` | Real-time price streaming |

### Analysis
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/screen` | GET | Stock screener |
| `/api/signals` | GET | Trading signals |
| `/api/backtest` | POST | Strategy backtesting |
| `/api/correlation` | GET | Correlation matrix |
| `/api/breadth` | GET | Market breadth |
| `/api/options/chain` | GET | Option chain data |

### Portfolio
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/portfolio/holdings` | GET | Get holdings |
| `/api/portfolio/holdings` | POST | Add holding |
| `/api/portfolio/live-pnl` | GET | Live P&L |
| `/api/watchlist` | GET | Get watchlist |

### AI & Analysis
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/gemini/analyze` | POST | AI stock analysis |
| `/api/gemini/chat` | POST | AI chat |
| `/api/ai/market-mood` | GET | Market sentiment |
| `/api/ai/trending` | GET | Trending stocks |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Frontend** | Vanilla JavaScript, HTML5, CSS3 |
| **Charts** | TradingView Lightweight Charts v4.1.3 |
| **Data Source** | Yahoo Finance (yfinance), Downstox API |
| **Database** | SQLite |
| **AI** | Google Gemini API |
| **Caching** | In-memory (30s - 10min TTL) |
| **Deployment** | Docker, Fly.io, Replit |

---

## 📦 Dependencies

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
yfinance>=0.2.31
pandas>=2.1.0
numpy>=1.25.0
aiofiles>=23.2.0
python-multipart>=0.0.6
requests>=2.31.0
```

---

## 🔧 Configuration

### Gemini AI (Optional)
1. Get API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Add via Settings → Gemini API Configuration in the app

### Telegram Alerts (Optional)
1. Create a Telegram bot via [@BotFather](https://t.me/BotFather)
2. Configure in the app's Alerts section

---

## 🌐 Deployment Options

| Platform | Credit Card? | Free Tier | Always-On |
|----------|--------------|-----------|-----------|
| **Replit** | ❌ No | ✅ Yes | ⚠️ Limited |
| **Fly.io** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Render** | ✅ Yes | ✅ Yes | ⚠️ Spins down |
| **Oracle Cloud** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Docker (Local)** | ❌ No | ✅ Yes | ✅ Yes |

### Deploy to Replit
1. Import from GitHub
2. Set run command: `python3 -m uvicorn main:app --host 0.0.0.0 --port 8000`
3. Click Run

---

## ⚠️ Important Notes

- **Market Hours**: Indian market operates 9:15 AM - 3:30 PM IST (Mon-Fri)
- **Data Delay**: Yahoo Finance data may have 15-min delay during market hours
- **Rate Limiting**: yfinance may rate-limit frequent requests; caching helps
- **Not Financial Advice**: This tool is for educational purposes only

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

---

## 👨‍💻 Author

**Ketul Gohil** - [@ketulgohil](https://github.com/ketulgohil)

---

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

---

## ⭐ Star History

If you find this useful, give it a ⭐ on GitHub!
