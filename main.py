import argparse
from modules.logger import get_logger
from modules.llm import OllamaHandler
from modules.dataloader import load_dataloader
from modules.test_runner import TestRunner
import time
from tqdm.auto import tqdm
from agents.developer import Ellian
from agents.orchestrator import Vivi, OrchestratorConfig
from schemas.tests import TestSuiteBase
import json
import traceback

parser = argparse.ArgumentParser(description="TG-Benchmark Main Script")
parser.add_argument('--model', type=str, required=True, help='Model name to load')
parser.add_argument('--architeture', type=str, required=False, help='Model architecture')
args = parser.parse_args()

logger = get_logger(__name__)

if __name__ == "__main__":
    logger.info(f"Loading model: {args.model} with architecture: {args.architeture}")
    handler = OllamaHandler(model_name=args.model, keep_alive=True)
    logger.info(f"Model {args.model} loaded successfully.")
    test_runer = TestRunner()
    dataset = load_dataloader(30, 40, 30)
    agent = Ellian(handler)
    orchestrator_config = OrchestratorConfig(
        model=args.model,
        max_iter=2,
        max_retry=3, 
        dev_verbosity=3,
        judge_level=1,
        use_buffer=True,
        ignore_warnings=True
    )
    multi_agent = Vivi(orchestrator_config)
    current_input_tokens = 0
    current_output_tokens = 0
    
    handler = multi_agent.ollama_handler if args.architeture == "multi-agent" else handler
    json_data = {
        "model": args.model,
        "architecture": args.architeture,
        "results": []
    }
    
    test_start_time = time.time()
    for question in tqdm(dataset, desc="Running Tests"):
        start_code_gen_time = time.time()
        end_code_gen_time = None
        try:
            if args.architeture == "simple":
                code = agent.generate_code_from_question_dataset(question)
            else:
                code = multi_agent.solve_question_dataset(question)
            end_code_gen_time = time.time()
            result = test_runer.run(TestSuiteBase(test_cases=question.private_test_cases), code)
            results_dict = result.model_dump()
            del results_dict["raw_code"]
            del results_dict["errors"]
        except Exception as e:
            logger.error(f"Error generating code for question {question.question_id}: {e}")
            results_dict = {
                "question_id": question.question_id,
                "error": str(e),
                "traceback": traceback.format_exc()	
            }
            
        results_dict.update({
            "question_id": question.question_id,
            "error": None,
            "traceback": None,
            "code_generation_time": (end_code_gen_time if end_code_gen_time else time.time()) - start_code_gen_time,
            "total_input_tokens": handler.total_input_tokens - current_input_tokens,
            "total_output_tokens": handler.total_output_tokens - current_output_tokens,
        })
        current_input_tokens = handler.total_input_tokens
        current_output_tokens = handler.total_output_tokens
        json_data["results"].append(results_dict)
    test_end_time = time.time()
    json_data.update({
        "total_test_time": test_end_time - test_start_time
    })
    
    with open(f"results/{args.model.replace(':', '_')}_{args.architeture}.json", "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=4)
        