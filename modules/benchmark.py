"""
Módulo principal de execução de benchmarks.
"""
import json
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from tqdm.auto import tqdm

from modules.logger import get_logger
from modules.llm import OllamaHandler
from modules.dataloader import load_dataloader
from modules.test_runner import TestRunner
from modules.checkpoint import (
    get_checkpoint_path, get_result_path,
    load_checkpoint, save_checkpoint, clear_checkpoint, save_results
)
from tui.state import get_tui_writer
from agents.developer import Ellian
from agents.master import Davi
from schemas.tests import TestSuiteBase

logger = get_logger(__name__)
tui = get_tui_writer()


def sanitize_model_name(model: str) -> str:
    """Converte nome do modelo para nome de pasta válido."""
    return re.sub(r'[<>:"/\\|?*]', '_', model).replace(':', '_')


def save_history_file(results_dir: str, model: str, question_id: str, history: Any) -> Optional[str]:
    """
    Salva histórico em arquivo separado.
    Retorna o caminho relativo do arquivo ou None se não houver histórico.
    """
    if history is None:
        return None
    
    model_folder = sanitize_model_name(model)
    history_dir = Path(results_dir) / model_folder
    history_dir.mkdir(parents=True, exist_ok=True)
    
    history_file = history_dir / f"{question_id}.json"
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    
    # Retorna caminho relativo à pasta results
    return f"{model_folder}/{question_id}.json"


def calculate_metrics(results: List[Dict]) -> Dict[str, Any]:
    """Calcula métricas finais dos resultados."""
    weights = {"easy": 1, "medium": 3, "hard": 5}
    
    # Score ponderado
    total_weighted = sum(r["success_rate"] * weights.get(r["difficulty"], 1) for r in results)
    total_weight = sum(weights.get(r["difficulty"], 1) for r in results)
    score = (total_weighted / total_weight * 100) if total_weight > 0 else 0.0
    
    # Stats por dificuldade
    difficulty_stats = {}
    for diff in ["easy", "medium", "hard"]:
        diff_results = [r for r in results if r["difficulty"] == diff]
        if diff_results:
            passed = sum(1 for r in diff_results if r["success_rate"] == 1.0)
            difficulty_stats[diff] = {
                "total": len(diff_results),
                "passed": passed,
                "percentage": (passed / len(diff_results)) * 100,
            }
    
    return {"score": score, "difficulty_stats": difficulty_stats}


