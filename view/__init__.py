# view/__init__.py
"""
View layer - Presentation and user interface.
"""

from .views import GUI
from .menu import MainMenu

try:
    from .terminal_view import TerminalView
except ModuleNotFoundError as exc:
    # Windows can miss the optional curses module.
    if exc.name == "_curses":
        TerminalView = None
    else:
        raise

__all__ = ["GUI", "TerminalView", "MainMenu"]
