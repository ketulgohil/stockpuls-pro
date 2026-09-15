# StockPulse Pro

## Run

The project is a FastAPI application with a static frontend.

- Start it with `./run.sh`.
- The server binds to `0.0.0.0:5000` for Replit's web preview.
- Python dependencies are listed in `requirements.txt`.

The market-data features use public data through `yfinance`. The Gemini feature asks for an API key through the application's settings when used; the rest of the app can run without it.