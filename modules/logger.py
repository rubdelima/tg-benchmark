import logging
import datetime
import yaml
import sys
import os
from pathlib import Path
from rich.console import Console
from rich.logging import RichHandler
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from textual.widgets import RichLog, Label, LoadingIndicator
from textual.containers import Vertical, Horizontal
import time

# --- 1. Carregamento de Configuração ---
def _load_config():
    default_config = {"level": "INFO", "logs_path": "./logs/"}
    try:
        with open("config.yaml", "r") as f:
            data = yaml.safe_load(f)
            return data.get("logging", default_config)
    except FileNotFoundError:
        return default_config

_config = _load_config()
_LOG_LEVEL = _config.get("level", "INFO").upper()
_LOG_PATH = Path(_config.get("logs_path", "./logs/"))

# --- 2. Configuração do Root Logger (Arquivo + Filtros) ---
# Executa IMEDIATAMENTE ao importar o módulo

_LOG_PATH.mkdir(parents=True, exist_ok=True)
_filename = f"run_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"

_root_logger = logging.getLogger()
_root_logger.setLevel(logging.DEBUG) # Raiz aceita tudo

# 2.1 Filtro de Bibliotecas Barulhentas
_NOISY_LIBS = ["httpcore", "httpx", "urllib3", "asyncio", "matplotlib", "multipart"]
for lib_name in _NOISY_LIBS:
    logging.getLogger(lib_name).setLevel(logging.WARNING)

# 2.2 File Handler (Log em Arquivo)
_file_handler = logging.FileHandler(_LOG_PATH / _filename, encoding='utf-8')
_file_handler.setLevel(logging.DEBUG) # Arquivo sempre grava DEBUG
_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
_root_logger.addHandler(_file_handler)


# --- 3. Detecção Automática de Ambiente e Console ---

def _is_jupyter():
    try:
        shell = get_ipython().__class__.__name__
        if shell == 'ZMQInteractiveShell':
            return True   # Jupyter notebook or qtconsole
        elif shell == 'TerminalInteractiveShell':
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False      # Probably standard Python interpreter

_console = None

if _is_jupyter():
    # Modo Notebook
    _console = Console(force_jupyter=True)
else:
    # Modo Terminal Padrão
    _console = Console(force_terminal=True)

# --- 4. Configuração Automática do Handler Visual (CLI/Notebook) ---

# Remove handlers Rich antigos (caso de reload)
_existing_handlers = [h for h in _root_logger.handlers if isinstance(h, RichHandler)]
for h in _existing_handlers:
    _root_logger.removeHandler(h)

# Adiciona o Handler Padrão (CLI/Notebook)
# Ele será removido automaticamente se entrarmos no modo TUI
_default_rich_handler = RichHandler(
    console=_console, 
    rich_tracebacks=True, 
    markup=True,
    show_time=False, 
    show_path=False
)
_default_rich_handler.setLevel(_LOG_LEVEL)
_root_logger.addHandler(_default_rich_handler)


# --- 5. Globais de Hooks (Para TUI) ---
_ui_hooks = {"start": None, "update": None, "stop": None}


# --- 6. Funções Públicas ---

def get_logger(name=None):
    return logging.getLogger(name)

def get_logger_widget():
    """
    Chamado pelo Textual.
    AUTOMATICAMENTE desativa o log de terminal e ativa o log de Widget.
    """
    # Remove o handler de CLI padrão para não sujar o terminal de fundo
    if _default_rich_handler in _root_logger.handlers:
        _root_logger.removeHandler(_default_rich_handler)
    
    # Recria console para modo não-terminal (evita conflito com TUI)
    global _console
    _console = Console(force_terminal=False)
    
    return LogConsole()


# --- 7. Classes de Suporte ---

