from .screenshot import Screenshot, capture
from .display import main_display_logical_size
from .app_info import (
    apps_match,
    ensure_frontmost,
    frontmost_app_name,
    maximize_front_window,
    open_app,
    quit_app,
)

__all__ = [
    "Screenshot",
    "capture",
    "main_display_logical_size",
    "frontmost_app_name",
    "apps_match",
    "ensure_frontmost",
    "maximize_front_window",
    "open_app",
    "quit_app",
]
