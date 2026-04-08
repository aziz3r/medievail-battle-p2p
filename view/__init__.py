# view/__init__.py
"""
View layer - Presentation and user interface
Contains GUI, terminal view, and menu
"""

from .views import GUI
from .terminal_view import TerminalView
from .menu import MainMenu

__all__ = [
    'GUI',
    'TerminalView',
    'MainMenu',
]
