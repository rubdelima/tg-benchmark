

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
  errors: list[ErrorDetail]

class TestCase(BaseModel):
    inputs : str
    expected_output: str

class TestSuite(BaseModel):
    test_cases: List[TestCase]
    test_code_raw:str

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
    status: Literal['completed','running','fail']
    up_task: Optional['Task'] = None
    history: List[dict] = []
    evidence: Optional[str] = None
    template : str = ''
    best_solution: str = ''
    code: str =''
    test_suite: TestSuite
    subproblems: List['Task'] = []

class BaseSolution(BaseModel):
    context: str
    propose_solution: str

class Solution(BaseSolution):
    status: Literal['success','pending','fail']
    remaining_retrials: int
    problem: Task
    best_code: Optional[str] = None
    success_rate: float = 0.0
    solution_history: List[dict] = []
    template : str = ''

class PlanBase(BaseModel):
    skeleton: str

class PlanSolutions(PlanBase):
    solutions: List[BaseSolution]

class PlanSubtasks(PlanBase):
    subtasks: List[BaseTask]

class PlanResponseModel(BaseModel):
    result : List[PlanSolutions] | List[PlanSubtasks]

class PlanResponse:
    plan: PlanResponseModel
    plan_type: Literal['solutions', 'subtasks']

