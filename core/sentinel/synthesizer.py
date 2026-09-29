import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.sentinel.types import DeskFinding, BullBearReview, MarketDigest
import core.gemini as gemini_core

class GeminiSynthesizer:
    @staticmethod
    def synthesize_alert(symbol: str, current_price: float, findings: List[DeskFinding]) -> BullBearReview:
        client = gemini_core.client
        if not client:
            return GeminiSynthesizer.fallback_synthesis(symbol, current_price, findings)

        try:
            findings_summary = "\n".join([f"- [{f.desk}] {f.headline}" for f in findings])
            prompt = f"""You are the Chief Market Intelligence Officer reviewing multi-desk findings for Indian stock {symbol}.
Current Price: ₹{current_price:.2f}

Specialist Desk Findings:
{findings_summary}

Conduct an adversarial Bull vs. Bear review. You must provide:
1. Bull Case & specific upside catalysts.
2. Bear Case & key risks/invalidation points.
3. Key levels: Invalidation Stop Loss level, Target Resistance, Key Support.
4. Overall consensus bias: STRONG_BULLISH, MODERATE_BULLISH, NEUTRAL, MODERATE_BEARISH, or STRONG_BEARISH.
5. Confidence Score (0 to 100).

Return ONLY valid JSON matching this structure:
{{
  "bull_case": "Concise summary of bull thesis",
  "bull_catalysts": ["catalyst 1", "catalyst 2"],
  "bear_case": "Concise summary of bear risk",
  "bear_risks": ["risk 1", "risk 2"],
  "invalidation_level": 0.0,
  "target_resistance": 0.0,
  "key_support": 0.0,
  "consensus_bias": "MODERATE_BULLISH",
  "confidence_score": 75
}}
"""
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            data = json.loads(text.strip())
            return BullBearReview(**data)
        except Exception:
            return GeminiSynthesizer.fallback_synthesis(symbol, current_price, findings)

    @staticmethod
    def fallback_synthesis(symbol: str, current_price: float, findings: List[DeskFinding]) -> BullBearReview:
        bull_points = []
        bear_points = []
        for f in findings:
            headline_upper = f.headline.upper()
            metrics_str = str(f.metrics).upper()
            if "SURGE" in headline_upper or "BULLISH" in headline_upper or "BULLISH" in metrics_str:
                bull_points.append(f.headline)
            elif "OVERBOUGHT" in headline_upper or "BEARISH" in headline_upper or "BEARISH" in metrics_str:
                bear_points.append(f.headline)
            else:
                bull_points.append(f.headline)

        bull_case = "; ".join(bull_points) if bull_points else "Price momentum stabilizing near support"
        bear_case = "; ".join(bear_points) if bear_points else "Broader market volatility and overhead supply"
        bias = "MODERATE_BULLISH" if len(bull_points) >= len(bear_points) else "MODERATE_BEARISH"

        return BullBearReview(
            bull_case=bull_case,
            bull_catalysts=bull_points if bull_points else ["Volume and technical base"],
            bear_case=bear_case,
            bear_risks=bear_points if bear_points else ["Broader sector pullback"],
            invalidation_level=round(current_price * 0.98, 2) if current_price else None,
            target_resistance=round(current_price * 1.04, 2) if current_price else None,
            key_support=round(current_price * 0.97, 2) if current_price else None,
            consensus_bias=bias,
            confidence_score=65 if findings else 50
        )

    @staticmethod
    def synthesize_market_digest(
        routine_type: str,
        macro_cues: List[str],
        stocks_in_focus: List[str],
        sector_leaders: List[str]
    ) -> MarketDigest:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title_map = {
            "PRE_MARKET": "Pre-Market Intelligence Briefing",
            "MIDDAY_PULSE": "Midday Market Momentum Pulse",
            "POST_MARKET_WRAP": "Post-Market Institutional Wrap"
        }
        title = title_map.get(routine_type, "Market Intelligence Digest")
        summary = f"{title} — Focus on {', '.join(stocks_in_focus[:3]) if stocks_in_focus else 'NIFTY 50'}. Sector leaders: {', '.join(sector_leaders[:3]) if sector_leaders else 'Broad market'}."

        return MarketDigest(
            id=f"digest_{int(datetime.now().timestamp())}",
            routine_type=routine_type,
            title=title,
            summary=summary,
            macro_cues=macro_cues,
            top_stocks_in_focus=stocks_in_focus,
            sector_leaders=sector_leaders,
            sector_laggards=[],
            timestamp=now_str
        )
