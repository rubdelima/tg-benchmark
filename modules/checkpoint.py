"""
Módulo de gerenciamento de checkpoints para benchmarks.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from modules.logger import get_logger

logger = get_logger(__name__)


def get_checkpoint_path(model: str, architecture: str, checkpoints_dir: str = "./.checkpoints/") -> Path:
    """Retorna o caminho do arquivo de checkpoint."""
    checkpoint_dir = Path(checkpoints_dir)
    checkpoint_dir.mkdir(exist_ok=True)
    safe_model = model.replace(":", "_").replace("/", "_")
    return checkpoint_dir / f"checkpoint_{safe_model}_{architecture}.json"


def get_result_path(model: str, architecture: str, results_dir: str = "./results/") -> Path:
    """Retorna o caminho do arquivo de resultado."""
    result_dir = Path(results_dir)
    result_dir.mkdir(exist_ok=True)
    safe_model = model.replace(":", "_").replace("/", "_")
    return result_dir / f"{safe_model}_{architecture}.json"


def load_checkpoint(checkpoint_path: Path) -> Optional[Dict[str, Any]]:
    """Carrega checkpoint se existir."""
    if checkpoint_path.exists():
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Erro ao carregar checkpoint: {e}")
    return None


def save_checkpoint(checkpoint_path: Path, model: str, architecture: str, results: List[Dict]) -> None:
    """Salva checkpoint."""
    try:
        data = {
            "model": model,
            "architecture": architecture,
            "results": results,
            "saved_at": datetime.now().isoformat(),
        }
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger.warning(f"Erro ao salvar checkpoint: {e}")


def clear_checkpoint(checkpoint_path: Path) -> None:
    """Remove arquivo de checkpoint."""
    if checkpoint_path.exists():
        checkpoint_path.unlink()


def save_results(result_path: Path, data: Dict[str, Any]) -> None:
    """Salva resultados finais."""
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
