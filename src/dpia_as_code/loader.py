"""YAML loader, Pydantic validator, and JSON Schema generator for `dataflow.yaml`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from dpia_as_code.models.dataflow import DataFlowModel


class DataFlowValidationError(ValueError):
    """Raised when a `dataflow.yaml` file fails syntax or schema validation."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        self.errors = errors or []
        super().__init__(message)


def _format_pydantic_errors(exc: ValidationError) -> list[str]:
    formatted: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"]) if err["loc"] else "<root>"
        formatted.append(f"{loc}: {err['msg']}")
    return formatted


def parse_dataflow_yaml(raw_yaml: str, source_name: str = "<string>") -> DataFlowModel:
    """Parse and validate a raw YAML string into a `DataFlowModel`."""
    try:
        payload = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        raise DataFlowValidationError(
            f"Invalid YAML syntax in {source_name}: {exc}",
            errors=[str(exc)],
        ) from exc

    if not isinstance(payload, dict):
        raise DataFlowValidationError(
            f"Expected a YAML mapping at root of {source_name}, got {type(payload).__name__}.",
            errors=["Root document must be a YAML mapping/object."],
        )

    try:
        return DataFlowModel.model_validate(payload)
    except ValidationError as exc:
        details = _format_pydantic_errors(exc)
        bullet_list = "\n".join(f"  - {item}" for item in details)
        raise DataFlowValidationError(
            f"Schema validation failed for {source_name} ({len(details)} error(s)):\n{bullet_list}",
            errors=details,
        ) from exc


def load_dataflow(path: str | Path) -> DataFlowModel:
    """Load and validate a `dataflow.yaml` file from disk."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Dataflow file not found: {file_path}")
    content = file_path.read_text(encoding="utf-8")
    return parse_dataflow_yaml(content, source_name=str(file_path))


def export_json_schema(output_path: str | Path | None = None) -> dict[str, Any]:
    """Generate the JSON Schema (Draft 2020-12) for `dataflow.yaml`.

    If `output_path` is provided, writes formatted JSON to disk.
    """
    schema = DataFlowModel.model_json_schema()
    schema.pop("title", None)
    enriched: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://dpia-as-code.dev/schemas/v1.0/dataflow.schema.json",
        "title": "DPIA-as-Code DataFlow Specification (v1.0)",
        **schema,
    }
    if output_path is not None:
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(enriched, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return enriched
