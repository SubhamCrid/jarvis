"""
Parameter validator enforcing strict input schema compliance before tool execution.
"""

from typing import Any, Dict
from jarvis.tools.schemas import ToolError, ToolSpec


class ValidationError(ValueError):
    """Raised when tool arguments fail parameter schema validation."""

    pass


class ToolValidator:
    """Validates raw argument dictionaries against a ToolSpec's Pydantic model or JSON schema."""

    @staticmethod
    def validate(spec: ToolSpec, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate input params. Returns clean validated parameters dictionary.
        Raises ValidationError if validation fails.
        """
        if spec.input_model:
            try:
                validated_obj = spec.input_model(**params)
                return validated_obj.model_dump()
            except Exception as err:
                raise ValidationError(f"Invalid parameters for tool '{spec.name}': {err}") from err

        # Basic JSON Schema required properties check if schema is provided
        schema = spec.parameters_schema
        if schema and isinstance(schema, dict):
            required = schema.get("required", [])
            for req_field in required:
                if req_field not in params:
                    raise ValidationError(f"Missing required parameter '{req_field}' for tool '{spec.name}'.")

        return params
