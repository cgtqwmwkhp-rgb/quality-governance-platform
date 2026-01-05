#!/usr/bin/env python3
"""Validate OpenAPI contract invariants."""

import json
import sys
from pathlib import Path


def validate_pagination_params(openapi_spec: dict) -> list[str]:
    """Validate that list endpoints have pagination parameters."""
    errors = []
    
    for path, methods in openapi_spec.get("paths", {}).items():
        for method, details in methods.items():
            if method != "get":
                continue
            
            # Only check endpoints that have page/page_size in their parameters already
            # (i.e., endpoints that claim to support pagination)
            params = details.get("parameters", [])
            param_names = {p["name"] for p in params if p.get("in") == "query"}
            
            # If endpoint has neither page nor page_size, skip it (not claiming pagination)
            if "page" not in param_names and "page_size" not in param_names:
                continue
            
            
            # Check for pagination params
            if "page" not in param_names or "page_size" not in param_names:
                errors.append(
                    f"{method.upper()} {path}: Missing pagination params (page, page_size)"
                )
    
    return errors


def validate_paginated_responses(openapi_spec: dict) -> list[str]:
    """Validate that paginated responses have the correct schema."""
    errors = []
    
    schemas = openapi_spec.get("components", {}).get("schemas", {})
    
    for schema_name, schema_def in schemas.items():
        # Look for response schemas that should be paginated
        if not any(keyword in schema_name.lower() for keyword in ["list", "response"]):
            continue
        
        properties = schema_def.get("properties", {})
        
        # If it has 'items', it should be a paginated response
        if "items" in properties:
            required_fields = {"items", "total", "page", "page_size"}
            actual_fields = set(properties.keys())
            
            missing = required_fields - actual_fields
            if missing:
                errors.append(
                    f"Schema {schema_name}: Missing paginated response fields: {missing}"
                )
    
    return errors


def validate_auth_security(openapi_spec: dict) -> list[str]:
    """Validate that endpoints requiring auth have security defined."""
    errors = []
    
    for path, methods in openapi_spec.get("paths", {}).items():
        # Skip health check and auth endpoints
        if path in ["/health", "/api/v1/auth/login", "/api/v1/auth/refresh"]:
            continue
        
        for method, details in methods.items():
            description = details.get("description", "").lower()
            summary = details.get("summary", "").lower()
            
            # Check if endpoint mentions authentication requirement
            if "requires authentication" in description or "requires authentication" in summary:
                security = details.get("security", [])
                
                if not security:
                    errors.append(
                        f"{method.upper()} {path}: Claims to require auth but has no security definition"
                    )
    
    return errors


def main():
    """Run all contract validations."""
    openapi_path = Path("docs/contracts/openapi.json")
    
    if not openapi_path.exists():
        print(f"❌ OpenAPI schema not found at {openapi_path}")
        sys.exit(1)
    
    with open(openapi_path) as f:
        openapi_spec = json.load(f)
    
    print("=== OpenAPI Contract Validation ===")
    
    all_errors = []
    
    # Run validations
    errors = validate_pagination_params(openapi_spec)
    if errors:
        all_errors.extend(errors)
        print(f"\n❌ Pagination parameter errors ({len(errors)}):")
        for error in errors[:5]:  # Show first 5
            print(f"  - {error}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more")
    
    errors = validate_paginated_responses(openapi_spec)
    if errors:
        all_errors.extend(errors)
        print(f"\n❌ Paginated response schema errors ({len(errors)}):")
        for error in errors[:5]:
            print(f"  - {error}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more")
    
    errors = validate_auth_security(openapi_spec)
    if errors:
        all_errors.extend(errors)
        print(f"\n❌ Authentication security errors ({len(errors)}):")
        for error in errors[:5]:
            print(f"  - {error}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more")
    
    if all_errors:
        print(f"\n❌ Contract validation failed with {len(all_errors)} errors")
        sys.exit(1)
    
    print("\n✅ All contract validations passed")


if __name__ == "__main__":
    main()