def run_single_benchmark(
    model: str,
    architecture: str,
    config: Dict[str, Any],
    resume: bool = True,
) -> Dict[str, Any]:
    """Executa benchmark para uma combinação modelo/arquitetura."""
    paths = config.get("paths", {})
    results_dir = paths.get("results", "./results/")
    # Agora salva direto em results (não mais em .checkpoints)
    result_path = get_result_path(model, architecture, results_dir)
    
    # Dataset config
    ds_cfg = config.get("dataset", {})
    easy, medium, hard = ds_cfg.get("easy_samples", 30), ds_cfg.get("medium_samples", 30), ds_cfg.get("hard_samples", 30)
    
    # Carrega resultados anteriores (funciona como checkpoint)
    start_index, results = 0, []
    acc_in_tokens, acc_out_tokens = 0, 0
    
    if resume:
        checkpoint = load_checkpoint(result_path)
        if checkpoint:
            results = checkpoint.get("results", [])
            start_index = len(results)
            acc_in_tokens = sum(r.get("total_input_tokens", 0) for r in results)
            acc_out_tokens = sum(r.get("total_output_tokens", 0) for r in results)
            logger.info(f"📂 Retomando: {start_index} questões concluídas")
    
    # Dataset
    logger.info("🔄 Carregando dataset...")
    dataset = load_dataloader(easy, medium, hard)
    total = len(dataset)
    logger.info(f"📊 Dataset: {total} questões")
    
    # Iniciar estado TUI (passa resultados do checkpoint para mostrar progresso correto)
    tui.start_run(model, architecture, total, resumed_results=results if results else None)
    
    # Modelo
    logger.info(f"🔄 Carregando {model}...")
    gen_cfg = config.get("generation_config", {})
    handler = OllamaHandler(
        model_name=model, 
        temperature=gen_cfg.get("temperature", 0.0),
        max_tokens=gen_cfg.get("max_tokens_response", 16384),
        repeat_penalty=gen_cfg.get("repeat_penalty", 1.3),
        repeat_last_n=gen_cfg.get("repeat_last_n", 512),
        keep_alive=config.get("agent", {}).get("keep_alive", True)
    )
    logger.info("✓ Modelo carregado!")
    tui.model_loaded()
    
    # Agente
    multi_agent, agent = None, None
    if architecture == "simple":
        agent = Ellian(handler)
        active_handler = handler
    else:
        mc = config.get("multi_agent", {})
        multi_agent = Davi(
            handler=handler,
            max_retries=mc.get("max_retries", 3),
        )
        active_handler = handler
    
    test_runner = TestRunner()
    start_time = time.time()
    cur_in, cur_out = active_handler.total_input_tokens, active_handler.total_output_tokens
    
    # IDs já processados (do checkpoint)
    processed_ids = {r.get("question_id") for r in results}
    
    try:
        # Loop de questões (sob demanda, sem carregar tudo em memória)
        q_idx = start_index
        pending_count = total - start_index
        
        if pending_count <= 0:
            logger.info("✅ Todas as questões já foram processadas!")
            tui.finish_run(success=True)
            metrics = calculate_metrics(results)
            total_time = sum(r.get("total_time", 0.0) for r in results)
            return {
                "model": model, "architecture": architecture,
                "total_questions": total, "score": metrics["score"],
                "difficulty_stats": metrics["difficulty_stats"],
                "total_time": total_time, "total_test_time": total_time,
                "total_input_tokens": acc_in_tokens, "total_output_tokens": acc_out_tokens,
                "results": results,
            }
        
        logger.info(f"📋 Pendentes: {pending_count} questões")
        
        with tqdm(total=pending_count, desc=f"[{model}]") as pbar:
            for full_q in dataset:
                # Pular questões já processadas
                if full_q.question_id in processed_ids:
                    continue
                
                q_idx += 1
                logger.info(f"📝 [{q_idx}/{total}] {full_q.question_id} ({full_q.difficulty})")
                
                # Atualizar estado TUI - início da questão
                tui.start_question(full_q.question_id, full_q.difficulty, q_idx, total)
                
                q_start = time.time()
                try:
                    if agent:
                        code = agent.generate_code_from_question_dataset(full_q)
                        history = None
                    else:
                        code, history = multi_agent.solve_question_dataset(full_q)
                    code_time = time.time() - q_start
                    
                    q_in = active_handler.total_input_tokens - cur_in
                    q_out = active_handler.total_output_tokens - cur_out
                    
                    # Atualizar tokens na TUI
                    tui.update_question_tokens(q_in, q_out)
                    
                    # Executar testes
                    tui.start_tests(len(full_q.private_test_cases))
                    test_result = test_runner.run(TestSuiteBase(test_cases=full_q.private_test_cases), code)
                    
                    # Salvar histórico em arquivo separado (se existir)
                    history_file = save_history_file(results_dir, model, full_q.question_id, history)
                    
                    result = {
                        "question_id": full_q.question_id, "difficulty": full_q.difficulty,
                        "total_time": time.time() - q_start, "code_generation_time": code_time,
                        "passed_tests": test_result.passed_tests, "total_tests": test_result.total_tests,
                        "success_rate": test_result.success_rate,
                        "total_input_tokens": q_in, "total_output_tokens": q_out,
                        "error": None, "traceback": None,
                        "code": code,
                        "history_file": history_file,  # Referência ao arquivo, não o histórico completo
                    }
                except Exception as e:
                    logger.error(f"Erro em {full_q.question_id}: {e}")
                    q_in = active_handler.total_input_tokens - cur_in
                    q_out = active_handler.total_output_tokens - cur_out
                    result = {
                        "question_id": full_q.question_id, "difficulty": full_q.difficulty,
                        "total_time": time.time() - q_start, "code_generation_time": 0.0,
                        "passed_tests": 0, "total_tests": 0, "success_rate": 0.0,
                        "total_input_tokens": q_in, "total_output_tokens": q_out,
                        "error": str(e), "traceback": traceback.format_exc(),
                    }
                
                cur_in, cur_out = active_handler.total_input_tokens, active_handler.total_output_tokens
                acc_in_tokens += result["total_input_tokens"]
                acc_out_tokens += result["total_output_tokens"]
                results.append(result)
                
                # Atualizar estado TUI - fim da questão
                tui.finish_question(result)
                
                icon = "✅" if result["success_rate"] == 1.0 else ("⚠️" if result["success_rate"] > 0 else "❌")
                logger.info(f"  {icon} {result['success_rate']*100:.0f}% ({result['passed_tests']}/{result['total_tests']})")
                
                # Salva direto em results (atômico)
                save_checkpoint(result_path, model, architecture, results)
                
                # Atualiza barra de progresso
                pbar.update(1)
        
        # Finalizar
        tui.finish_run(success=True)
        
        # Calcula tempo total baseado na soma dos tempos individuais (mais preciso com checkpoint)
        total_time = sum(r.get("total_time", 0.0) for r in results)
        metrics = calculate_metrics(results)
        
        final = {
            "model": model, "architecture": architecture,
            "total_test_time": total_time,  # Agora é a soma dos tempos individuais
            "total_input_tokens": acc_in_tokens, "total_output_tokens": acc_out_tokens,
            "score": metrics["score"],
            "tokens_per_second": acc_out_tokens / total_time if total_time > 0 else 0,
            "difficulty_stats": metrics["difficulty_stats"],
            "completed_at": datetime.now().isoformat(),
            "results": results,
        }
        
        logger.info("💾 Salvando resultados...")
        save_results(result_path, final)
        logger.info("🎉 Benchmark concluído!")
        
        return final
    
    finally:
        # SEMPRE fechar o handler para liberar o modelo
        logger.info("🔒 Fechando handler do modelo...")
        handler.close()
