import os
import json
import requests
import socket
from typing import Dict, Any, Optional
from utils.logging_config import logger

class OllamaClient:
    """
    Robust Ollama integration for Llama 3.2.
    Includes cached health check, fast socket probe, and graceful fallbacks.
    """
    _connection_cached: Optional[bool] = None

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.2")
        self.is_connected = self._check_connection()

    def _check_connection(self) -> bool:
        if OllamaClient._connection_cached is not None:
            return OllamaClient._connection_cached

        if os.getenv("OLLAMA_OFFLINE", "false").lower() in ("true", "1", "yes") or \
           os.getenv("OLLAMA_ENABLED", "true").lower() in ("false", "0", "no"):
            OllamaClient._connection_cached = False
            logger.info("OLLAMA_OFFLINE set. Operating in deterministic offline mode.")
            return False

        # Fast socket probe on port 11434 (< 50ms) to avoid timeout delay if offline
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.05)
            # Default host 127.0.0.1, port 11434
            res = s.connect_ex(('127.0.0.1', 11434))
            s.close()
            if res == 0:
                OllamaClient._connection_cached = True
                logger.info(f"Ollama server connected at {self.base_url}. Using model: {self.model}")
                return True
        except Exception:
            pass

        OllamaClient._connection_cached = False
        logger.warning(
            f"Ollama instance at {self.base_url} is unreachable. Operating in deterministic offline mode."
        )
        return False

    def generate_json(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """
        Sends request to Ollama and guarantees JSON return.
        Falls back to empty dictionary if unavailable.
        """
        if not self.is_connected:
            return {}

        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": (
                    system_prompt +
                    "\nIMPORTANT: Respond ONLY with valid, raw JSON. Do not include markdown codeblocks or explanations."
                ),
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1
                }
            }
            res = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=10)
            if res.status_code == 200:
                resp_json = res.json()
                response_text = resp_json.get("response", "").strip()
                if response_text.startswith("```"):
                    lines = response_text.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    response_text = "\n".join(lines).strip()
                return json.loads(response_text)
        except Exception as e:
            logger.error(f"Ollama inference error: {e}. Switching to deterministic fallback.")

        return {}