class _TextualHandler(logging.Handler):
    def __init__(self, rich_log_widget):
        super().__init__()
        self.widget = rich_log_widget

    def emit(self, record):
        log_time = datetime.datetime.fromtimestamp(record.created).strftime("[%X]")
        level_color = "green"
        if record.levelno == logging.DEBUG: level_color = "magenta"
        elif record.levelno == logging.WARNING: level_color = "yellow"
        elif record.levelno == logging.ERROR: level_color = "red"
        msg = (f"[dim]{log_time}[/dim] [bold {level_color}]{record.levelname:<8}[/bold {level_color}] {record.getMessage()}")
        self.widget.app.call_from_thread(self.widget.write, Text.from_markup(msg))

class LogConsole(Vertical):
    DEFAULT_CSS = """
    LogConsole { height: 100%; width: 100%; background: $surface; border: solid $primary; }
    LogConsole RichLog { height: 1fr; background: $surface; border: none; }
    LogConsole #status_bar { height: auto; border-top: solid $secondary; background: $surface-lighten-1; padding: 0 1; display: none; }
    LogConsole LoadingIndicator { height: 1; width: auto; color: yellow; margin-right: 1; }
    LogConsole Label { color: $text; }
    """
    def compose(self):
        yield RichLog(id="rlog", markup=True)
        with Horizontal(id="status_bar"):
            yield LoadingIndicator()
            yield Label("", id="status_lbl")

    def on_mount(self):
        rlog = self.query_one("#rlog", RichLog)
        tui_h = _TextualHandler(rlog)
        tui_h.setLevel(_LOG_LEVEL)
        logging.getLogger().addHandler(tui_h)
        _ui_hooks["start"], _ui_hooks["update"], _ui_hooks["stop"] = self._action_start, self._action_update, self._action_stop

    def _action_start(self, msg):
        self.app.call_from_thread(lambda: (setattr(self.query_one("#status_bar").styles, "display", "block"), self.query_one("#status_lbl", Label).update(msg)))
    def _action_update(self, msg):
        self.app.call_from_thread(lambda: self.query_one("#status_lbl", Label).update(msg))
    def _action_stop(self):
        self.app.call_from_thread(lambda: setattr(self.query_one("#status_bar").styles, "display", "none"))


# --- 8. StatusContext (Com Timer Real-Time) ---

class StatusContext:
    def __init__(self, msg, spinner_name="dots"):
        self.msg = msg
        self.spinner_name = spinner_name
        self.start_time = None
        self.progress = None
        self.task_id = None

    def _get_msg_with_time_manual(self, msg):
        """Para Logs e TUI que precisam formatar o tempo manualmente."""
        if self.start_time is None: return f"[00:00] {msg}"
        elapsed = time.time() - self.start_time
        return f"[{int(elapsed // 60):02d}:{int(elapsed % 60):02d}] {msg}"

    def __enter__(self):
        self.start_time = time.time()
        
        # CASO 1: TUI (Textual)
        if _ui_hooks["start"]:
            _ui_hooks["start"](self._get_msg_with_time_manual(self.msg))
        
        # CASO 2: CLI ou Jupyter (Usa Progress para Real-Time)
        elif _console.is_terminal or _console.is_jupyter:
            self.progress = Progress(
                SpinnerColumn(self.spinner_name),
                TimeElapsedColumn(), # <--- Conta o tempo SOZINHO (Real-Time)
                TextColumn("{task.description}"),
                console=_console,
                transient=True # Some ao terminar
            )
            self.task_id = self.progress.add_task(self.msg, total=None)
            self.progress.start()
        
        # CASO 3: Apenas Arquivo
        else:
            logging.getLogger().info(f"⏳ [START] {self._get_msg_with_time_manual(self.msg)}")
            
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if _ui_hooks["stop"]:
            _ui_hooks["stop"]()
        elif self.progress:
            self.progress.stop()
        
        logging.getLogger().info(f"✅ [END] {self._get_msg_with_time_manual(self.msg)}")

    def update(self, new_msg):
        self.msg = new_msg
        
        if _ui_hooks["update"]:
            _ui_hooks["update"](self._get_msg_with_time_manual(new_msg))
        elif self.progress:
            # Apenas atualiza o texto, o tempo continua correndo sozinho
            self.progress.update(self.task_id, description=new_msg)
        else:
            logging.getLogger().info(f"ℹ️ [STATUS] {self._get_msg_with_time_manual(new_msg)}")