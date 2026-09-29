from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

class DeskFinding(BaseModel):
    desk: Literal["ACTIVITY", "TECHNICAL", "NEWS", "FUNDAMENTALS"]
    symbol: str
    headline: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    significance: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    timestamp: str

class BullBearReview(BaseModel):
    bull_case: str
    bull_catalysts: List[str] = Field(default_factory=list)
    bear_case: str
    bear_risks: List[str] = Field(default_factory=list)
    invalidation_level: Optional[float] = None
    target_resistance: Optional[float] = None
    key_support: Optional[float] = None
    consensus_bias: Literal[
        "STRONG_BULLISH", "MODERATE_BULLISH", "NEUTRAL", "MODERATE_BEARISH", "STRONG_BEARISH"
    ] = "NEUTRAL"
    confidence_score: int = Field(default=50, ge=0, le=100)

class SentinelAlert(BaseModel):
    id: str
    symbol: str
    title: str
    summary: str
    severity: Literal["INFO", "HIGH", "CRITICAL"] = "INFO"
    findings: List[DeskFinding] = Field(default_factory=list)
    analysis: BullBearReview
    created_at: str
    data_as_of: str

class MarketDigest(BaseModel):
    id: str
    routine_type: Literal["PRE_MARKET", "MIDDAY_PULSE", "POST_MARKET_WRAP"]
    title: str
    summary: str
    macro_cues: List[str] = Field(default_factory=list)
    top_stocks_in_focus: List[str] = Field(default_factory=list)
    sector_leaders: List[str] = Field(default_factory=list)
    sector_laggards: List[str] = Field(default_factory=list)
    timestamp: str

class SentinelConfig(BaseModel):
    enabled: bool = True
    scan_interval_seconds: int = 30
    volume_threshold_multiplier: float = 2.5
    tracked_symbols: List[str] = Field(default_factory=list)
    telegram_alerts_enabled: bool = True
    audio_chime_enabled: bool = True
