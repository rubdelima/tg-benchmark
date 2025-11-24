from modules.dataloader import Dataloader
from modules.test_runner import TestRunner
from schemas.tests import TestSuiteBase
from modules.llm import OllamaHandler
from agents import *
from modules.logger import get_logger

logger = get_logger(__name__)
test_runner = TestRunner()

data = Dataloader.load_jsonl("data/dataset.jsonl")
example = data["1873_A"]
test_suite = TestSuiteBase(test_cases=example.private_test_cases)

from agents.orchestrator import Vivi, OrchestratorConfig

config = OrchestratorConfig(
    model="qwen2.5-coder:1.5b",
    max_iter=2,
    max_retry=2,
    dev_verbosity=1,
    judge_level=0,
    use_buffer=False,
    ignore_warnings=True
)

orchestrator = Vivi(config)

code_arch = orchestrator.solve_question_dataset(example)