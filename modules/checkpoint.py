"""
Módulo de gerenciamento de checkpoints para benchmarks.
Agora salva diretamente em results (com escrita atômica).
"""
import json
import os
import time
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


def _atomic_write(file_path: Path, data: Dict[str, Any], indent: int = 2) -> None:
    """
    Escrita atômica com retry para Windows.
    Tenta renomear o arquivo .tmp para o destino final com retries.
    Em caso de falha persistente, cria backup numerado (.json.bck1, .json.bck2, etc.)
    """
    temp_path = file_path.with_suffix(".tmp")
    max_retries = 3
    
    # Escreve no arquivo temporário
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, default=str)
    
    # Tenta renomear com retry
    for attempt in range(max_retries):
        try:
            # No Windows, precisamos remover o destino antes de renomear
            if file_path.exists():
                os.remove(file_path)
            os.rename(temp_path, file_path)
            return
        except (PermissionError, OSError) as e:
            if attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))  # Delay progressivo
            else:
                # Falha persistente: cria backup do arquivo existente e tenta escrita direta
                try:
                    # Se o arquivo original existe, cria backup numerado
                    if file_path.exists():
                        bck_num = 1
                        while True:
                            bck_path = file_path.with_suffix(f".json.bck{bck_num}")
                            if not bck_path.exists():
                                break
                            bck_num += 1
                        try:
                            os.rename(file_path, bck_path)
                            logger.warning(f"Backup criado: {bck_path}")
                        except:
                            pass  # Se não conseguir criar backup, tenta escrever mesmo assim
                    
                    # Tenta escrita direta
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=indent, default=str)
                    
                    # Remove temp se conseguiu escrever diretamente
                    if temp_path.exists():
                        try:
                            os.remove(temp_path)
                        except:
                            pass
                    return
                except Exception as fallback_error:
                    raise e  # Re-raise o erro original


def save_checkpoint(checkpoint_path: Path, model: str, architecture: str, results: List[Dict]) -> None:
    """Salva diretamente em results com escrita atômica."""
    try:
        data = {
            "model": model,
            "architecture": architecture,
            "results": results,
            "saved_at": datetime.now().isoformat(),
        }
        _atomic_write(checkpoint_path, data, indent=2)
    except Exception as e:
        logger.warning(f"Erro ao salvar resultados: {e}")


def clear_checkpoint(checkpoint_path: Path) -> None:
    """Não faz nada - results não deve ser removido."""
    pass


def save_results(result_path: Path, data: Dict[str, Any]) -> None:
    """Salva resultados finais com escrita atômica."""
    _atomic_write(result_path, data, indent=4)
