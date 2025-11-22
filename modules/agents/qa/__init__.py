
from dataclasses import dataclass, field
import re
from typing import Tuple, Optional
from modules.schemas.tests import TestSuiteComplete, TestSuite, TestsResult, TestCase, TestSuiteBase
from modules.schemas.task import BaseTask

from modules.ollama import OllamaHandler, ChatResponse

from modules.agents.generator_code import GeneratorCodeBaseModel
from modules.agents.qa.prompt import *

from modules.agents.qa.test_runner import TestRunner

CODE_BLOCK_PATTERN = re.compile(r"```(?:python)?\s*(.*?)\s*```", re.DOTALL)

@dataclass
class Carlos(GeneratorCodeBaseModel):
    ollama_handler: OllamaHandler
    retry_attempts: int = 2
    runner: TestRunner = field(default_factory=lambda: TestRunner(max_workers=8))

    def create_tests_suite(self, task: BaseTask) -> TestSuiteComplete:
        reasoning_text = self._step_reasoning(task)

        test_suite_data, raw_code = self._step_extraction(reasoning_text)
        
        final_code = self._repair_code_loop(
            code=raw_code,
            function_name=task.function_name,
            system_prompt_template=fix_code_prompt_template,
            user_prompt_template=fix_code_user_template,
            validation_ignore_func=task.function_name
        )

        return TestSuiteComplete(
            function_name=task.function_name, 
            test_code_raw=final_code, 
            test_cases=test_suite_data.test_cases
        )

    def run_tests(self, test_suite: TestSuiteComplete, implementation: str) -> TestsResult:
        merged_code = test_suite.test_code_raw.replace("# FUNCTION_IMPLEMENTATION_HERE", implementation)
        final_valid_code = self._repair_code_loop(
            code=merged_code,
            function_name=test_suite.function_name,
            system_prompt_template=adjust_code_system_prompt,
            user_prompt_template=adjust_code_user_prompt,
            validation_ignore_func=None
        )
        return self.runner.run(test_suite, final_valid_code)
    
    def _step_reasoning(self, task: BaseTask)->str:
        messages = [
            {
                "role": "system",
                "content": qa_reasoning_system_prompt
            },
            {
                "role": "user",
                "content": qa_reasoning_user_prompt.format(
                    function_name=task.function_name,
                    definition=task.definition,
                    dod=task.dod
                )
            }
        ]
        response = self.ollama_handler.generate_response(messages=messages)
        assert isinstance(response, ChatResponse) and isinstance(response.response, str)
        return response.response
    
    def _step_extraction(self, reasoning_text: str) -> Tuple[TestSuiteBase, str]:
        extracted_code = self.clean_code(reasoning_text)
        if extracted_code:
            return self._extract_cases_only(reasoning_text, extracted_code)
        
        return self._extract_full_suite(reasoning_text)
    
    def _extract_cases_only(self, reasoning_text: str, code: str) -> Tuple[TestSuiteBase, str]:
        messages = [
            {"role": "system", "content": extraction_cases_prompt},
            {"role": "user", "content": reasoning_text}
        ]
        
        response = self.ollama_handler.generate_response(
            messages=messages,
            response_format=TestSuiteBase # type: ignore
        )
        
        assert isinstance(response, ChatResponse) and isinstance(response.response, TestSuiteBase)
        
        return response.response, code

    def _extract_full_suite(self, reasoning_text: str) -> Tuple[TestSuiteBase, str]:
        messages = [
            {"role": "system", "content": extraction_full_suite_prompt},
            {"role": "user", "content": reasoning_text}
        ]
        
        response = self.ollama_handler.generate_response(
            messages=messages,
            response_format=TestSuite # type: ignore
        )
        
        assert isinstance(response, ChatResponse) and isinstance(response.response, TestSuite)
        
        return response.response, response.response.test_code_raw
    
    def _repair_code_loop(
        self, 
        code: str, 
        function_name: str, 
        system_prompt_template: str, 
        user_prompt_template: str,
        validation_ignore_func: Optional[str] = None
    ) -> str:
        current_code = code
        check_result = self.parse_code(current_code, ignore_function=validation_ignore_func)
        retries = self.retry_attempts

        while not check_result.success and retries > 0:
            error_msg = "\n".join(check_result.errors)
            user_content = user_prompt_template.format(
                function_name=function_name,
                code=current_code,
                error_msg=error_msg
            )

            try:
                sys_content = system_prompt_template.format(function_name=function_name)
            except KeyError:
                sys_content = system_prompt_template

            messages = [
                {"role": "system", "content": sys_content},
                {"role": "user", "content": user_content}
            ]

            fix_response = self.ollama_handler.generate_response(messages=messages)
            assert isinstance(fix_response, ChatResponse) and isinstance(fix_response.response, str)

            cleaned_fix = self.clean_code(fix_response.response)
            current_code = cleaned_fix if cleaned_fix else fix_response.response

            check_result = self.parse_code(current_code, ignore_function=validation_ignore_func)
            retries -= 1

        return current_code