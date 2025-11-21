from dataclasses import dataclass
from typing import List, Dict, Tuple

from modules.ollama import OllamaHandler, ChatResponse
from modules.agents.generator_code import GeneratorCodeBaseModel, CheckResult

from modules.schemas.task import Task
from modules.schemas.solution import Solution

from .prompts_dev_verbosity import get_verbosity_prompt
from .pompts_join_tasks import join_tasks, system_join_tasks_prompt

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
        messages = [
            {"role": "system", "content": get_verbosity_prompt(self.verbosity)},
            *self._extract_solution_messages(solution)
        ]
        
        for _ in range(self.generation_retry_attempts):
            
            response = self.ollama_handler.generate_response(messages=messages)
            assert isinstance(response, ChatResponse) and isinstance(response.response, str)

            parse_code_result = self.parse_code(response.response, ignore_warnings=self.ignore_warnings)
            
            if parse_code_result.success:
                solution.solution_history.append({"role": "developer","content": parse_code_result.code})
                return solution
            
            messages.extend(self.get_retry_messages(parse_code_result, response))
                
        raise DeveloperGenerationError("Failed to generate valid Python code after multiple attempts.", messages=messages)
    
    def join_subtasks_code(self, main_task:Task, subtasks:List[Task], skeleton:str)->str:
        messages = [
            {"role": "system", "content": system_join_tasks_prompt},
            {"role": "user", "content": join_tasks(main_task, subtasks, skeleton)}
        ]
        
        for _ in range(self.generation_retry_attempts):
            response = self.ollama_handler.generate_response(messages=messages)
            assert isinstance(response, ChatResponse) and isinstance(response.response, str)
            
            parse_code_result = self.parse_code(response.response, ignore_warnings=self.ignore_warnings)
            
            if parse_code_result.success:
                return parse_code_result.code
            
            messages.extend(self.get_retry_messages(parse_code_result, response))
        
        raise DeveloperGenerationError("Failed to join subtasks code into a valid Python code after multiple attempts.", messages=messages)
        
    
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
        
        

