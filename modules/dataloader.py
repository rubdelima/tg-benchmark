from pydantic import BaseModel
from pathlib import Path

class QuestionDatasetBase(BaseModel):
    question_id : str
    difficulty : str
    title : str
    content : str

class TestCase(BaseModel):
    input : str
    output : str

class QuestionDataset(QuestionDatasetBase):
    public_test_cases : list[TestCase] = []
    private_test_cases : list[TestCase] = []

class Dataloader:
    def __init__(self, dataset: list[QuestionDatasetBase]):
        self.dataset = dataset
    
    def __len__(self):
        return len(self.dataset)
    
    def __getitem__(self, idx:int)->QuestionDataset:
        return QuestionDataset(
            **self.dataset[idx].model_dump(),
            public_test_cases = self._get_test_cases(self.dataset[idx].question_id, "public"),
            private_test_cases = self._get_test_cases(self.dataset[idx].question_id, "private")
        )
    
    def __iter__(self):
        for item in self.dataset:
            yield item
    
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
            with open(input_path, "r") as infile, open(output_path, "r") as outfile:
                test_case = TestCase(
                    input=infile.read(),
                    output=outfile.read()
                )
                test_cases.append(test_case)
            idx += 1
        return test_cases
    
    