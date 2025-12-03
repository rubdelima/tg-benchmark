# TG-Benchmark TUI - Documentação

## Visão Geral

A TUI (Terminal User Interface) do TG-Benchmark é uma interface de terminal **READ-ONLY** que monitora em tempo real a execução de benchmarks. Ela não executa benchmarks diretamente - apenas observa arquivos de estado escritos pelo `main.py`.

### Arquitetura

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BenchmarkTUI (app.py)                          │
│                    Aplicação principal Textual Framework                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │  StateManager   │  │    Widgets      │  │       Utils                 │  │
│  │  (state/)       │  │   (widgets/)    │  │      (utils/)               │  │
│  │                 │  │                 │  │                             │  │
│  │  - models.py    │  │ - current_run   │  │ - formatters.py             │  │
│  │  - manager.py   │  │ - results_table │  │ - colors.py                 │  │
│  │  - writer.py    │  │ - history_table │  │                             │  │
│  │                 │  │ - progress_bars │  │                             │  │
│  └────────┬────────┘  └────────┬────────┘  └──────────────────────────────┘  │
│           │                    │                                             │
│           │    Callbacks       │                                             │
│           └────────────────────┘                                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Filesystem Events (watchdog)
                                    ▼
                    ┌───────────────────────────────────┐
                    │        Arquivos de Estado          │
                    │  .tui_state/                       │
                    │    ├── run_state.json              │
                    │    └── launcher_state.json         │
                    │  results/*.json                    │
                    └───────────────────────────────────┘
```

## Estrutura de Diretórios

```text
tui/
├── __init__.py          # Exports principais
├── app.py               # Aplicação principal (BenchmarkTUI)
├── state/               # Gerenciamento de estado
│   ├── __init__.py
│   ├── models.py        # Modelos Pydantic para estado
│   ├── manager.py       # StateManager - observa arquivos
│   └── writer.py        # TUIStateWriter - escrito pelo benchmark
├── widgets/             # Componentes visuais
│   ├── __init__.py
│   ├── current_run.py   # Widget de execução atual
│   ├── results_table.py # Tabela de resultados completos
│   ├── history_table.py # Tabela de comparação histórica
│   └── progress_bars.py # Barras de progresso
└── utils/               # Utilitários compartilhados
    ├── __init__.py
    ├── formatters.py    # Formatação de texto/números
    └── colors.py        # Escala de cores centralizada
```

---

## Módulos

### 1. `app.py` - BenchmarkTUI

A aplicação principal que orquestra todos os componentes.

#### Classe `BenchmarkTUI`

```python
class BenchmarkTUI(App):
    """
    TG-Benchmark Terminal User Interface (Read-Only Monitor)
    
    Esta aplicação APENAS monitora o estado do benchmark.
    Ela NÃO executa o benchmark - para isso use: python main.py
    """
```

#### Layout Visual

```
┌───────────────────────────────────────────────────────────────────────┐
│                    🧪 TG-Benchmark TUI                                │
├──────────────────────────────────┬────────────────────────────────────┤
│  📊 Execução Atual               │  📈 Resultados Concluídos          │
│  ─────────────────               │  ────────────────                  │
│  🤖 Modelo: qwen3:8b             │  ┌──────────────────────────────┐  │
│  🏗️  Arquitetura: multi-agent    │  │ Model│Arch│Score│Easy│...   │  │
│  📝 Questão: abc301_a (15/100)   │  ├──────┼────┼─────┼────┼─────┤  │
│  ⏱️  Tempo Total: 02:25:37        │  │ ...  │... │...  │... │...  │  │
│  💾 Tokens: In: 4.2M | Out: 3.4M │  └──────────────────────────────┘  │
│  ✅ Score Atual: 70%              │                                    │
├──────────────────────────────────┴────────────────────────────────────┤
│ 📦 Progresso Total: [████████░░░░░░░] 450/2070 (21.7%)               │
│ 📝 Progresso Atual: [██████████░░░░░] 15/90 (16.7%)                  │
├───────────────────────────────────────────────────────────────────────┤
│ q: Sair | r: Refresh | h: Histórico                                   │
└───────────────────────────────────────────────────────────────────────┘
```

#### Bindings de Teclado

| Tecla | Ação | Descrição |
|-------|------|-----------|
| `q` | `quit` | Sair da aplicação |
| `r` | `refresh` | Recarregar dados dos arquivos |
| `h` | `toggle_history` | Alternar para visão de histórico |

#### Métodos Principais

| Método | Descrição |
|--------|-----------|
| `compose()` | Monta a estrutura visual da aplicação |
| `on_mount()` | Inicializa observadores e carrega dados |
| `_calculate_launcher_progress()` | Calcula progresso baseado em questões (não runs) |
| `_on_launcher_state_change()` | Handler para mudanças no estado do launcher |
| `_on_run_state_change()` | Handler para mudanças no estado da execução |
| `_on_results_change()` | Handler para novos resultados |
| `action_toggle_history()` | Alterna entre visão principal e histórico |

---

### 2. `state/models.py` - Modelos de Estado

Define os modelos Pydantic para comunicação entre processos.

#### Enums

```python
class RunStatus(str, Enum):
    """Status da execução atual"""
    IDLE = "idle"
    LOADING_MODEL = "loading_model"
    GENERATING_CODE = "generating_code"
    RUNNING_TESTS = "running_tests"
    SAVING_RESULTS = "saving_results"
    COMPLETED = "completed"
    ERROR = "error"
```

#### Modelos Principais

| Modelo | Descrição |
|--------|-----------|
| `QuestionResult` | Resultado de uma única questão |
| `QuestionState` | Estado da questão sendo processada |
| `RunState` | Estado completo de uma execução (`main.py`) |
| `GridItem` | Item na grade de execução |
| `LauncherState` | Estado do launcher de testes |
| `Checkpoint` | Checkpoint para recuperação |
| `CompletedRunSummary` | Resumo de uma execução completa |

#### Exemplo: CompletedRunSummary

```python
class CompletedRunSummary(BaseModel):
    """Resumo de uma execução completa para a tabela de resultados"""
    model: str
    architecture: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    score: float = 0.0
    total_questions: int = 0
    total_time: float = 0.0
    tokens_per_second: float = 0.0
    
    # Estatísticas por dificuldade
    easy_percentage: float = 0.0
    medium_percentage: float = 0.0
    hard_percentage: float = 0.0
    
    # Contadores
    easy_total: int = 0
    easy_passed: float = 0.0
    medium_total: int = 0
    medium_passed: float = 0.0
    hard_total: int = 0
    hard_passed: float = 0.0
```

---

### 3. `state/manager.py` - StateManager

Gerencia a observação de arquivos e notifica mudanças via callbacks.

#### Classe `StateManager`

```python
class StateManager:
    """
    Gerencia arquivos de estado e notifica callbacks em mudanças.
    Usa watchdog para monitoramento eficiente (sem polling).
    """
```

#### Arquivos Monitorados

| Arquivo | Descrição |
|---------|-----------|
| `.tui_state/run_state.json` | Estado da execução atual |
| `.tui_state/launcher_state.json` | Estado do launcher |
| `.tui_state/checkpoint.json` | Checkpoint para recuperação |
| `results/*.json` | Resultados de execuções completas |

#### Métodos de Callback

```python
# Registrar callbacks para eventos
manager.on_launcher_state_change(callback)  # LauncherState
manager.on_run_state_change(callback)       # RunState
manager.on_checkpoint_change(callback)      # Checkpoint
manager.on_results_change(callback)         # List[CompletedRunSummary]
```

#### Polling Fallback

Para compatibilidade com Windows (onde watchdog pode falhar), há um sistema de polling:

```python
def poll_for_changes(self) -> None:
    """
    Poll para mudanças de arquivo como fallback para watchdog.
    Chame periodicamente (ex: cada 0.5s).
    """
```

---

### 4. `state/writer.py` - TUIStateWriter

Escrito pelo `benchmark.py` para comunicar estado com a TUI.

#### Uso pelo Benchmark

```python
from tui.state.writer import TUIStateWriter

writer = TUIStateWriter()

# Iniciar uma execução
writer.start_run(model="qwen3:8b", architecture="simple", total_questions=90)

# Iniciar uma questão
writer.start_question(question_id="abc301_a", difficulty="easy", index=1, total=90)

# Atualizar tokens
writer.update_tokens(input_tokens=1500, output_tokens=500)

# Finalizar questão
writer.finish_question(
    passed_tests=5,
    total_tests=5,
    success_rate=1.0,
    total_time=2.5
)

# Finalizar execução
writer.finish_run()
```

---

### 5. `widgets/current_run.py` - CurrentRunWidget

Exibe informações da execução atual em formato compacto.

#### Layout

```
┌─ 📊 Execução Atual ─────────────────────────────────────────────────┐
│ 🤖 Modelo: qwen3:8b 🏗️  Arquitetura: multi-agent ⏱️  Tempo: 02:25:37 │
│ 🟢 Easy: 10/30 (33.3%) 🟡 Medium: 5/30 (16.7%) 🔴 Hard: 2/30 (6.7%) │
│ 📊 Total: 17/90 (18.9%) Score: 15.2%                                │
│ 💾 Tokens: In: 4.2M | Out: 3.4M                                     │
│ 📋 Questão Atual: abc301_a (15/90)                                  │
└─────────────────────────────────────────────────────────────────────┘
```

#### Propriedade Reativa

```python
run_state: reactive[Optional[RunState]] = reactive(None, layout=True)
```

Quando `run_state` muda, o widget automaticamente atualiza a exibição.

---

### 6. `widgets/results_table.py` - ResultsTableWidget

Tabela de resultados de execuções completas com ordenação e filtros.

#### Colunas

| Coluna | Chave | Descrição |
|--------|-------|-----------|
| Model | `model` | Nome do modelo |
| Arch | `arch` | Arquitetura (simple/multi) |
| Tks Out | `tokens_out` | Total de tokens de saída |
| T.Total | `total_time` | Tempo total de execução |
| T.Médio | `avg_time` | Tempo médio por questão |
| Tks/s | `tks_per_sec` | Tokens por segundo |
| Fáceis | `easy_pct` | % acerto em questões fáceis |
| Médias | `med_pct` | % acerto em questões médias |
| Difícil | `hard_pct` | % acerto em questões difíceis |
| Total | `total_pct` | % acerto geral |
| Score | `score` | Score ponderado |

#### Filtros Disponíveis

- **Arquitetura**: Todas, Simple, Multi-Agent
- **Ordenação**: Por modelo, score, tempo, tokens/s
- **Modelos**: Multi-select para filtrar modelos específicos

#### Interação

- Clique no cabeçalho da coluna para ordenar
- Botão "🔍 Modelos" expande lista de seleção de modelos

---

### 7. `widgets/history_table.py` - HistoryTableWidget

Tabela de comparação histórica - mostra questões vs modelos.

#### Layout

```
Questão | Dificuldade | AVG | Model1|S | Model1|M | Model2|S | ...
--------|-------------|-----|---------|----------|----------|----
abc301_a| easy        | 75% |   80%   |   70%    |   85%    | ...
abc301_b| medium      | 45% |   50%   |   40%    |   55%    | ...
```

#### Filtros

- **Pesquisa**: Filtra por ID da questão
- **Dificuldade**: Todas, Fácil, Médio, Difícil
- **Modelos**: Multi-select para escolher modelos
- **Colunas**: Multi-select para métricas (Score, Tempo, Tokens)

#### Navegação

- Pressione `H` para alternar entre visão principal e histórico
- Use setas ↑↓ para navegar entre linhas
- Clique no cabeçalho para ordenar

---

### 8. `widgets/progress_bars.py` - ProgressBarsWidget

Duas barras de progresso: total e atual.

#### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ 📦 Progresso Total:  [████████░░░░░░░░░░] 450/2070 (21.7%)     │
│ 📝 Progresso Atual:  [██████████░░░░░░░] 15/90 (16.7%)         │
└─────────────────────────────────────────────────────────────────┘
```

#### CustomProgressBar

Widget customizado que usa Rich Text para controle total da renderização.

```python
class CustomProgressBar(Static):
    progress: reactive[float] = reactive(0.0)
    label: reactive[str] = reactive("")
    info: reactive[str] = reactive("")
```

#### Cores Dinâmicas

A barra de progresso atual usa cores dinâmicas baseadas na porcentagem.

---

### 9. `utils/formatters.py` - Formatadores

Funções utilitárias para formatação de texto.

| Função | Descrição | Exemplo |
|--------|-----------|---------|
| `format_tokens(n)` | Formata tokens com sufixo K/M/B | `1500000` → `"1.5M"` |
| `format_time(seconds)` | Formata segundos em HH:MM:SS | `3665` → `"01:01:05"` |
| `format_time_elapsed(start)` | Tempo decorrido desde datetime | |
| `format_score(score)` | Score com emoji indicador | `75.0` → `"🟢 75.0"` |
| `format_progress(curr, total)` | Progresso formatado | `(5, 100)` → `"5/100 (5.0%)"` |
| `truncate_text(text, max)` | Trunca texto com "..." | |
| `get_score_color(score)` | Cor Rich para score | |

---

### 10. `utils/colors.py` - Escala de Cores

Sistema centralizado de cores para consistência visual.

#### Escala de Porcentagem (5 níveis)

```python
def get_color_for_percentage(percentage: float) -> str:
    """
    Escala de cores por porcentagem:
    - 0-20%:   red (crítico)
    - 21-40%:  orange1 (abaixo da média)
    - 41-60%:  yellow (médio)
    - 61-80%:  green (bom)
    - 81-100%: bright_blue (excelente)
    """
```

#### Outras Funções de Cor

| Função | Descrição |
|--------|-----------|
| `get_difficulty_color(difficulty)` | Cor por dificuldade (easy=green, medium=yellow, hard=red) |
| `get_time_color(seconds)` | Cor por tempo (menor é melhor) |
| `get_tokens_color(tokens)` | Cor por tokens (menos é melhor) |

---

## Fluxo de Dados

```
┌─────────────────┐       ┌──────────────────┐       ┌─────────────────┐
│   main.py       │       │  TUIStateWriter  │       │   Arquivos      │
│   (benchmark)   │──────▶│   (writer.py)    │──────▶│   JSON          │
└─────────────────┘       └──────────────────┘       └────────┬────────┘
                                                              │
                                                              │ watchdog
                                                              ▼
┌─────────────────┐       ┌──────────────────┐       ┌─────────────────┐
│   BenchmarkTUI  │◀──────│   StateManager   │◀──────│   Filesystem    │
│   (app.py)      │       │   (manager.py)   │       │   Events        │
└────────┬────────┘       └──────────────────┘       └─────────────────┘
         │
         │ callbacks
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                            Widgets                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │ CurrentRun   │  │ ResultsTable │  │ HistoryTable │  │ Progress │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Como Usar

### Executar a TUI

```bash
# Método 1: Como módulo
python -m tui.app

# Método 2: Com config customizado
python -m tui.app --config my_config.yaml

# Método 3: Com diretório base diferente
python -m tui.app --base-path /path/to/project
```

### Executar o Benchmark (separadamente)

```bash
# Em outro terminal
python main.py
```

A TUI irá automaticamente detectar mudanças nos arquivos de estado e atualizar a exibição.

---

## Teclas de Atalho

| Tecla | Contexto | Ação |
|-------|----------|------|
| `q` | Global | Sair da aplicação |
| `r` | Global | Recarregar dados |
| `h` | Global | Alternar visão de histórico |
| `↑` `↓` | Tabelas | Navegar entre linhas |
| Click | Cabeçalho | Ordenar por coluna |

---

## Configuração

A TUI lê configurações do `config.yaml`:

```yaml
paths:
  results: "./results/"
  dataset_file: "./data/dataset.jsonl"

benchmark:
  models:
    qwen3:
      - "8b"
      - "14b"
    gemma3:
      - "9b"
  architectures:
    - "simple"
    - "multi-agent"

dataset:
  easy_samples: 30
  medium_samples: 30
  hard_samples: 30
```

---

## Extensibilidade

### Adicionar Novo Widget

1. Crie arquivo em `tui/widgets/novo_widget.py`
2. Exporte em `tui/widgets/__init__.py`
3. Adicione ao `compose()` em `app.py`

### Adicionar Nova Métrica

1. Adicione campo em `state/models.py`
2. Atualize `state/writer.py` para escrevê-la
3. Atualize widgets para exibi-la

### Adicionar Novo Callback

```python
# Em StateManager
def on_custom_event(self, callback: Callable[[CustomData], None]):
    self._callbacks["custom_event"].append(callback)

# Em BenchmarkTUI
def on_mount(self):
    self.state_manager.on_custom_event(self._handle_custom_event)
```

---

## Dependências

- **Textual**: Framework TUI assíncrono
- **Rich**: Renderização de texto estilizado
- **Pydantic**: Validação de modelos de dados
- **Watchdog**: Observação de mudanças em arquivos
- **PyYAML**: Parsing de configuração

---

## Troubleshooting

### TUI não atualiza

1. Verifique se o benchmark está rodando (`python main.py`)
2. Pressione `r` para forçar refresh
3. Verifique se `.tui_state/` existe

### Watchdog não funciona (Windows)

O sistema usa polling como fallback (0.5s). Se precisar de atualização mais frequente, ajuste o intervalo em `app.py`:

```python
self.set_interval(0.5, self._poll_state_changes)  # Mudar para 0.2
```

### Cores não aparecem corretamente

Verifique se o terminal suporta cores ANSI. No Windows, use Windows Terminal ou PowerShell 7+.
