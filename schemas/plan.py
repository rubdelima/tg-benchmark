from typing import List, Optional, Literal

from pydantic import BaseModel, Field

from schemas.solution import BaseSolution
from schemas.task import BaseTask

class PlanSolutions(BaseModel):
    solutions: List[BaseSolution] = Field(..., description="A list of proposed solutions for the plan.")

class PlanSubtasks(BaseModel):
    skeleton:str = Field(..., description="A pseudo-code skeleton representing the overall structure of the plan.")
    subtasks: List[BaseTask] = Field(..., description="A list of subtasks that must be implemented to solve the main task.")

class PlanResponseModel(BaseModel):
    reasoning: str = Field(..., description="Detailed thought on why the proposed plan was chosen.")
    result_type : Literal['solutions', 'subtasks'] = Field(..., description="Indicates whether the plan consists of direct solutions or a breakdown into subtasks.")

class PlanResponse(PlanResponseModel):
    subtasks : Optional[PlanSubtasks] = Field(None, description="The breakdown of the main task into subtasks, if applicable.")
    solutions : Optional[PlanSolutions] = Field(None, description="A list of proposed solutions for the plan, if applicable.")

__all__ = ["PlanSolutions", "PlanSubtasks", "PlanResponseModel", "PlanResponse"]