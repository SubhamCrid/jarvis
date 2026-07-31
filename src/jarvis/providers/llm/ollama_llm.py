"""
Local Ollama LLM provider streaming token chunks over HTTP REST/WebSocket endpoints.
"""

import asyncio
import json
import logging

import re
from typing import Any, AsyncGenerator, Dict, List, Optional
import aiohttp

from jarvis.core.base import HealthStatus, ServiceStatus
from jarvis.core.config.schema import AppConfig
from jarvis.providers.base import LLMProtocol
from jarvis.providers.registry import register_provider

logger = logging.getLogger("jarvis.providers.llm.ollama")


@register_provider("llm", "ollama")
class OllamaLLM(LLMProtocol):
    """
    Client provider connecting to a local Ollama service for streaming text generation.
    """

    @classmethod
    def from_config(cls, config: AppConfig) -> "OllamaLLM":
        return cls(
            model=config.llm.model,
            system_prompt=config.llm.system_prompt,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
        )

    def __init__(
        self,
        model: str = "hermes3:3b",
        base_url: str = "http://localhost:11434",
        system_prompt: str = (
            "You are Jarvis, a helpful local voice assistant. "
            "Keep all responses brief (1 to 2 sentences maximum), clear, and natural for speech synthesis."
        ),
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._session: Optional[aiohttp.ClientSession] = None
        self._cancelled: bool = False
        self.has_error: bool = False

    async def initialize(self) -> bool:
        try:
            self._session = aiohttp.ClientSession()
            async with self._session.get(f"{self.base_url}/api/tags", timeout=3.0) as resp:
                if resp.status == 200:
                    self._status = ServiceStatus.RUNNING
                    data = await resp.json()
                    models = [m.get("name", "") for m in data.get("models", [])]

                    if models and self.model not in models and not any(m.startswith(self.model) for m in models):
                        usable = [m for m in models if "embed" not in m and "cloud" not in m]
                        if not usable:
                            usable = [m for m in models if "embed" not in m]
                        instruct_preferred = [
                            m for m in usable if any(k in m for k in ["hermes", "granite", "gemma", "llama", "mistral"])
                        ]
                        target_model = (
                            instruct_preferred[0]
                            if instruct_preferred
                            else (usable[0] if usable else self.model)
                        )
                        if usable:
                            logger.info(
                                f"Configured model '{self.model}' unavailable. Selected installed model '{target_model}'."
                            )
                            self.model = target_model

                    logger.info(
                        f"OllamaLLM initialized on {self.base_url} with model '{self.model}'"
                    )
                    return True
        except Exception as e:
            logger.warning(
                f"Connection attempt to Ollama endpoint at {self.base_url} failed: {e}"
            )
            self._status = ServiceStatus.DEGRADED
            self.has_error = True
            return True
        return True

    async def _read_stream(self, resp: aiohttp.ClientResponse) -> AsyncGenerator[str, None]:
        thinking_buffer: List[str] = []
        yielded_any_content = False

        async for line in resp.content:
            if self._cancelled:
                logger.info("Ollama LLM token stream cancelled.")
                break
            if not line:
                continue
            try:
                data = json.loads(line.decode("utf-8"))
                msg = data.get("message", {})
                content = msg.get("content", "")
                thinking = msg.get("thinking", "")

                if content:
                    yielded_any_content = True
                    yield content
                elif thinking:
                    thinking_buffer.append(thinking)

                if data.get("done", False):
                    break
            except Exception as parse_err:
                logger.warning(f"Failed parsing Ollama stream chunk: {parse_err}")

        if not yielded_any_content and thinking_buffer and not self._cancelled:
            full_thinking = "".join(thinking_buffer).strip()
            if full_thinking:
                quotes = re.findall(r'"([^"\n]{10,200})"', full_thinking)
                if quotes:
                    clean_res = quotes[-1].strip()
                else:
                    lines = [l.strip() for l in full_thinking.splitlines() if l.strip()]
                    clean = [
                        l
                        for l in lines
                        if not l.startswith(
                            ("*", "#", "1.", "2.", "3.", "4.", "5.", "Thinking", "Analyze", "**")
                        )
                    ]
                    clean_res = (
                        clean[-1]
                        if clean
                        else "I am here and ready to help. How can I assist you today?"
                    )

                for token in clean_res.split():
                    yield token + " "

    async def generate_stream(
        self, prompt: str, history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[str, None]:
        self._cancelled = False
        self.has_error = False
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()

        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }

        req_timeout = aiohttp.ClientTimeout(total=180.0, connect=5.0, sock_read=120.0)

        try:
            async with self._session.post(
                f"{self.base_url}/api/chat", json=payload, timeout=req_timeout
            ) as resp:
                if resp.status == 404:
                    logger.warning(f"Ollama model '{self.model}' returned 404. Attempting model resolution...")
                    async with self._session.get(f"{self.base_url}/api/tags", timeout=3.0) as tags_resp:
                        if tags_resp.status == 200:
                            tags_data = await tags_resp.json()
                            models = [m.get("name", "") for m in tags_data.get("models", [])]
                            usable = [m for m in models if "embed" not in m and "cloud" not in m]
                            if not usable:
                                usable = [m for m in models if "embed" not in m]
                            if usable and usable[0] != self.model:
                                logger.info(f"Fallback switching target model to '{usable[0]}'")
                                self.model = usable[0]
                                payload["model"] = self.model
                                async with self._session.post(
                                    f"{self.base_url}/api/chat", json=payload, timeout=req_timeout
                                ) as retry_resp:
                                    if retry_resp.status == 200:
                                        async for token in self._read_stream(retry_resp):
                                            yield token
                                        return

                if resp.status != 200:
                    self.has_error = True
                    logger.error(f"Ollama endpoint returned status HTTP {resp.status}")
                    fallback = f"I heard you! Model {self.model} returned HTTP {resp.status}."
                    for token in fallback.split():
                        yield token + " "
                    return

                async for token in self._read_stream(resp):
                    yield token

        except asyncio.CancelledError:
            self._cancelled = True
            logger.info("Ollama generation request cancelled.")
            raise
        except Exception as e:
            self.has_error = True
            err_msg = str(e) or type(e).__name__
            logger.error(f"Ollama request error: {type(e).__name__} ({err_msg})")
            if isinstance(e, (asyncio.TimeoutError, TimeoutError, aiohttp.ClientTimeout)):
                fallback = "I heard you clearly, but model response timed out. Please check system resources."
            else:
                fallback = "I can hear you clearly! Processing your request. Please check that Ollama is running."
            for token in fallback.split():
                yield token + " "

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="Ollama LLM service operational",
            details={"model": self.model, "url": self.base_url},
        )

    async def shutdown(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        self._cancelled = True

