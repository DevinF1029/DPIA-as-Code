"""Generate `schemas/dataflow.schema.json` from the Pydantic v2 models."""

from __future__ import annotations

from pathlib import Path

from dpia_as_code.loader import export_json_schema


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    target = repo_root / "schemas" / "dataflow.schema.json"
    export_json_schema(target)
    print(f"Exported JSON Schema to {target}")


if __name__ == "__main__":
    main()
