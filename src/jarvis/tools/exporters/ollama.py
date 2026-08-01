"""
Ollama JSON tool schema exporter.
"""

from typing import Any, Dict, List
from jarvis.tools.exporters.base import BaseSchemaExporter
from jarvis.tools.schemas import ToolSpec


class OllamaSchemaExporter(BaseSchemaExporter):
    """Exports list of ToolSpec objects into Ollama tool calling format."""

    def export(self, specs: List[ToolSpec]) -> List[Dict[str, Any]]:
        tools = []
        for spec in specs:
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": spec.parameters_schema or {
                            "type": "object",
                            "properties": {},
                        },
                    },
                }
            )
        return tools
