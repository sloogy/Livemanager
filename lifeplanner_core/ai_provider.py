from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class AIProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class OllamaProvider:
    endpoint: str = "http://127.0.0.1:11434"
    timeout: float = 5.0

    def _validated_base(self) -> str:
        parsed = urlparse(self.endpoint)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise AIProviderError("Aus Datenschutzgründen sind standardmäßig nur lokale Ollama-Endpunkte erlaubt")
        return self.endpoint.rstrip("/")

    def healthcheck(self) -> bool:
        try:
            with urlopen(self._validated_base() + "/api/tags", timeout=self.timeout) as response:
                return 200 <= response.status < 300
        except Exception:
            return False

    def generate(self, model: str, prompt: str) -> str:
        if not model.strip() or not prompt.strip():
            raise AIProviderError("Modell und Prompt dürfen nicht leer sein")
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
        request = Request(
            self._validated_base() + "/api/generate",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=max(self.timeout, 60.0)) as response:
                result = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise AIProviderError(f"Ollama-Anfrage fehlgeschlagen: {exc}") from exc
        return str(result.get("response", ""))
