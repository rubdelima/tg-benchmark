"""
Formatters for history table cells.
"""
from rich.text import Text

from ...utils.colors import get_color_for_percentage, get_difficulty_color, get_time_color, get_tokens_color


def format_difficulty(difficulty: str) -> Text:
    """Formata dificuldade com cor"""
    color = get_difficulty_color(difficulty)
    abbrev = {"easy": "easy", "medium": "med", "hard": "hard", "unknown": "?"}
    return Text(abbrev.get(difficulty, "?"), style=color)


def format_score(score: float) -> Text:
    """Formata score com cor"""
    style = get_color_for_percentage(score)
    if score > 80:
        style = f"{style} bold"
    return Text(f"{score:.0f}%", style=style)


def format_avg(avg: float) -> Text:
    """Formata média com cor"""
    style = get_color_for_percentage(avg)
    if avg > 80:
        style = f"{style} bold"
    return Text(f"{avg:.0f}%", style=style)


def format_time(seconds: float) -> Text:
    """Formata tempo com cor"""
    if seconds < 60:
        time_str = f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        time_str = f"{minutes}m{secs:02d}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        time_str = f"{hours}h{minutes:02d}m"
    
    style = get_time_color(seconds)
    return Text(time_str, style=style)


def format_tokens(tokens: int) -> Text:
    """Formata tokens com cor"""
    if tokens >= 1_000_000:
        token_str = f"{tokens / 1_000_000:.1f}M"
    elif tokens >= 1_000:
        token_str = f"{tokens / 1_000:.1f}K"
    else:
        token_str = str(tokens)
    
    style = get_tokens_color(tokens)
    return Text(token_str, style=style)


def short_name(model: str, arch: str) -> str:
    """Cria nome curto para cabeçalho de coluna"""
    if ":" in model:
        parts = model.split(":")
        model_short = parts[0][:5] + ":" + parts[-1][:3]
    else:
        model_short = model[:8]
    arch_short = "S" if arch == "simple" else "M"
    return f"{model_short}|{arch_short}"
