from typing import List, Optional
from pydantic import BaseModel, Field
from modules.schema.tests import TestSuiteComplete

class FunctionArgs(BaseModel):
    name: str = Field(..., description="Name of the function argument")
    type: str = Field(..., description="Type of the function argument")
    description: Optional[str] = Field(None, description="Description of the function argument")

class BaseTask(BaseModel):
    definition: str = Field(..., description="Definition of the task")
    function_name : str = Field(..., description="Name of the function to be implemented")
    args: List[FunctionArgs] = Field([], description="List of function arguments")
    dod: str = Field(..., description="Definition of Done for the task")
    keywords: List[str] = Field([], description="List of keywords associated with the task")

class Task(BaseTask):
    test_suite: TestSuiteComplete = Field(..., description="Test suite associated with the task")
    template : str = Field("", description="Template for the task resolution")
    best_solution: str = Field("", description="Best solution for resolve this task")
    best_solution_rating: float = Field(0.0, description="Rating of the best solution (0.0 - 1.0, 1.0 means 100%)")
    code: str = Field("", description="Code for the task solution")

__all__ = ["BaseTask", "Task", "FunctionArgs"]