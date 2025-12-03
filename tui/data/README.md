# TUI Data Module

Módulo responsável pelo carregamento de dados e cálculo de estatísticas.

## Componentes

### `loader.py`

#### `DatasetLoader` (Singleton)
Carrega e cacheia informações do dataset.jsonl para evitar múltiplas leituras.

```python
from tui.data import DatasetLoader

# Inicializa e carrega
loader = DatasetLoader(Path("./data/dataset.jsonl"))

# Obtém dificuldade de uma questão
difficulty = loader.get_difficulty("abc301_a")  # "easy", "medium", "hard"

# Obtém todas as dificuldades
all_difficulties = loader.difficulties  # Dict[str, str]
```

#### `calculate_difficulty_stats()`
Calcula estatísticas por dificuldade (easy/medium/hard/total).

```python
from tui.data import calculate_difficulty_stats

stats = calculate_difficulty_stats(results, dataset_loader)
# stats = {
#   "easy": {"total": 30, "completed": 30, "success_sum": 25.5, "percentage": 85.0, "passed": 25.5},
#   "medium": {...},
#   "hard": {...},
#   "total": {...}
# }
```

#### `calculate_weighted_score()`
Calcula score ponderado: `(easy% * 1 + medium% * 3 + hard% * 5) / 9`

```python
from tui.data import calculate_weighted_score

score = calculate_weighted_score(difficulty_stats)  # 0-100
```

#### `load_results_file()` / `save_json_file()`
Funções utilitárias para I/O de arquivos JSON.

## Por que este módulo existe?

Centraliza lógica que estava duplicada em:
- `state/manager.py` - carregamento de dataset e cálculo de stats
- `widgets/history_table.py` - carregamento de dataset
- `widgets/current_run.py` - cálculo de estatísticas

Agora todos usam as mesmas funções deste módulo.
