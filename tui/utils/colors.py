"""
Color utilities for TUI display.

This module provides a centralized color scale for consistent
visual feedback across all TUI components.
"""


def get_color_for_percentage(percentage: float) -> str:
    """
    Get Rich color name based on percentage value.
    
    Uses a 5-tier color scale for consistent visual feedback:
    - 0-20%:   Red (critical/poor performance)
    - 21-40%:  Orange (below average)
    - 41-60%:  Yellow (average)
    - 61-80%:  Green (good)
    - 81-100%: Bright Blue (excellent)
    
    Args:
        percentage: Value from 0 to 100
        
    Returns:
        Rich color name string
        
    Example:
        >>> get_color_for_percentage(85)
        'bright_blue'
        >>> get_color_for_percentage(45)
        'yellow'
    """
    if percentage <= 20:
        return "red"
    elif percentage <= 40:
        return "orange1"
    elif percentage <= 60:
        return "yellow"
    elif percentage <= 80:
        return "green"
    else:
        return "bright_blue"


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


def get_time_color(seconds: float) -> str:
    """
    Get color based on time duration (shorter is better).
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Rich color name
    """
    if seconds < 10:
        return "green"
    elif seconds < 60:
        return "yellow"
    else:
        return "red"


def get_tokens_color(tokens: int) -> str:
    """
    Get color based on token count (fewer is generally better).
    
    Args:
        tokens: Token count
        
    Returns:
        Rich color name
    """
    if tokens < 1_000:
        return "green"
    elif tokens < 10_000:
        return "yellow"
    else:
        return "red"
