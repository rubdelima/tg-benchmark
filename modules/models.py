

from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class ErrorDetail(BaseModel):
    test_input: str
    expected_output: str
    actual_output: str
    error_message: str
  
class TestsResult(BaseModel):
  total_time: float
  passed_tests: int
  total_tests: int
  success_rate: float
  errors: list[ErrorDetail]

class TestCase(BaseModel):
    inputs : str
    expected_output: str

class TestSuite(BaseModel):
    test_cases: List[TestCase]
    test_code_raw:str
    
    def test_cases_summary(self) -> str:
        summary = "Code for tests:\n"
        summary += self.test_code_raw + "\n\n" + "Test Cases Summary:\n"
        for i, tc in enumerate(self.test_cases):
            summary += f"Test Case {i+1}:\nInput: {tc.inputs}\nExpected Output: {tc.expected_output}\n\n"
        return summary.strip()

class TestSuiteComplete(TestSuite):
    function_name: str

class FunctionArgs(BaseModel):
    name: str
    type: str
    description: Optional[str] = None

class BaseTask(BaseModel):
    definition: str
    function_name : str
    args: List[FunctionArgs] = []
    dod: str
    keywords: List[str]

class Task(BaseTask):
    status: Literal['completed','running','fail'] = 'running'
    test_suite: TestSuiteComplete    
    evidence: Optional[str] = None
    template : str = ''
    best_solution: str = ''
    best_solution_rating: float = 0.0
    code: str =''

class BaseSolution(BaseModel):
    context: str
    propose_solution: str

class Solution(BaseSolution):
    best_code: str = ''
    success_rate: float = 0.0
    solution_history: List[dict] = []

class PlanBase(BaseModel):
    skeleton: str

class PlanSolutions(PlanBase):
    solutions: List[BaseSolution]

class PlanSubtasks(PlanBase):
    skeleton:str
    subtasks: List[BaseTask]

class PlanResponseModel(BaseModel):
    reasoning: Optional[str] = None
    result_type : Literal['solutions', 'subtasks']

class PlanResponse(PlanResponseModel):
    subtasks : Optional[PlanSubtasks] = None
    solutions : Optional[List[BaseSolution]] = None
    

