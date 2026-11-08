"""Confluence Scoring & Risk Sizing Engine for Dalal Street Dashboard.

Combines short-term technical indicators (5m ORB, VWAP, volume surge, MA20)
and fundamental disclosures (8-quarter statements, TTM PAT YoY, margins)
into a unified 0-100 Confluence Score with INR position sizing.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def score_technical(tech: Dict[str, Any]) -> int:
    """Computes short-term technical momentum score (0-100)."""
    if not tech:
        return 50

    score = 40  # base baseline

    # ORB breakout / breakdown
    if tech.get("orb_breakout"):
        score += 30
    elif tech.get("below_orb_low"):
        score -= 30

    # Volume surge
    vol_ratio = tech.get("volume_ratio", 1.0) or 1.0
    if vol_ratio >= 1.75:
        score += 25
    elif vol_ratio >= 1.25:
        score += 18
    elif vol_ratio < 0.75:
        score -= 10

    # VWAP positioning
    if tech.get("above_vwap") is True:
        score += 15
    elif tech.get("above_vwap") is False:
        score -= 15

    # Trend / Reclaim
    if tech.get("reclaim_ma20"):
        score += 10
    if tech.get("oversold_bounce") or tech.get("oversold"):
        score += 10

    return max(0, min(100, score))


def score_fundamental(fund: Dict[str, Any]) -> int:
    """Computes fundamental health score (0-100) based on 8-quarter metrics."""
    if not fund:
        return 50  # neutral default when financials unavailable

    score = 0

    # 1. TTM PAT YoY Growth (max 35 pts)
    pat_growth = fund.get("ttm_pat_growth_yoy")
    if pat_growth is not None:
        if pat_growth >= 20.0:
            score += 35
        elif pat_growth >= 10.0:
            score += 28
        elif pat_growth >= 0.0:
            score += 15
        elif pat_growth >= -10.0:
            score += 5
        else:
            score += 0
    else:
        score += 15  # neutral baseline if missing

    # 2. Operating Margin & Expansion (max 25 pts)
    op_margin = fund.get("operating_margin")
    if op_margin is not None:
        if op_margin >= 20.0:
            score += 20
        elif op_margin >= 15.0:
            score += 16
        elif op_margin >= 10.0:
            score += 10
        else:
            score += 5
        if fund.get("margin_expanding"):
            score += 5
    else:
        score += 10

    # 3. Quarterly Growth Consistency (max 20 pts)
    pos_quarters = fund.get("positive_growth_quarters")
    if pos_quarters is not None:
        score += int(min(8, max(0, pos_quarters)) / 8.0 * 20)
    else:
        score += 10

    # 4. TTM Revenue YoY Growth (max 20 pts)
    rev_growth = fund.get("ttm_revenue_growth_yoy")
    if rev_growth is not None:
        if rev_growth >= 15.0:
            score += 20
        elif rev_growth >= 8.0:
            score += 15
        elif rev_growth >= 0.0:
            score += 8
        else:
            score += 0
    else:
        score += 10

    return max(0, min(100, score))


def calculate_position_sizing(
    price: float,
    stop_loss: float,
    target: float,
    max_risk: float = 5000.0,
    capital: float = 500000.0,
) -> Dict[str, Any]:
    """Calculates integer share allocation strictly respecting max risk and
    capital limit in INR."""
    if price <= 0 or stop_loss >= price:
        return {
            "shares": 0,
            "risk_per_share": 0.0,
            "total_risk": 0.0,
            "capital_required": 0.0,
            "risk_reward_ratio": 0.0,
            "error": "Invalid risk bounds (stop >= entry)",
        }

    risk_per_share = price - stop_loss
    shares = int(max_risk / risk_per_share)

    # Capital constraint ceiling
    if shares * price > capital:
        shares = int(capital / price)

    reward_per_share = max(0.0, target - price)
    rr = (reward_per_share / risk_per_share) if risk_per_share > 0 else 0.0

    return {
        "shares": shares,
        "risk_per_share": round(risk_per_share, 2),
        "total_risk": round(shares * risk_per_share, 2),
        "capital_required": round(shares * price, 2),
        "risk_reward_ratio": round(rr, 2),
    }


def evaluate_confluence(
    tech_data: Dict[str, Any],
    fund_data: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluates combined technical and fundamental signals for a stock."""
    cfg = config or {}
    max_risk = float(cfg.get("max_risk", 5000.0))
    capital = float(cfg.get("capital", 500000.0))

    symbol = tech_data.get("symbol", "")
    price = float(tech_data.get("price", 0.0) or 0.0)

    tech_score = score_technical(tech_data)
    fund_score = score_fundamental(fund_data)

    confluence_score = round(0.55 * tech_score + 0.45 * fund_score)

    # Assign actionable signal badge
    if tech_data.get("below_orb_low") or fund_score < 40 or tech_score < 35:
        signal = "AVOID / SELL SIGNAL"
    elif tech_score >= 70 and fund_score >= 70:
        signal = "CONFIRMED BUY"
    elif fund_score >= 75 and (
        tech_data.get("oversold") or tech_data.get("reclaim_ma20")
    ):
        signal = "BUY ON DIP"
    elif tech_score >= 60:
        signal = "WATCHLIST"
    else:
        signal = "NEUTRAL"

    # Targets & Stops
    orb_low = tech_data.get("orb_low")
    stop_loss = float(orb_low) if orb_low and orb_low < price else round(price * 0.985, 2)
    risk_spread = price - stop_loss
    target = round(price + risk_spread * 2.2, 2) if risk_spread > 0 else round(price * 1.02, 2)

    sizing = calculate_position_sizing(price, stop_loss, target, max_risk, capital)

    return {
        "symbol": symbol,
        "price": price,
        "technical_score": tech_score,
        "fundamental_score": fund_score,
        "confluence_score": confluence_score,
        "signal": signal,
        "entry": price,
        "stop_loss": stop_loss,
        "target": target,
        "sizing": sizing,
        "tech_details": tech_data,
        "fund_details": fund_data,
    }
