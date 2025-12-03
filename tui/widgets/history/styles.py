"""
CSS styles for history table widget.
"""

WIDGET_CSS = """
HistoryTableWidget {
    width: 100%;
    height: 100%;
    border: solid $primary;
}

HistoryTableWidget > Vertical { height: 100%; }
HistoryTableWidget .section-header { background: $surface; text-style: bold; padding: 0 1; height: 1; }
HistoryTableWidget .filters-row { height: 3; padding: 0 1; background: $surface; }
HistoryTableWidget #toggle-models-btn { width: auto; min-width: 14; height: 3; }
HistoryTableWidget #toggle-columns-btn { width: auto; min-width: 14; height: 3; }
HistoryTableWidget #model-selection-container { height: auto; max-height: 12; display: none; padding: 0 1; background: $surface-darken-1; }
HistoryTableWidget #model-selection-container.visible { display: block; }
HistoryTableWidget #column-selection-container { height: auto; max-height: 8; display: none; padding: 0 1; background: $surface-darken-1; }
HistoryTableWidget #column-selection-container.visible { display: block; }
HistoryTableWidget #model-selection-list { height: auto; max-height: 10; width: 100%; scrollbar-size: 1 1; }
HistoryTableWidget #column-selection-list { height: auto; max-height: 6; width: 100%; }
HistoryTableWidget #search-input { width: 30; }
HistoryTableWidget #difficulty-filter { width: 15; }
HistoryTableWidget .filter-label { width: auto; padding: 0 1; content-align: center middle; }
HistoryTableWidget DataTable { height: 1fr; }
"""

# Colunas disponíveis para exibição
AVAILABLE_COLUMNS = {
    "score": "Acurácia (%)",
    "time": "Tempo (⏱)",
    "tokens": "Tokens (T)",
}

# Mapeamento de sufixos para tipos de coluna
COLUMN_SUFFIXES = {
    "score": "%",
    "time": "⏱",
    "tokens": "T",
}

# Ordem de dificuldade para ordenação
DIFFICULTY_ORDER = {
    "easy": 0,
    "medium": 1,
    "hard": 2,
    "unknown": 99,
}
