"""
Formatting utilities for TUI display
"""
from datetime import datetime, timedelta
from typing import Optional


def format_tokens(n: int) -> str:
    """
    Format token count with K, M, B suffixes.
    
    Examples:
        500 -> "500"
        1500 -> "1.5K"
        1500000 -> "1.5M"
        1500000000 -> "1.5B"
    """
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    elif n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def format_time(seconds: float) -> str:
    """
    Format seconds into HH:MM:SS format.
    
    Examples:
        65 -> "00:01:05"
        3665 -> "01:01:05"
    """
    if seconds < 0:
        return "00:00:00"
    
    td = timedelta(seconds=int(seconds))
    hours, remainder = divmod(td.seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    
    # Handle days if necessary
    if td.days > 0:
        hours += td.days * 24
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_time_elapsed(start_time: Optional[datetime]) -> str:
    """
    Format elapsed time from a start datetime.
    
    Args:
        start_time: The start datetime, or None
        
    Returns:
        Formatted time string like "01:23:45"
    """
    if start_time is None:
        return "00:00:00"
    
    elapsed = datetime.now() - start_time
    return format_time(elapsed.total_seconds())


def format_score(score: float) -> str:
    """
    Format score with color indicator.
    
    Args:
        score: Score value (0-100)
        
    Returns:
        Formatted score string with emoji indicator
    """
    if score >= 70:
        return f"🟢 {score:.1f}"
    elif score >= 40:
        return f"🟡 {score:.1f}"
    else:
        return f"🔴 {score:.1f}"


def format_score_plain(score: float) -> str:
    """
    Format score without emoji.
    
    Args:
        score: Score value (0-100)
        
    Returns:
        Formatted score string
    """
    return f"{score:.1f}%"


def format_progress(current: int, total: int) -> str:
    """
    Format progress as "current/total (percentage)".
    
    Examples:
        (5, 100) -> "5/100 (5.0%)"
        (0, 0) -> "0/0 (0.0%)"
    """
    if total == 0:
        return "0/0 (0.0%)"
    
    percentage = (current / total) * 100
    return f"{current}/{total} ({percentage:.1f}%)"


def format_status_icon(status: str) -> str:
    """
    Get status icon for display.
    
    Args:
        status: Status string
        
    Returns:
        Emoji icon for the status
    """
    status_icons = {
        "idle": "⏸️",
        "loading_model": "📦",
        "generating_code": "💻",
        "running_tests": "🧪",
        "saving_results": "💾",
        "completed": "✅",
        "error": "❌",
    }
    return status_icons.get(status, "❓")


def truncate_text(text: str, max_length: int = 30, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length with suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncating
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def get_difficulty_color(difficulty: str) -> str:
    """
    Get Rich color name for difficulty level.
    
    Args:
        difficulty: "easy", "medium", or "hard"
        
    Returns:
        Rich color name
    """
    colors = {
        "easy": "green",
        "medium": "yellow",
        "hard": "red",
    }
    return colors.get(difficulty.lower(), "white")


def get_score_color(score: float) -> str:
    """
    Get Rich color name based on score.
    
    Args:
        score: Score value (0-100)
        
    Returns:
        Rich color name
    """
    if score >= 70:
        return "green"
    elif score >= 40:
        return "yellow"
    else:
        return "red"
