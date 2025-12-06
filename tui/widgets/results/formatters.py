"""
Formatters for results table cells.
"""
import re
from rich.text import Text
from typing import Tuple, Optional

from ...utils.colors import get_color_for_percentage
from ...utils.formatters import get_score_color


# Cores por família de modelo
MODEL_FAMILY_COLORS = {
    "gemma3": "light_sky_blue1",
    "qwen3-coder": "dark_orchid",
    "qwen3": "medium_orchid",
    "qwen2.5-coder": "orchid",
    "gpt-oss": "light_slate_grey",
}

# Cores por tamanho do modelo (em bilhões de parâmetros)
def get_size_color(size_b: float) -> str:
    """Retorna a cor baseada no tamanho do modelo em bilhões."""
    if size_b <= 3:
        return "red"
    elif size_b <= 10:
        return "yellow"
    elif size_b <= 100:
        return "green"
    else:
        return "deep_sky_blue1"


def parse_model_name(full_name: str) -> Tuple[str, Optional[float]]:
    """
    Separa o nome do modelo e extrai os parâmetros.
    Exemplos:
        'qwen3:1.7b' -> ('qwen3', 1.7)
        'gemma3:12b' -> ('gemma3', 12.0)
        'qwen3-coder:480b-cloud' -> ('qwen3-coder', 480.0)
        'gpt-oss:20b' -> ('gpt-oss', 20.0)
    """
    if ':' not in full_name:
        return full_name, None
    
    parts = full_name.split(':', 1)
    model_name = parts[0]
    params_str = parts[1]
    
    # Extrai o número de parâmetros (pode ser float, int, ou ter texto depois)
    # Padrão: número seguido opcionalmente de 'b' e texto
    match = re.match(r'^(\d+\.?\d*)b?', params_str, re.IGNORECASE)
    if match:
        params = float(match.group(1))
        return model_name, params
    
    return model_name, None


def get_model_family_color(model_name: str) -> str:
    """Retorna a cor da família do modelo."""
    model_lower = model_name.lower()
    
    # Ordem importa: verificar nomes mais específicos primeiro
    for family, color in MODEL_FAMILY_COLORS.items():
        if model_lower.startswith(family):
            return color
    
    return "white"  # Cor padrão


def format_model_name(full_name: str, max_length: int = 18) -> Text:
    """Formata o nome do modelo com cor da família."""
    model_name, _ = parse_model_name(full_name)
    color = get_model_family_color(model_name)
    
    display_name = model_name
    if len(display_name) > max_length:
        display_name = display_name[:max_length - 2] + ".."
    
    return Text(display_name.ljust(max_length), style=color)


def format_params(full_name: str) -> Text:
    """Formata a quantidade de parâmetros com cor baseada no tamanho."""
    _, params = parse_model_name(full_name)
    
    if params is None:
        return Text("-".center(6), style="dim")
    
    color = get_size_color(params)
    
    # Formata o número de parâmetros
    if params >= 100:
        params_str = f"{params:.0f}B"
    elif params >= 10:
        params_str = f"{params:.0f}B"
    else:
        params_str = f"{params:.1f}B"
    
    return Text(params_str.center(6), style=f"{color} bold")


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


def truncate_model_name(name: str, max_length: int = 15) -> Text:
    """
    DEPRECATED: Use format_model_name instead.
    Mantido para compatibilidade, agora retorna Text com cor.
    """
    return format_model_name(name, max_length)
