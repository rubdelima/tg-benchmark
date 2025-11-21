from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import tempfile
import os
import time

from dataclasses import dataclass

from modules.models import TestSuite, BaseTask, ErrorDetail, TestsResult, TestSuiteComplete
from modules.ollama import OllamaHandler
from modules.agents.utils import parse_code

qa_testsuite_prompt_template = \
"""
You are a rigorous and detail-oriented QA engineer.

You will be given:
- A task definition describing what the system must accomplish.
- A general problem description that provides context and expected behavior.
- The name of the function to be implemented: `{function_name}`

Your job is to:
1. Carefully read and understand the task and problem description.
2. Think critically about edge cases, typical scenarios, and failure conditions.
3. Design a set of test cases that thoroughly validate the behavior of the function `{function_name}`.
4. Return a JSON object matching the following structure:

```json
{{{{
  "test_code_raw": "<Python code containing the test logic and the line # FUNCTION_IMPLEMENTATION_HERE>",
  "testcases": [
    {{{{
      "input": "<raw input string to be passed to the function>",
      "expected_output": "<expected output string>"
    }}}},
    ...
  ]
}}}}
```

### Example:

Task:
Create a function that receives two integers and returns their sum.

Function name: `sum_two_numbers`

Function signature: `def sum_two_numbers(a: int, b: int) -> int`

Input format: Two integers separated by comma (e.g., "5,3")

Expected output format: The sum as a string (e.g., "8")

Example output:

```json
{{{{
  "test_code_raw": "# FUNCTION_IMPLEMENTATION_HERE\\n\\nimport sys\\nfor line in sys.stdin:\\n    try:\\n        num1, num2 = line.strip().split(',')\\n        result = sum_two_numbers(int(num1), int(num2))\\n        print(result)\\n    except ValueError:\\n        print('ValueError')",
  "testcases": [
    {{{{
      "input": "5,3",
      "expected_output": "8"
    }}}},
    {{{{
      "input": "10,20",
      "expected_output": "30"
    }}}}
  ]
}}}}
```

REMEMBER: 
    - Always convert stdin input strings to the correct types before calling the function!
    - Its function is only to create the environment for testing the function. Do not implement the function, just call the function {function_name} in the main module.
    - Remember to include the placeholder "# FUNCTION_IMPLEMENTATION_HERE" and call the function {function_name} in the code.

Now generate a similar JSON object for the user task and function.
"""

user_task_prompt_template = \
"""
This is the task definition:
{definition}

And this is the definition of done of this task:
{dod}
"""

adjust_code_prompt_template = \
"""
You are a precise and careful code engineer.

You will be given a Python code snippet that includes a function named `{function_name}`. Your task is to adjust the surrounding code — such as input/output handling, test harnesses, or structural wrappers — to make the code executable and functional in a standard Python environment.

You must NOT change the logic, structure, or behavior of the function `{function_name}` itself. The function must remain exactly as it was provided.

Your responsibilities:
1. Ensure the code runs correctly from the command line or as a script.
2. Add or fix any necessary boilerplate (e.g., `if __name__ == "__main__":`, input parsing, output formatting).
3. Do not modify the function `{function_name}` in any way.
4. Do not add comments or explanations — return only the adjusted code.
5. Your output must be a single, complete Python code block.

The goal is to make the code runnable and testable, while preserving the original function logic.

Begin with the following code:
"""

def execute_single_test(temp_file, test_input, expected_output, timeout=5):
    try:
        start = time.time()
        result = subprocess.run(
            ['python', temp_file],
            input=test_input,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        exec_time = time.time() - start
        actual_output = result.stdout.strip()
        if actual_output == expected_output.strip():
            return (True, None, exec_time)
        else:
            err_detail = ErrorDetail(
                test_input=test_input,
                expected_output=expected_output,
                actual_output=actual_output,
                error_message=result.stderr.strip()
            )
            return (False, err_detail, exec_time)
    except subprocess.TimeoutExpired:
        err_detail = ErrorDetail(
            test_input=test_input,
            expected_output=expected_output,
            actual_output='',
            error_message=f'Timeout exceeded ({timeout}s)'
        )
        return (False, err_detail, timeout)
    except Exception as e:
        err_detail = ErrorDetail(
            test_input=test_input,
            expected_output=expected_output,
            actual_output='',
            error_message=str(e)
        )
        return (False, err_detail, 0)

def run_tests_parallel(test_suite, implementation):
    total_tests = len(test_suite.test_cases)
    passed_tests = 0
    errors = []
    total_time = 0.0

    test_code = test_suite.test_code_raw.replace("# FUNCTION_IMPLEMENTATION_HERE", implementation)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        temp_file = f.name
        f.write(test_code)

    def task_runner(test_case):
        return execute_single_test(temp_file, test_case.inputs, test_case.expected_output)

    try:
        with ThreadPoolExecutor(max_workers=min(8, total_tests)) as executor:
            all_futures = [executor.submit(task_runner, tc) for tc in test_suite.test_cases]
            for future in as_completed(all_futures):
                ok, err, exec_time = future.result()
                total_time += exec_time
                if ok:
                    passed_tests += 1
                else:
                    errors.append(err)
    finally:
        os.unlink(temp_file)

    return TestsResult(
        total_time=total_time,
        passed_tests=passed_tests,
        total_tests=total_tests,
        success_rate=passed_tests / total_tests if total_tests > 0 else 0.0,
        errors=errors
    )


@dataclass
class Carlos:
    ollama_handler: OllamaHandler
    retry_attempts: int = 2
    
    def create_tests_suite(self, task: BaseTask)->TestSuiteComplete:
        messages = [
            {
                "role": "system",
                "content": qa_testsuite_prompt_template.format(
                    function_name=task.function_name,
                ),
            },
            {
                "role": "user",
                "content": user_task_prompt_template.format(
                    definition=task.definition,
                    dod=task.dod
                )
            }
        ]
        response = self.ollama_handler.generate_response(
            messages=messages,
            response_format=TestSuite # type:ignore
        )
        return TestSuiteComplete(function_name=task.function_name, **response.response.model_dump())# type:ignore
    
    def run_tests(self, test_suite: TestSuiteComplete, implementation:str)->TestsResult:
        test_code = test_suite.test_code_raw.replace(
            "# FUNCTION_IMPLEMENTATION_HERE", implementation)
        
        for _ in range(self.retry_attempts):
            try:
                parse_code(test_code)
            except ValueError as e:
                fixed_code = self.ollama_handler.generate_response(
                    messages=[
                        {
                            "role" : "system",
                            "content": adjust_code_prompt_template.format(
                                function_name=test_suite.function_name
                            )
                        },
                        {
                            "role": "user",
                            "content": (
                                "The combined test code and implementation has syntax errors. "
                                "Please review the code and provide a corrected version that is valid Python code. "
                                "Here is the error message:\n"
                                f"{str(e)}"
                            )
                        }
                    ]
                )
                test_code = parse_code(fixed_code.response) # type:ignore
        
        return run_tests_parallel(test_suite, test_code)
        