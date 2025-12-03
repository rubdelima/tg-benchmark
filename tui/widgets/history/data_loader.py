"""
Data loading utilities for history table.
"""
import json
from pathlib import Path
from typing import Dict, List, Set, Any

from ...data import DatasetLoader


class HistoryDataLoader:
    """
    Carrega e processa dados para a tabela de histórico.
    """
    
    def __init__(self, results_dir: Path, dataset_path: Path):
        self.results_dir = results_dir
        self.dataset_path = dataset_path
        self._dataset_loader = DatasetLoader(dataset_path)
        
        self.all_results: Dict[str, Dict] = {}  # {model_arch: {question_id: result}}
        self.questions: Dict[str, Dict] = {}  # {question_id: {difficulty, ...}}
        self.configs: List[str] = []  # List of model|arch configs
    
    def load_dataset_difficulties(self) -> Dict[str, str]:
        """Carrega dificuldades do dataset"""
        self._dataset_loader.reload(self.dataset_path)
        return self._dataset_loader.difficulties
    
    def load_all_results(self) -> None:
        """Carrega todos os resultados do diretório"""
        self.all_results = {}
        self.questions = {}
        self.configs = []
        
        if not self.results_dir.exists():
            return
        
        for result_file in self.results_dir.glob("*.json"):
            self._load_result_file(result_file)
        
        # Ordena configs alfabeticamente
        self.configs.sort()
    
    def _load_result_file(self, result_file: Path) -> None:
        """Carrega um arquivo de resultado"""
        try:
            with open(result_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            model = data.get("model", "unknown")
            arch = data.get("architecture", "unknown")
            key = f"{model}|{arch}"
            
            if key not in self.configs:
                self.configs.append(key)
            
            self.all_results[key] = {}
            
            for result in data.get("results", []):
                q_id = result.get("question_id")
                if q_id:
                    self.all_results[key][q_id] = result
                    
                    # Armazena metadata da questão
                    if q_id not in self.questions:
                        difficulty = self._dataset_loader.get_difficulty(q_id)
                        if difficulty == "unknown":
                            difficulty = result.get("difficulty", "unknown")
                        self.questions[q_id] = {"difficulty": difficulty}
        except Exception:
            pass
    
    def build_table_data(self) -> List[Dict[str, Any]]:
        """Constrói dados da tabela para ordenação/filtragem"""
        table_data = []
        
        for q_id, q_info in self.questions.items():
            scores = []
            config_data = {}
            
            for config in self.configs:
                result = self.all_results.get(config, {}).get(q_id)
                if result:
                    score = result.get("success_rate", 0) * 100
                    time_taken = result.get("total_time", 0)
                    tokens_in = result.get("total_input_tokens", 0) or 0
                    tokens_out = result.get("total_output_tokens", 0) or 0
                    
                    scores.append(score)
                    config_data[config] = {
                        "score": score,
                        "time": time_taken,
                        "tokens": tokens_in + tokens_out,
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                    }
                else:
                    config_data[config] = None
            
            avg_score = sum(scores) / len(scores) if scores else 0
            
            table_data.append({
                "question_id": q_id,
                "difficulty": q_info["difficulty"],
                "avg_score": avg_score,
                "config_data": config_data,
            })
        
        return table_data
