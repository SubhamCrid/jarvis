"""
XML System Prompt tool exporter optimized for small quantized local LLMs (3B / 7B).
"""

import json
from typing import List
from jarvis.tools.exporters.base import BaseSchemaExporter
from jarvis.tools.schemas import ToolSpec


class XMLPromptExporter(BaseSchemaExporter):
    """Formats ToolSpec definitions into compact XML instructions for system prompt injection."""

    def export(self, specs: List[ToolSpec]) -> str:
        if not specs:
            return ""

        lines = [
            "<available_tools>",
            "You have access to the following local tools. To call a tool, respond ONLY with a JSON block in format: ",
            '```json\n{"tool": "tool_name", "params": {...}}\n```\n',
        ]

        for spec in specs:
            params_str = json.dumps(spec.parameters_schema.get("properties", {}))
            lines.append(f"  <tool name=\"{spec.name}\">")
            lines.append(f"    <description>{spec.description}</description>")
            lines.append(f"    <parameters>{params_str}</parameters>")
            lines.append("  </tool>")

        lines.append("</available_tools>")
        return "\n".join(lines)
