from typing import List
from pydantic import BaseModel, Field
from schemas.task import FunctionArgs

class BaseSolution(BaseModel):
    context: str = Field(..., description="Context of the overall task to be solved, and how this solution proposes to solve that task. History of attempts, errors, and lessons learned.")
    propose_solution: str = Field(..., description="Step-by-step instructions on how this solution should be implemented.")

class Solution(BaseSolution):
    function_name: str = Field("", description="The name of the main function implemented in the solution.")
    args: List[FunctionArgs] = Field([], description="List of function arguments")
    best_code: str = Field("", description="The atual best code implementation for the proposed solution.")
    success_rate: float = Field(-1.0, description="A float between 0.0 and 1.0 indicating the success rate of the solution.")
    solution_history: List[dict] = Field([], description="A list of dictionaries recording the history of solution attempts, including errors and lessons learned.")

__all__ = ["BaseSolution", "Solution"]