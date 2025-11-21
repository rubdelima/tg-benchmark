from dataclasses import dataclass
import re
from typing import Tuple

from pydantic import BaseModel

from modules.ollama import OllamaHandler, ChatResponse
from modules.schemas.solution import Solution, BaseSolution
from modules.schemas.tests import TestSuite, TestsResult

from .prompts import (
    judge_code_system_prompt, evaluate_solution_system_prompt,
    extract_feedback_system_prompt, error_analysis_system_prompt,
    analyze_test_failures_user_template, extract_solution_system_prompt
)

feedback_pattern = r"<feedback>\s*(.*?)\s*</feedback>"
is_correct_pattern = r"<is_correct>\s*(.*?)\s*</is_correct>"
propose_solution_pattern = r"<propose_solution>\s*(.*?)\s*</propose_solution>"
context_pattern = r"<context>\s*(.*?)\s*</context>"

class Judgment(BaseModel):
    is_correct: bool
    feedback: str

@dataclass
class Will:
    ollama_handler: OllamaHandler
    
    def parse_judgment_response(self, response_text: str) -> Judgment:
        
        feedback_match = re.search(feedback_pattern, response_text, re.DOTALL | re.IGNORECASE)
        is_correct_match = re.search(is_correct_pattern, response_text, re.DOTALL | re.IGNORECASE)
        
        if feedback_match and is_correct_match:
            feedback = feedback_match.group(1).strip()
            is_correct_str = is_correct_match.group(1).strip().lower()
            is_correct = is_correct_str in ["true", "correct", "pass"]
            return Judgment(is_correct=is_correct, feedback=feedback)
        
        messages = [
            {"role": "system", "content": extract_feedback_system_prompt},
            {"role": "user", "content": response_text}
        ]
        
        extraction_response = self.ollama_handler.generate_response(
            messages=messages,
            response_format=Judgment # type:ignore
        )
        
        assert isinstance(extraction_response, ChatResponse) and isinstance(extraction_response.response, Judgment), "Unexpected response type from OllamaHandler"
        return extraction_response.response
        
    
    def judge_solution(self, solution: Solution) -> Tuple[bool, Solution]:
        messages = [
            {"role": "system", "content": evaluate_solution_system_prompt},
            {"role": "user", "content": solution.propose_solution}
        ]
        
        response = self.ollama_handler.generate_response(messages=messages)
        
        assert isinstance(response, ChatResponse) and type(response.response) == str, "Unexpected response type from OllamaHandler"
        
        analysis = self.parse_judgment_response(response.response)
        
        if not analysis.is_correct:
            solution.solution_history.append({"role": "judge","content": analysis.feedback})
        
        return analysis.is_correct, solution

    def judge_code(self, solution: Solution)->Tuple[bool, Solution]:
        
        messages = [
            {"role": "system", "content": judge_code_system_prompt.format(criteria=solution.propose_solution)},
            {"role": "user", "content": solution.solution_history[-1]['content']}
        ]
        
        response = self.ollama_handler.generate_response(messages=messages)
        
        assert isinstance(response, ChatResponse) and isinstance(response.response, Judgment), "Unexpected response type from OllamaHandler"
        
        if not response.response.is_correct:
            solution.solution_history.append({"role": "judge","content": response.response.feedback})
        
        return response.response.is_correct, solution
    
    def analyze_test_failures(self, solution: Solution, test_suite:TestSuite, tests_results:TestsResult)->Solution:
        messages = [
            {"role": "system", "content": error_analysis_system_prompt},
            {"role" : "user", "content": analyze_test_failures_user_template.format(
                solution_context=solution.context,
                propose_solution=solution.propose_solution,
                test_code=tests_results.raw_code,
                test_suite_summary=test_suite.test_cases_summary(no_code=True),
                tests_report=tests_results.display_errors()
            )}
        ]
        
        response = self.ollama_handler.generate_response(messages=messages)
        
        assert isinstance(response, ChatResponse) and type(response.response) == str, "Unexpected response type from OllamaHandler"
        solution.solution_history.append({"role": "judge","content": response.response})
        
        new_context_match = re.search(context_pattern, response.response, re.DOTALL | re.IGNORECASE)
        new_propose_solution_match = re.search(propose_solution_pattern, response.response, re.DOTALL | re.IGNORECASE)
        
        if new_context_match and new_propose_solution_match:
            new_context = new_context_match.group(1).strip()
            new_propose_solution = new_propose_solution_match.group(1).strip()
            solution.context = new_context
            solution.propose_solution = new_propose_solution
            return solution
        
        messages = [
            {"role": "system", "content": extract_solution_system_prompt},
            {"role": "user", "content": response.response}
        ]
        
        extraction_response = self.ollama_handler.generate_response(
            messages=messages,
            response_format=BaseSolution # type:ignore
        )
        
        assert isinstance(extraction_response, ChatResponse) and isinstance(extraction_response.response, BaseSolution), "Unexpected response type from OllamaHandler"
        solution.context = extraction_response.response.context
        solution.propose_solution = extraction_response.response.propose_solution
        return solution
        