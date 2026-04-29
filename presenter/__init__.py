# presenter/__init__.py
"""
Presenter layer - Controllers and orchestration
Contains AI controllers, battle CLI, and tournament management
"""

from .ai import (
    BaseController,
    CaptainBraindead,
    MajorDaft,
    SimpleAI
)

__all__ = [
    'BaseController',
    'CaptainBraindead',
    'MajorDaft',
    'SimpleAI',
]
