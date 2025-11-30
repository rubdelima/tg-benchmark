from typing import List
from pydantic import BaseModel
from pathlib import Path
import random
import json
from schemas.tests import TestCase

class QuestionDatasetBase(BaseModel):
    question_id : str
    difficulty : str
    title : str
    content : str

class QuestionDataset(QuestionDatasetBase):
    public_test_cases : List[TestCase] = []
    private_test_cases : List[TestCase] = []

class Dataloader:
    def __init__(self, dataset: List[QuestionDatasetBase]):
        self.dataset_list = dataset
        self.dataset_dict = {item.question_id: item for item in dataset}
    
    def __len__(self):
        return len(self.dataset_list)
    
    def __getitem__(self, idx:int|str)->QuestionDataset:
        target = self.dataset_list if type(idx) == int else self.dataset_dict
        item = target[idx] # type: ignore
        return QuestionDataset(
            **item.model_dump(),
            public_test_cases = self._get_test_cases(item.question_id, "public"),
            private_test_cases = self._get_test_cases(item.question_id, "private")
        )
    
    def __iter__(self):
        for item in self.dataset_list:
            yield QuestionDataset(
            **item.model_dump(),
            public_test_cases = self._get_test_cases(item.question_id, "public"),
            private_test_cases = self._get_test_cases(item.question_id, "private")
        )
    
    @classmethod
    def load_jsonl(cls, filepath:str)->'Dataloader':
        with open(filepath, "r", encoding="utf-8") as f:
            dataset_lines = [json.loads(line) for line in f]
        dataset = [QuestionDatasetBase(**line) for line in dataset_lines]
        return cls(dataset)
    
    def _get_test_cases(self, question_id:str, test_type:str)->list[TestCase]:
        dir_path = Path(f"./data/{question_id}/{test_type}")
        test_cases : list[TestCase] = []
        if not dir_path.exists():
            return test_cases
        
        idx = 0
        while True:
            input_path = dir_path / f"{idx}.in"
            output_path = dir_path / f"{idx}.out"
            if not input_path.exists() or not output_path.exists():
                break
            with open(input_path, "r", encoding="utf-8") as infile, open(output_path, "r", encoding="utf-8") as outfile:
                test_case = TestCase(
                    inputs=infile.read(),
                    expected_output=outfile.read()
                )
                test_cases.append(test_case)
            idx += 1
        return test_cases
    
def load_dataloader(easy:int, medium:int, hard:int, random_seed:int=42)->Dataloader:
    with open("./data/dataset.jsonl", "r", encoding="utf-8") as f:
        dataset_lines = [json.loads(line) for line in f]
    
    random.seed(random_seed)
    easy_questions = [line for line in dataset_lines if line['difficulty'] == 'easy']
    medium_questions = [line for line in dataset_lines if line['difficulty'] == 'medium']
    hard_questions = [line for line in dataset_lines if line['difficulty'] == 'hard']
    
    selected_questions = random.sample(easy_questions, min(easy, len(easy_questions))) + \
                         random.sample(medium_questions, min(medium, len(medium_questions))) + \
                         random.sample(hard_questions, min(hard, len(hard_questions)))
    random.shuffle(selected_questions)
    dataset = [QuestionDatasetBase(**question) for question in selected_questions]
    return Dataloader(dataset)