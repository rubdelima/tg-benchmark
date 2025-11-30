
import ollama
import subprocess
from pydantic import BaseModel
from typing import Dict, Union, Literal, Optional, Generic, Any, TypeVar, overload, Type, List
import time
from tqdm.auto import tqdm # type: ignore
import json
from modules.logger import get_logger, StatusContext
from contextlib import nullcontext

logger = get_logger(__name__)

T = TypeVar('T')
M = TypeVar('M', bound=BaseModel)

stream_text_template_thinking = \
"""
[reverse]Thinking[/reverse]
[dim][italic]
{thinking}
[/italic][/dim]
"""

stream_text_template_response = \
"""
[reverse]Response[/reverse]
{response}
[reverse]Raw Response[/reverse]

[center][dim]Time Elapsed: {inference_time:.2f}s[/dim][/center]
"""

class ChatResponse(BaseModel, Generic[T]):
    inference_time: float
    input_tokens: int
    output_tokens: int
    thinking: str
    response: T
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
            ollama.chat( # type: ignore
                model=model_name,
                messages=[{"role" : "user", "content" : "Return 'hi'"}],
                keep_alive="-1m"
            )
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def _check_ollama_installed(self) -> bool:
        try:
            result = subprocess.run(
                ['ollama', 'list'], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False

    def check_and_pull_model(self, model_name: str):
        models_available = ollama.list()
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
    
    @overload
    def chat(self, messages: List[Dict], response_format: Type[dict], status_context: Optional["StatusContext"]=None) -> ChatResponse[dict]: ...
    
    @overload
    def chat(self, messages: List[Dict], response_format: Type[M], status_context: Optional["StatusContext"]=None) -> ChatResponse[M]: ...
    
    @overload
    def chat(self, messages: List[Dict], response_format: Optional[Type[str]] = None, status_context: Optional["StatusContext"]=None) -> ChatResponse[str]: ...
    
    # --- IMPLEMENTAÇÃO UNIFICADA ---
    def chat(self, messages: list[Dict], response_format: Optional[Union[Type[str], Type[dict], Type[M]]]=None, status_context: Optional["StatusContext"]=None) -> ChatResponse:
        
        # 1. Gestão de Contexto Seguro
        if status_context:
            ctx_manager = nullcontext(status_context)
        else:
            ctx_manager = StatusContext(f"Generating response ({self.model_name})...")

        # 2. Prepara parâmetros
        ollama_format = None
        if response_format is dict:
            ollama_format = "json"
        elif response_format is not None and issubclass(response_format, BaseModel):
            ollama_format = response_format.model_json_schema()

        # 3. Inicia Stream
        start_time = time.time()
        
        stream_response = ollama.chat( #type: ignore
            model=self.model_name,
            messages=messages,
            options={"temperature": self.temperature, "num_predict": 8192},
            format=ollama_format, # type: ignore
            stream=True
        )
        
        full_thinking = ""
        full_response = ""
        input_tokens = 0
        output_tokens = 0
        last_chunk_raw = {} #type:ignore

        # 4. Consome Stream e Atualiza UI
        with ctx_manager as sc:
            for chunk in stream_response:
                # Extrai conteúdo do objeto Message
                msg = chunk.message
                chunk_content = msg.content if msg.content else ""
                chunk_thinking = ""
                if hasattr(msg, 'thinking') and msg.thinking:
                    chunk_thinking = msg.thinking

                full_response += chunk_content
                full_thinking += chunk_thinking
                
                # Coleta métricas (se disponíveis)
                if chunk.prompt_eval_count: input_tokens = chunk.prompt_eval_count
                if chunk.eval_count: output_tokens = chunk.eval_count
                if chunk.done: 
                    last_chunk_raw = chunk.model_dump() if hasattr(chunk, 'model_dump') else dict(chunk)

                # Atualiza UI se o contexto for válido
                if sc:
                    current_time = time.time() - start_time
                    status_text = self._stream_update_status_str(
                        full_thinking, 
                        full_response, 
                        current_time
                    )
                    sc.update(status_text)
            sc.update(f"Generation completed in {time.time() - start_time:.2f}s. With {input_tokens} input tokens and {output_tokens} output tokens.")
        
        total_time = time.time() - start_time
        
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        
        # 5. Parse Final
        final_response = self._parse_response(full_response, response_format)

        return ChatResponse(
            inference_time=total_time,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking=full_thinking,
            response=final_response,
            raw_response=last_chunk_raw
        )
                    
    @staticmethod
    def _parse_response(response_content: str, response_format):
        if not response_content: return ""
        
        try:
            if response_format is dict:
                return json.loads(response_content)
            
            if response_format is str or response_format is None:
                return response_content
            
            # Pydantic
            return response_format.model_validate_json(response_content)
        except Exception as e:
            # Fallback seguro para string em caso de erro de parse
            return response_content
    
    @staticmethod
    def _stream_update_status_str(thinking: str, response: str, inference_time: float):
        output_str = ""
        
        # Se houver pensamento (Thinking Block)
        if thinking:
            # Aqui ainda recomendo manter um limite se o pensamento for GIGANTE, 
            # mas vamos liberar as quebras de linha.
            # Se quiser ver o pensamento TODO, remova o slice [-500:].
            preview_thinking = thinking.replace('\n', '\n') # Garante quebras reais
            output_str += stream_text_template_thinking.format(thinking=preview_thinking)
        
        # --- CORREÇÃO AQUI ---
        # 1. Removemos o slice ([-600:]) para mostrar o texto COMPLETO.
        # 2. Removemos o .replace('\n', '⏎') para ter quebras de linha reais.
        # 3. Adicionamos um '\n' antes para garantir que o texto não cole no título.
        
        output_str += stream_text_template_response.format(
            response=response, 
            inference_time=inference_time
        )
        
        return output_str
    
    def close(self):
        result = subprocess.run(
            ["ollama", "stop", self.model_name],
            capture_output=True, text=True
        )
