"""
Formatters for results table cells.
"""
from rich.text import Text

from ...utils.colors import get_color_for_percentage
from ...utils.formatters import get_score_color


def format_time(seconds: float) -> str:
    """Formata tempo em formato legível"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m{secs:02d}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h{minutes:02d}m"


def format_tokens(tokens: int) -> str:
    """Formata tokens com sufixo K/M"""
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M"
    elif tokens >= 1_000:
        return f"{tokens / 1_000:.1f}K"
    return str(tokens)


def format_difficulty_stats(passed: float, total: int, percentage: float) -> Text:
    """Formata estatística de dificuldade no formato (XX.X/XX) XXX.X%"""
    if total == 0:
        return Text("-".rjust(18), style="dim")
    
    color = get_color_for_percentage(percentage)
    text = Text()
    text.append(f"({passed:4.1f}/{total:2d}) ", style=color)
    text.append(f"{percentage:5.1f}%", style=f"{color} bold")
    return text


def format_score(score: float) -> Text:
    """Formata score com cor"""
    score_color = get_score_color(score)
    return Text(f"{score:.1f}%".rjust(7), style=f"{score_color} bold")


def truncate_model_name(name: str, max_length: int = 15) -> str:
    """Trunca nome do modelo para exibição"""
    if len(name) <= max_length:
        return name
    return name[:max_length - 3] + "..."
