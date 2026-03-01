import json
import requests
from typing import Optional, List, Dict, Any


class LLMAdapter:
    def __init__(self, config: Dict[str, Any]):
        self.provider = config.get("provider", "ollama")
        self.model = config.get("model", "qwen2.5:7b")
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.api_key = config.get("api_key", "")
        self.total_tokens = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.request_count = 0
        
    def _update_tokens(self, usage: Dict):
        if usage:
            prompt = usage.get("prompt_tokens", 0) or usage.get("prompt_token_count", 0)
            completion = usage.get("completion_tokens", 0) or usage.get("completion_token_count", 0)
            self.total_prompt_tokens += prompt
            self.total_completion_tokens += completion
            self.total_tokens += prompt + completion
            self.request_count += 1
    
    def get_token_stats(self) -> Dict:
        return {
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "request_count": self.request_count
        }
    
    def reset_stats(self):
        self.total_tokens = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.request_count = 0
    
    def chat(self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        if self.provider == "ollama":
            return self._ollama_chat(messages, tools)
        elif self.provider == "openai":
            return self._openai_chat(messages, tools)
        elif self.provider == "anthropic":
            return self._anthropic_chat(messages, tools)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    def _ollama_chat(self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }
        if tools:
            payload["tools"] = tools
            
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            if "usage" in result:
                self._update_tokens(result["usage"])
            elif "eval_count" in result:
                self._update_tokens({"prompt_tokens": result.get("prompt_eval_count", 0), "completion_tokens": result.get("eval_count", 0)})
            return result
        except requests.exceptions.ConnectionError:
            return {"error": "无法连接到Ollama服务，请确保Ollama正在运行"}
        except Exception as e:
            return {"error": str(e)}
    
    def _openai_chat(self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7
        }
        if tools:
            payload["tools"] = tools
            
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            if "usage" in result:
                self._update_tokens(result["usage"])
            return result
        except Exception as e:
            return {"error": str(e)}
    
    def _anthropic_chat(self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096
        }
        if tools:
            payload["tools"] = tools
            
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def is_available(self) -> bool:
        try:
            if self.provider == "ollama":
                response = requests.get(f"{self.base_url}/api/tags", timeout=5)
                return response.status_code == 200
            return True
        except:
            return False
