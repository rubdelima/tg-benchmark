"""
Módulo de gerenciamento de checkpoints para benchmarks.
Agora salva diretamente em results (com escrita atômica).
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from modules.logger import get_logger

logger = get_logger(__name__)


def get_checkpoint_path(model: str, architecture: str, checkpoints_dir: str = "./.checkpoints/") -> Path:
    """DEPRECATED: Retorna caminho do resultado (não mais checkpoint separado)."""
    return get_result_path(model, architecture, "./results/")


def get_result_path(model: str, architecture: str, results_dir: str = "./results/") -> Path:
    """Retorna o caminho do arquivo de resultado."""
    result_dir = Path(results_dir)
    result_dir.mkdir(exist_ok=True)
    safe_model = model.replace(":", "_").replace("/", "_")
    return result_dir / f"{safe_model}_{architecture}.json"


def load_checkpoint(checkpoint_path: Path) -> Optional[Dict[str, Any]]:
    """Carrega resultado existente (funciona como checkpoint)."""
    # Tenta carregar do results primeiro
    if checkpoint_path.exists():
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Erro ao carregar resultados: {e}")
    return None


def save_checkpoint(checkpoint_path: Path, model: str, architecture: str, results: List[Dict]) -> None:
    """Salva diretamente em results com escrita atômica."""
    try:
        data = {
            "model": model,
            "architecture": architecture,
            "results": results,
            "saved_at": datetime.now().isoformat(),
        }
        # Escrita atômica: escreve em .tmp e renomeia
        temp_path = checkpoint_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        temp_path.replace(checkpoint_path)
    except Exception as e:
        logger.warning(f"Erro ao salvar resultados: {e}")


def clear_checkpoint(checkpoint_path: Path) -> None:
    """Não faz nada - results não deve ser removido."""
    pass


def save_results(result_path: Path, data: Dict[str, Any]) -> None:
    """Salva resultados finais com escrita atômica."""
    temp_path = result_path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    temp_path.replace(result_path)
