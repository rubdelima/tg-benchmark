from dataclasses import dataclass
from typing import List, Dict
import time

# Modules
from modules.ollama import OllamaHandler, ChatResponse
from modules.dataloader import QuestionDataset
from modules.logger import get_logger, StatusContext
from agents.generator_code import GeneratorCodeBaseModel, CheckResult

# Schemas
from schemas.task import Task
from schemas.solution import Solution

# Prompts
from .prompts_dev_verbosity import get_verbosity_prompt
from .pompts_join_tasks import join_tasks, system_join_tasks_prompt
from .prompts_direct import system_direct_solve_prompt, user_direct_solve_template, test_cases_template

logger = get_logger(__name__)

class DeveloperGenerationError(Exception):
    def __init__(self, text, *args, messages: list[dict]):
        super().__init__(text, *args)
        self.text = text
        self.messages = messages

@dataclass
class ParseCodeResult:
    parsed : bool
    code: str

@dataclass
class Ellian(GeneratorCodeBaseModel):
    ollama_handler: OllamaHandler
    verbosity: int = 0
    generation_retry_attempts: int = 3
    ignore_warnings: bool = True
    
    def generate_solution_code(self, solution: Solution) -> Solution:
        logger.info("Developer: Starting code generation for solution.")
        messages = [
            {"role": "system", "content": get_verbosity_prompt(self.verbosity)},
            *self._extract_solution_messages(solution)
        ]
        generated_code = self._generation_loop(messages)
        solution.solution_history.append({"role": "developer","content": generated_code})
        return solution
    
    def join_subtasks_code(self, main_task:Task, subtasks:List[Task], skeleton:str)->str:
        logger.info("Developer: Starting to join subtasks code.")
        messages = [
            {"role": "system", "content": system_join_tasks_prompt},
            {"role": "user", "content": join_tasks(main_task, subtasks, skeleton)}
        ]
        return self._generation_loop(messages)
        
    def generate_code_from_question_dataset(self, question_dataset: QuestionDataset)->str:
        logger.info("Developer: Starting code generation from question dataset.")
        test_cases_str = "\n".join(
            test_cases_template.format(index=i+1, input=tc.inputs, output=tc.expected_output)
            for i, tc in enumerate(question_dataset.public_test_cases)
        )
        messages = [
            {"role": "system", "content": system_direct_solve_prompt},
            {"role": "user", "content": user_direct_solve_template.format(
                title=question_dataset.title,
                description=question_dataset.content,
                test_cases=test_cases_str
            )}
        ]
        return self._generation_loop(messages)
    
    def _generation_loop(self, messages: List[Dict]) ->str:
        with StatusContext(f"Generating code for solution (1/{self.generation_retry_attempts})") as status:
            for attempt in range(1, self.generation_retry_attempts + 1):
                
                logger.debug(f"Developer: Generation attempt {attempt} / {self.generation_retry_attempts}")
                status.update(f"Developer: Generating code for solution ({attempt}/{self.generation_retry_attempts})")
                start_time = time.time()
                response = self.ollama_handler.generate_response(messages=messages)
                elapsed_time = time.time() - start_time
                assert isinstance(response, ChatResponse) and isinstance(response.response, str)
                logger.debug(f"Developer: Response generation took {elapsed_time:.2f} seconds. With {response.output_tokens} output tokens.")
                

                status.update("Developer: Parsing generated code")
                parse_code_result = self.parse_code(response.response, ignore_warnings=self.ignore_warnings)
                
                if parse_code_result.success:
                    logger.debug("Developer: Code parsed successfully.")
                    return parse_code_result.code

                logger.warning("Developer: Generated code has issues, preparing to retry.")
                messages.extend(self.get_retry_messages(parse_code_result, response))
                
        raise DeveloperGenerationError("Failed to generate valid Python code after multiple attempts.", messages=messages)
    
    @staticmethod
    def _extract_solution_messages(solution: Solution) -> list[dict]:
        messages = []        
        for history_entry in solution.solution_history:
            messages.append({
                "role" : "assistant" if history_entry['role'] == "developer" else "user",
                "content" : history_entry['content']
            })
        return messages
    
    def get_retry_messages(self, parse_code_result:CheckResult, response: ChatResponse)-> List[Dict]:
        user_content = (
            f"The previous code has the following issues:\n"
            f"Errors:\n{chr(10).join(parse_code_result.errors)}\n"
            f"Warnings:\n{chr(10).join(parse_code_result.warnings) if parse_code_result.warnings else 'None'}\nPlease fix the code accordingly."
        )
        
        return[
            {"role": "assistant", "content": response.response},
            {"role": "user", "content": user_content}
        ]
        
        

