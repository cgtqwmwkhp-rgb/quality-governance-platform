import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.main import app

def sort_dict(d):
    if isinstance(d, dict):
        return {k: sort_dict(v) for k, v in sorted(d.items())}
    if isinstance(d, list):
        return [sort_dict(i) for i in d]
    return d

def main():
    """Generate and save the OpenAPI schema."""
    schema = app.openapi()
    sorted_schema = sort_dict(schema)

    output_path = Path("docs/contracts/openapi.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(sorted_schema, f, indent=2)

    print(f"✅ OpenAPI schema generated at {output_path}")

if __name__ == "__main__":
    main()
