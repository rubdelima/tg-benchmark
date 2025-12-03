"""
Utilities for current run widget.
Status formatting, difficulty stats calculation.
"""
from typing import Dict, List, Any

from ..state.models import RunStatus


def get_status_text(status: RunStatus) -> str:
    """Get human-readable status text"""
    status_texts = {
        RunStatus.IDLE: "Aguardando",
        RunStatus.LOADING_MODEL: "Carregando modelo",
        RunStatus.GENERATING_CODE: "Gerando código",
        RunStatus.RUNNING_TESTS: "Executando testes",
        RunStatus.SAVING_RESULTS: "Salvando resultados",
        RunStatus.COMPLETED: "Concluído",
        RunStatus.ERROR: "Erro",
    }
    return status_texts.get(status, "Desconhecido")


def get_status_icon(status: RunStatus) -> str:
    """Get status icon"""
    status_icons = {
        RunStatus.IDLE: "⏸️",
        RunStatus.LOADING_MODEL: "⏳",
        RunStatus.GENERATING_CODE: "💻",
        RunStatus.RUNNING_TESTS: "🧪",
        RunStatus.SAVING_RESULTS: "💾",
        RunStatus.COMPLETED: "✅",
        RunStatus.ERROR: "❌",
    }
    return status_icons.get(status, "❓")


def calculate_difficulty_stats(results: List[Any]) -> Dict[str, Dict]:
    """
    Calculate difficulty statistics from results.
    
    Returns for each difficulty:
    - completed: number of questions executed
    - total_success_rate: sum of success_rates
    - avg_percentage: average success_rate as percentage (0-100)
    """
    stats = {
        "easy": {"completed": 0, "total_success_rate": 0.0, "avg_percentage": 0.0},
        "medium": {"completed": 0, "total_success_rate": 0.0, "avg_percentage": 0.0},
        "hard": {"completed": 0, "total_success_rate": 0.0, "avg_percentage": 0.0},
    }
    
    for result in results:
        diff = result.difficulty if hasattr(result, 'difficulty') else result.get("difficulty", "medium")
        if diff in stats:
            stats[diff]["completed"] += 1
            success_rate = result.success_rate if hasattr(result, 'success_rate') else result.get("success_rate", 0)
            stats[diff]["total_success_rate"] += success_rate
    
    # Calculate average percentage for each difficulty
    for diff in stats:
        if stats[diff]["completed"] > 0:
            stats[diff]["avg_percentage"] = (stats[diff]["total_success_rate"] / stats[diff]["completed"]) * 100
    
    return stats


# CSS styles for current run widget
WIDGET_CSS = """
CurrentRunWidget {
    width: 100%;
    height: auto;
    border: solid $primary;
    padding: 0;
}

CurrentRunWidget > Vertical { height: auto; }
CurrentRunWidget .info-line { height: 1; padding: 0 1; }
CurrentRunWidget .section-header { background: $surface; text-style: bold; padding: 0 1; }
"""
