"""
Data loading and statistics calculation utilities.

Este módulo centraliza a lógica de carregamento de dados e cálculo
de estatísticas, eliminando duplicação entre manager.py e widgets.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Any


class DatasetLoader:
    """
    Carrega e cacheia informações do dataset.
    Singleton para evitar múltiplas leituras do arquivo.
    """
    
    _instance: Optional['DatasetLoader'] = None
    _difficulties: Dict[str, str] = {}
    _loaded: bool = False
    
    def __new__(cls, dataset_path: Optional[Path] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, dataset_path: Optional[Path] = None):
        if dataset_path and not self._loaded:
            self.load(dataset_path)
    
    def load(self, dataset_path: Path) -> None:
        """Carrega dificuldades do arquivo dataset.jsonl"""
        if self._loaded:
            return
            
        self._difficulties = {}
        
        if not dataset_path.exists():
            return
        
        try:
            with open(dataset_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        q_id = data.get("question_id")
                        difficulty = data.get("difficulty", "unknown")
                        if q_id:
                            self._difficulties[q_id] = difficulty
                    except json.JSONDecodeError:
                        continue
            self._loaded = True
        except IOError:
            pass
    
    def get_difficulty(self, question_id: str) -> str:
        """Retorna dificuldade de uma questão"""
        return self._difficulties.get(question_id, "unknown")
    
    @property
    def difficulties(self) -> Dict[str, str]:
        """Retorna dicionário completo de dificuldades"""
        return self._difficulties.copy()
    
    def reload(self, dataset_path: Path) -> None:
        """Força recarregamento do dataset"""
        self._loaded = False
        self._difficulties = {}
        self.load(dataset_path)


def calculate_difficulty_stats(
    results: List[Dict[str, Any]], 
    dataset_loader: Optional[DatasetLoader] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Calcula estatísticas por dificuldade a partir dos resultados.
    
    Args:
        results: Lista de resultados com question_id e success_rate
        dataset_loader: Opcional - loader para buscar dificuldades
        
    Returns:
        Dict com estatísticas para easy, medium, hard e total
    """
    stats = {
        "easy": {"total": 0, "completed": 0, "success_sum": 0.0, "percentage": 0.0, "avg_percentage": 0.0},
        "medium": {"total": 0, "completed": 0, "success_sum": 0.0, "percentage": 0.0, "avg_percentage": 0.0},
        "hard": {"total": 0, "completed": 0, "success_sum": 0.0, "percentage": 0.0, "avg_percentage": 0.0},
        "total": {"total": 0, "completed": 0, "success_sum": 0.0, "percentage": 0.0, "avg_percentage": 0.0},
    }
    
    for result in results:
        question_id = result.get("question_id", "")
        
        # Determina dificuldade
        if dataset_loader:
            difficulty = dataset_loader.get_difficulty(question_id)
        else:
            difficulty = result.get("difficulty", "unknown")
        
        if difficulty not in ["easy", "medium", "hard"]:
            difficulty = "medium"  # Default
        
        success_rate = result.get("success_rate", 0.0)
        if hasattr(result, 'success_rate'):
            success_rate = result.success_rate
        
        stats[difficulty]["total"] += 1
        stats[difficulty]["completed"] += 1
        stats[difficulty]["success_sum"] += success_rate
        stats["total"]["total"] += 1
        stats["total"]["completed"] += 1
        stats["total"]["success_sum"] += success_rate
    
    # Calcula porcentagens
    for diff in ["easy", "medium", "hard", "total"]:
        total = stats[diff]["total"]
        success_sum = stats[diff]["success_sum"]
        stats[diff]["percentage"] = (success_sum / total * 100) if total > 0 else 0.0
        stats[diff]["avg_percentage"] = stats[diff]["percentage"]
        stats[diff]["passed"] = round(success_sum, 2)
    
    return stats


def calculate_weighted_score(difficulty_stats: Dict[str, Dict[str, Any]]) -> float:
    """
    Calcula score ponderado a partir das estatísticas de dificuldade.
    
    Fórmula: (easy% * 1 + medium% * 3 + hard% * 5) / 9
    
    Args:
        difficulty_stats: Estatísticas calculadas por calculate_difficulty_stats
        
    Returns:
        Score ponderado (0-100)
    """
    easy_pct = difficulty_stats.get("easy", {}).get("percentage", 0.0)
    medium_pct = difficulty_stats.get("medium", {}).get("percentage", 0.0)
    hard_pct = difficulty_stats.get("hard", {}).get("percentage", 0.0)
    
    return (easy_pct * 1 + medium_pct * 3 + hard_pct * 5) / 9


def load_results_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Carrega um arquivo JSON de resultados.
    
    Args:
        file_path: Caminho para o arquivo JSON
        
    Returns:
        Dict com dados ou None se falhar
    """
    try:
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return None


def save_json_file(file_path: Path, data: Dict[str, Any]) -> bool:
    """
    Salva dados em arquivo JSON.
    
    Args:
        file_path: Caminho para o arquivo
        data: Dados a salvar
        
    Returns:
        True se sucesso, False se falhar
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except IOError:
        return False
