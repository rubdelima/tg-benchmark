import json
from typing import Dict, Optional, Any
import re

JSON_TAG_PATTERN = re.compile(r'<json>\s*(.*?)\s*</json>', re.DOTALL)
JSON_MARKDOWN_PATTERN = re.compile(r'```(?:json)?\s*(.*?)\s*```', re.DOTALL | re.IGNORECASE)

def extract_json(response_text: str) -> Optional[Dict[str, Any]]:
    matches = JSON_TAG_PATTERN.findall(response_text)
    if matches:
        return _try_parse(matches[-1])

    matches = JSON_MARKDOWN_PATTERN.findall(response_text)
    if matches:
        return _try_parse(matches[-1])

    return None

def _try_parse(json_str: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(json_str.strip())
    except json.JSONDecodeError:
        return None