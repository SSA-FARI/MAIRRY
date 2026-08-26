import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.validators import validator_for
from openapi_spec_validator import validate_spec

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = PROJECT_ROOT / "contracts"
EXAMPLES_PATH = CONTRACTS_DIR / "examples" / "contract-examples.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_json_schema(schema_path: Path) -> dict[str, Any]:
    schema = load_json(schema_path)
    validator_for(schema).check_schema(schema)
    print(f"validated schema: {schema_path.relative_to(PROJECT_ROOT)}")
    return schema


def validate_instances(schema: dict[str, Any], instances: list[dict[str, Any]], label: str) -> None:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for index, instance in enumerate(instances):
        validator.validate(instance)
        print(f"validated example: {label}[{index}]")


def validate_openapi_examples(
    openapi: dict[str, Any],
    examples: dict[str, list[dict[str, Any]]],
) -> None:
    schemas = openapi["components"]["schemas"]
    root_validator = Draft202012Validator(openapi, format_checker=FormatChecker())
    for schema_name, instances in examples.items():
        if schema_name not in schemas:
            raise KeyError(f"Unknown OpenAPI schema in examples: {schema_name}")
        for index, instance in enumerate(instances):
            errors = list(root_validator.evolve(schema=schemas[schema_name]).iter_errors(instance))
            if errors:
                raise errors[0]
            print(f"validated OpenAPI example: {schema_name}[{index}]")


def main() -> None:
    openapi_path = CONTRACTS_DIR / "openapi.yaml"
    openapi = yaml.safe_load(openapi_path.read_text(encoding="utf-8"))
    validate_spec(openapi)
    print(f"validated OpenAPI: {openapi_path.relative_to(PROJECT_ROOT)}")

    extraction_schema = validate_json_schema(CONTRACTS_DIR / "ai-extraction.schema.json")
    tool_result_schema = validate_json_schema(CONTRACTS_DIR / "tool-result.schema.json")
    examples = load_json(EXAMPLES_PATH)

    validate_instances(extraction_schema, examples["aiExtraction"], "aiExtraction")
    validate_instances(tool_result_schema, examples["toolResults"], "toolResults")
    validate_openapi_examples(openapi, examples["openapi"])


if __name__ == "__main__":
    main()
