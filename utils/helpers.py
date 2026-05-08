"""
Utilities — Shared formatting, date, and display helpers.
"""

import datetime
from typing import Optional


def format_date(date, fmt: str = "%d/%m/%Y") -> str:
    """Format a datetime object as a string, or return 'N/A' if None."""
    if isinstance(date, datetime.datetime):
        return date.strftime(fmt)
    if date:
        return str(date)
    return "N/A"


def format_currency(amount: float) -> str:
    """Format a number as currency string."""
    return f"${amount:,.2f}"


def days_remaining(target_date) -> int:
    """Calculate days remaining until a target date."""
    if not target_date:
        return 0
    if isinstance(target_date, str):
        from data.models import parse_date
        target_date = parse_date(target_date)
    if not isinstance(target_date, datetime.datetime):
        return 0
    delta = target_date - datetime.datetime.now()
    return max(0, delta.days)


def status_icon(status) -> str:
    """Return a status icon for display (ASCII-safe for Windows console)."""
    from data.models import Status
    icons = {
        Status.ON_TRACK: "[OK]",
        Status.AT_RISK: "[!!]",
        Status.DELAYED: "[XX]",
        Status.COMPLETE: "[OK]",
    }
    return icons.get(status, "[??]")


def priority_label(score: float) -> str:
    """Convert a priority score to a human-readable label."""
    if score >= 80:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 20:
        return "MEDIUM"
    return "LOW"


def print_separator(char: str = "=", length: int = 60):
    """Print a separator line."""
    print(char * length)


def print_boxed_header(title: str, width: int = 60):
    """Print a boxed header for section separation."""
    padding = (width - len(title) - 2) // 2
    print(f"{'=' * width}")
    print(f"{' ' * padding}{title}")
    print(f"{'=' * width}")
