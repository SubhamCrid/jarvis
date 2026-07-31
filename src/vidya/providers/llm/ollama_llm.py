"""
Ollama Local LLM provider streaming token chunks via HTTP endpoint.
"""

import json
import asyncio
import logging
from typing import AsyncGenerator, Optional, List, Dict
import aiohttp
from vidya.core.base import ServiceStatus, HealthStatus
from vidya.providers.base import LLMProtocol

logger = logging.getLogger("vidya.providers.llm.ollama")


class OllamaLLM(LLMProtocol):
    """
    Local Ollama LLM provider. Streams tokens from http://localhost:11434 API.
    """

    def __init__(
        self,
        model: str = "llama3.2:3b",
        base_url: str = "http://localhost:11434",
        system_prompt: str = "You are Vidya, a helpful local voice assistant. Keep answers brief and conversational."
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.system_prompt = system_prompt
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._session: Optional[aiohttp.ClientSession] = None
        self._cancelled: bool = False

    async def initialize(self) -> bool:
        try:
            self._session = aiohttp.ClientSession()
            # Test connection to Ollama
            async with self._session.get(f"{self.base_url}/api/tags", timeout=2.0) as resp:
                if resp.status == 200:
                    self._status = ServiceStatus.RUNNING
                    logger.info(f"OllamaLLM connected to {self.base_url} with model {self.model}")
                    return True
        except Exception as e:
            logger.warning(f"Could not connect to Ollama at {self.base_url}: {e}. Degrading status.")
            self._status = ServiceStatus.DEGRADED
            return True
        return True

    async def generate_stream(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[str, None]:
        self._cancelled = False
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()

        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }

        try:
            async with self._session.post(f"{self.base_url}/api/chat", json=payload) as resp:
                if resp.status != 200:
                    logger.error(f"Ollama API returned HTTP {resp.status}")
                    return

                async for line in resp.content:
                    if self._cancelled:
                        logger.info("Ollama LLM generation stream cancelled.")
                        break

                    if not line:
                        continue

                    try:
                        data = json.loads(line.decode("utf-8"))
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if data.get("done", False):
                            break
                    except Exception as parse_err:
                        logger.warning(f"Error parsing Ollama stream chunk: {parse_err}")

        except asyncio.CancelledError:
            self._cancelled = True
            logger.info("Ollama LLM generation task cancelled.")
            raise
        except Exception as e:
            logger.error(f"Error streaming from Ollama: {e}")

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="Ollama LLM status",
            details={"model": self.model, "url": self.base_url}
        )

    async def shutdown(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        self._cancelled = True
