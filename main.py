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

ollama_handler = OllamaHandler(model_name="phi4-mini-reasoning:3.8b")
dev = Ellian(ollama_handler)
qa = Carlos(ollama_handler)
reseacher = Thifany(ollama_handler)
judge = Will(ollama_handler)

code = dev.generate_code_from_question_dataset(example)
results = test_runner.run(test_suite, code)

logger.info("Test Results:")
print("\nTest Results:")
print(f"Total Time: {results.total_time}")
print(f"Accuracy: {results.success_rate:2.1%} ({results.passed_tests}/{results.total_tests})")
if results.errors:
    print("Errors:")
    for error in results.errors:
        print("Expected:\n", error.expected_output)
        print("Got:\n", error.actual_output)
        print("Error Message:\n", error.error_message)
        print("-----")