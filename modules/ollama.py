
import ollama
import subprocess
from rich import print
from pydantic import BaseModel
from typing import Dict, Union, Literal, Optional, Generator, Any
import time
from tqdm.auto import tqdm
import json

class ChatResponse(BaseModel):
    inference_time: float
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    thinking: Optional[str] = None
    response: Union[str, Dict, BaseModel]
    raw_response: Dict[str, Any]


class OllamaHandler:
    def __init__(self, model_name: str, temperature: float = 0.0, keep_alive: bool=False):
        if not self._check_ollama_installed():
            raise EnvironmentError(
                "Ollama CLI is not installed or not found in PATH.")
        self.check_and_pull_model(model_name)
        self.model_name = model_name
        self.temperature = temperature
        if keep_alive:
            ollama.chat(
                model=model_name,
                messages=[{"role" : "user", "content" : "Return 'hi'"}],
                keep_alive="-1m"
            )

    def _check_ollama_installed(self) -> bool:
        try:
            result = subprocess.run(
                ['ollama', 'list'], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False

    def check_and_pull_model(self, model_name: str):
        models_available = ollama.list()  # type:ignore
        available_model_names = [
            model.model for model in models_available.models]
        if model_name in available_model_names:
            return
        current_digest, bars = '', {}
        
        for progress in ollama.pull(model_name, stream=True):
          digest = progress.get('digest', '')
          if digest != current_digest and current_digest in bars:
            bars[current_digest].close()

          if not digest:
            print(progress.get('status'))
            continue
        
          if digest not in bars and (total := progress.get('total')):
            bars[digest] = tqdm(total=total, desc=f'pulling {digest[7:19]}', unit='B', unit_scale=True)

          if completed := progress.get('completed'):
            bars[digest].update(completed - bars[digest].n)

          current_digest = digest
        

    def generate_response(self, messages: list[dict], stream: bool=False, response_format: Optional[Union[Literal["json"], BaseModel]] = None) -> Union[Generator[ChatResponse, None, None], ChatResponse]:
        format_param = None
        if response_format is not None:
            if isinstance(response_format, type) and issubclass(response_format, BaseModel):
                format_param = response_format.model_json_schema()
            else:
                format_param = response_format
                
        start_time = time.time()
        response = ollama.chat( #type:ignore
            model=self.model_name,
            messages=messages,
            options={"temperature": self.temperature},
            format=format_param, #type:ignore
            stream=stream
        )

        if stream:
            def _chat_stream():
                for chunk in response:
                    elapsed_time = time.time() - start_time
                    yield ChatResponse(
                        inference_time=elapsed_time,
                        input_tokens=chunk.prompt_eval_count,
                        output_tokens=chunk.eval_count,
                        thinking=chunk.message.get("thinking", ""),
                        response=chunk.message.content,
                        raw_response=chunk.message.model_dump(),
                    )
            return _chat_stream()

        response_content = response.message.content
        if response_format == "json":
            response_content = json.loads(response.message.content)
        elif isinstance(response_format, type) and issubclass(response_format, BaseModel):
            response_content = response_format.model_validate_json(response.message.content)
        
        return ChatResponse(
            inference_time=time.time() - start_time,
            input_tokens=response.prompt_eval_count,
            output_tokens=response.eval_count,
            thinking=response.message.get("thinking", ""),
            response=response_content,
            raw_response=response.message.model_dump(),
        )
    
    def close(self):
        result = subprocess.run(
            ["ollama", "stop", self.model_name],
            capture_output=True, text=True
        )
