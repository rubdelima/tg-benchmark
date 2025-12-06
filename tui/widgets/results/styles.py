"""
CSS styles for results table widget.
"""

WIDGET_CSS = """
ResultsTableWidget {
    width: 100%;
    height: 100%;
    border: solid $primary;
}

ResultsTableWidget > Vertical { height: 100%; }
ResultsTableWidget .section-header { background: $surface; text-style: bold; padding: 0 1; height: 1; }
ResultsTableWidget .filters-row { height: 3; padding: 0 1; background: $surface; }
ResultsTableWidget #toggle-models-btn { width: auto; min-width: 14; height: 3; }
ResultsTableWidget #model-selection-container { height: auto; max-height: 10; display: none; padding: 0 1; background: $surface-darken-1; }
ResultsTableWidget #model-selection-container.visible { display: block; }
ResultsTableWidget #model-selection-list { height: auto; max-height: 8; width: 100%; }
ResultsTableWidget .filter-label { width: auto; padding: 0 1; }
ResultsTableWidget #arch-filter { width: 18; }
ResultsTableWidget #sort-filter { width: 18; }
ResultsTableWidget DataTable { height: 1fr; }
"""

# Definição das colunas com chaves para ordenação
COLUMNS = [
    ("Modelo", "model"),
    ("Params", "params"),
    ("Arch", "arch"),
    ("Tks Out", "tokens_out"),
    ("T.Total", "total_time"),
    ("T.Médio", "avg_time"),
    ("Tks/s", "tks_per_sec"),
    ("Fáceis", "easy_pct"),
    ("Médias", "med_pct"),
    ("Difícil", "hard_pct"),
    ("Total", "total_pct"),
    ("Score", "score"),
]

# Opções de ordenação
SORT_OPTIONS = [
    ("Modelo (A-Z)", "model_asc"),
    ("Modelo (Z-A)", "model_desc"),
    ("Score ↑", "score_asc"),
    ("Score ↓", "score_desc"),
    ("Tempo ↑", "time_asc"),
    ("Tempo ↓", "time_desc"),
    ("Tks/s ↑", "tks_asc"),
    ("Tks/s ↓", "tks_desc"),
]
