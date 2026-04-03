#!/usr/bin/env python3
"""
OpenAPI Contract Validator

Enforces canonical error envelope contract in OpenAPI schema:
1. Error envelope schema component exists with {code, message, details, request_id}
2. 4xx responses reference the canonical error envelope via {"error": {...}}
3. $ref references are resolved before property checks
"""

import json
import sys
from pathlib import Path


def load_openapi_schema(path: Path) -> dict:
    """Load the OpenAPI schema from JSON file."""
    with open(path) as f:
        return json.load(f)


def resolve_ref(ref: str, schema: dict) -> dict:
    """Resolve a $ref like '#/components/schemas/Foo' against the full schema."""
    if not ref.startswith("#/"):
        return {}
    parts = ref.lstrip("#/").split("/")
    node = schema
    for part in parts:
        node = node.get(part, {})
        if not isinstance(node, dict):
            return {}
    return node


def _resolve_schema(obj: dict, root: dict) -> dict:
    """If *obj* is a $ref wrapper, resolve it; otherwise return as-is."""
    if "$ref" in obj:
        return resolve_ref(obj["$ref"], root)
    return obj


ENVELOPE_FIELDS = {"code", "message", "details", "request_id"}


def validate_error_envelope_schema(schema: dict) -> list[str]:
    """Validate that a canonical error envelope schema exists in components."""
    errors = []
    schemas = schema.get("components", {}).get("schemas", {})

    if not schemas:
        errors.append("No components.schemas found in OpenAPI spec")
        return errors

    found = False
    for name, defn in schemas.items():
        props = defn.get("properties", {})
        prop_names = set(props.keys())

        if ENVELOPE_FIELDS <= prop_names:
            found = True
            break

        if "error" in prop_names:
            inner = _resolve_schema(props["error"], schema)
            inner_props = set(inner.get("properties", {}).keys())
            if ENVELOPE_FIELDS <= inner_props:
                found = True
                break

    if not found:
        errors.append(
            "No error envelope schema found in components.schemas with "
            f"required fields {sorted(ENVELOPE_FIELDS)}"
        )

    return errors


def validate_error_responses(schema: dict) -> list[str]:
    """Validate that 4xx responses use the canonical error envelope."""
    errors = []
    paths = schema.get("paths", {})

    for path, methods in paths.items():
        for method, operation in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            responses = operation.get("responses", {})

            for status_code, response in responses.items():
                if not status_code.startswith("4"):
                    continue

                content = response.get("content", {})
                if "application/json" not in content:
                    errors.append(
                        f"{method.upper()} {path} - {status_code} response "
                        "missing application/json content"
                    )
                    continue

                response_schema = content["application/json"].get("schema", {})
                response_schema = _resolve_schema(response_schema, schema)

                properties = response_schema.get("properties", {})

                if "error" in properties:
                    inner = _resolve_schema(properties["error"], schema)
                    inner_props = set(inner.get("properties", {}).keys())

                    missing = ENVELOPE_FIELDS - inner_props
                    if missing:
                        errors.append(
                            f"{method.upper()} {path} - {status_code} "
                            f"error envelope missing fields: {sorted(missing)}"
                        )
                elif ENVELOPE_FIELDS <= set(properties.keys()):
                    pass
                else:
                    errors.append(
                        f"{method.upper()} {path} - {status_code} response "
                        "schema missing 'error' wrapper property"
                    )

    return errors


def main():
    """Run OpenAPI contract validation."""
    schema_path = Path("docs/contracts/openapi.json")

    if not schema_path.exists():
        print(f"❌ OpenAPI schema not found at {schema_path}")
        print("Run: python3 scripts/generate_openapi.py")
        sys.exit(1)

    schema = load_openapi_schema(schema_path)

    print("🔍 Validating OpenAPI contract...")

    schema_errors = validate_error_envelope_schema(schema)
    response_errors = validate_error_responses(schema)

    all_errors = schema_errors + response_errors

    if all_errors:
        print(f"\n❌ Found {len(all_errors)} contract violations:\n")
        for error in all_errors:
            print(f"  - {error}")
        sys.exit(1)

    print("✅ OpenAPI contract validation passed")
    print(f"   - Validated {len(schema.get('paths', {}))} paths")
    sys.exit(0)


if __name__ == "__main__":
    main()
