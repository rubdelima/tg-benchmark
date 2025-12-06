"""
Table builder for history widget.
Handles filtering, sorting, and row building.
"""
from typing import List, Dict, Set
from textual.widgets import DataTable
from rich.text import Text

from .formatters import format_difficulty, format_score, format_avg, format_time, format_tokens, short_name
from .styles import COLUMN_SUFFIXES, DIFFICULTY_ORDER


def filter_data(
    table_data: List[Dict],
    search: str,
    difficulty: str,
) -> List[Dict]:
    """Aplica filtros aos dados da tabela."""
    filtered = []
    for row in table_data:
        # Filtro de busca
        if search and search not in row["question_id"].lower():
            continue
        # Filtro de dificuldade
        if difficulty != "all" and row["difficulty"] != difficulty:
            continue
        filtered.append(row)
    return filtered


def sort_data(
    data: List[Dict],
    sort_column: str,
    sort_reverse: bool,
    display_configs: List[str],
    use_select_sort: bool = False,
) -> List[Dict]:
    """
    Ordena dados pela coluna especificada.
    
    Se use_select_sort=True, sort_column é o valor do Select (ex: 'id_asc', 'difficulty_desc')
    Se use_select_sort=False, sort_column é a key da coluna clicada no header
    """
    if not sort_column:
        return sorted(data, key=lambda x: x["question_id"])
    
    # Ordenação via Select (dropdown)
    if use_select_sort:
        return _sort_by_select(data, sort_column)
    
    # Ordenação via clique no header da tabela
    if sort_column == "question_id":
        return sorted(data, key=lambda x: x["question_id"], reverse=sort_reverse)
    elif sort_column == "difficulty":
        return sorted(
            data,
            key=lambda x: DIFFICULTY_ORDER.get(x["difficulty"], 99),
            reverse=sort_reverse
        )
    elif sort_column == "avg_score":
        return sorted(data, key=lambda x: x["avg_score"], reverse=sort_reverse)
    else:
        # Ordenar por coluna de config específica
        return _sort_by_config_column(data, sort_column, sort_reverse, display_configs)


def _sort_by_select(data: List[Dict], sort_option: str) -> List[Dict]:
    """Ordena dados baseado na opção selecionada no Select."""
    reverse = sort_option.endswith("_desc")
    sort_key = sort_option.replace("_asc", "").replace("_desc", "")
    
    if sort_key == "id":
        return sorted(data, key=lambda x: x["question_id"], reverse=reverse)
    elif sort_key == "difficulty":
        return sorted(
            data,
            key=lambda x: DIFFICULTY_ORDER.get(x["difficulty"], 99),
            reverse=reverse
        )
    elif sort_key == "avg":
        return sorted(data, key=lambda x: x["avg_score"], reverse=reverse)
    
    return data


def _sort_by_config_column(
    data: List[Dict],
    sort_column: str,
    sort_reverse: bool,
    display_configs: List[str],
) -> List[Dict]:
    """Ordena por uma coluna específica de configuração."""
    for config in display_configs:
        if sort_column.startswith(config):
            col_type = sort_column[len(config)+1:]
            return sorted(
                data,
                key=lambda x, c=config, ct=col_type: (
                    (x["config_data"].get(c) or {}).get(ct, -1)
                ),
                reverse=sort_reverse
            )
    return data


def build_table_columns(
    table: DataTable,
    display_configs: List[str],
    selected_columns: Set[str],
) -> None:
    """Adiciona colunas à tabela."""
    table.clear(columns=True)
    
    # Colunas base
    table.add_column("Questão", key="question_id")
    table.add_column("Dif", key="difficulty")
    table.add_column("AVG", key="avg_score")
    
    # Colunas para cada config e métrica
    for config in display_configs:
        model, arch = config.split("|")
        col_name = short_name(model, arch)
        for col_type in selected_columns:
            suffix = COLUMN_SUFFIXES.get(col_type, "")
            table.add_column(f"{col_name}{suffix}", key=f"{config}_{col_type}")


def add_table_row(
    table: DataTable,
    row_data: Dict,
    display_configs: List[str],
    selected_columns: Set[str],
) -> None:
    """Adiciona uma linha formatada à tabela."""
    row = [
        row_data["question_id"],
        format_difficulty(row_data["difficulty"]),
        format_avg(row_data["avg_score"]),
    ]
    
    for config in display_configs:
        data = row_data["config_data"].get(config)
        if data:
            if "score" in selected_columns:
                row.append(format_score(data["score"]))
            if "time" in selected_columns:
                row.append(format_time(data["time"]))
            if "tokens" in selected_columns:
                row.append(format_tokens(data["tokens"]))
        else:
            for _ in selected_columns:
                row.append(Text("-", style="dim"))
    
    table.add_row(*row)
