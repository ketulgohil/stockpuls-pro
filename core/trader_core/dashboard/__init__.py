"""trader_core.dashboard - Dalal Street Decision Deck Dashboard."""

from .aggregator import DashboardAggregator, DEFAULT_SYMBOLS
from .confluence import (
    score_technical,
    score_fundamental,
    calculate_position_sizing,
    evaluate_confluence,
)

__all__ = [
    "DashboardAggregator",
    "DEFAULT_SYMBOLS",
    "score_technical",
    "score_fundamental",
    "calculate_position_sizing",
    "evaluate_confluence",
]
