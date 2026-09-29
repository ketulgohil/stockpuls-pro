"""Specialist research desks for Sentinel."""
from core.sentinel.desks.activity_desk import ActivityDesk
from core.sentinel.desks.technical_desk import TechnicalDesk
from core.sentinel.desks.news_desk import NewsDesk
from core.sentinel.desks.fundamentals_desk import FundamentalsDesk

__all__ = [
    "ActivityDesk",
    "TechnicalDesk",
    "NewsDesk",
    "FundamentalsDesk",
]
