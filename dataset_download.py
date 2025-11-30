from datasets import load_dataset #type: ignore
from tqdm.auto import tqdm #type: ignore
from pathlib import Path
from modules.dataloader import QuestionDatasetBase
import json

def save_test_cases(test_cases_str:str, test_type:str, question_id:str):
    test_cases :dict = json.loads(test_cases_str)
    dir_path = Path(f"./data/{question_id}/{test_type}")
    dir_path.mkdir(parents=True, exist_ok=True)
    
    for idx, test_case in enumerate(test_cases):
        with open(dir_path / f"{idx}.in", "w", encoding="utf-8") as infile:
            infile.write(test_case['input'])
        with open(dir_path / f"{idx}.out", "w", encoding="utf-8") as outfile:
            outfile.write(test_case['output'])

def create_dataset_line(line)-> QuestionDatasetBase:
    save_test_cases(line['public_test_cases'], "public", line['question_id'])
    save_test_cases(line['private_test_cases'], "private", line['question_id'])
    return QuestionDatasetBase(
        question_id = line['question_id'],
        difficulty = line['difficulty'],
        title = line['question_title'],
        content = line['question_content']
    )
    
ds = load_dataset("livecodebench/code_generation", split="test", streaming=True)
dataset_lines = []

for line in tqdm(ds, total=290):
    dataset_line = create_dataset_line(line)
    dataset_lines.append(dataset_line.model_dump())

with open(".data/dataset.jsonl", "w", encoding="utf-8") as f:
    for data_line in dataset_lines:
        f.write(json.dumps(data_line) + "\n")