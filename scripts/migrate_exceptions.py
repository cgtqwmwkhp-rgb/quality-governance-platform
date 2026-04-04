"""One-shot migration: replace raise HTTPException with DomainError subclasses."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional, Set, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
ROUTES = ROOT / "src" / "api" / "routes"

STATUS_MAP = {
    404: "NotFoundError",
    400: "BadRequestError",
    422: "ValidationError",
    403: "AuthorizationError",
    401: "AuthenticationError",
    409: "ConflictError",
}

SKIP_STATUS = {500, 503}

IMPORT_LINE_TEMPLATE = "from src.domain.exceptions import {classes}"


def extract_status_code(block: str) -> int | None:
    m = re.search(r"status_code\s*=\s*(?:status\.HTTP_)?(\d{3})", block)
    if m:
        return int(m.group(1))
    for pat in [
        r"status_code\s*=\s*status\.HTTP_(\d{3})_\w+",
        r"status_code\s*=\s*(\d{3})",
    ]:
        m = re.search(pat, block)
        if m:
            return int(m.group(1))
    return None


def find_raise_blocks(source: str) -> list[tuple[int, int, str]]:
    """Find all `raise HTTPException(...)` blocks with their char spans."""
    results = []
    pattern = re.compile(r"raise HTTPException\(")
    for m in pattern.finditer(source):
        start = m.start()
        # find matching closing paren
        depth = 0
        i = m.end() - 1  # position of '('
        for j in range(i, len(source)):
            if source[j] == '(':
                depth += 1
            elif source[j] == ')':
                depth -= 1
                if depth == 0:
                    end = j + 1
                    block = source[start:end]
                    results.append((start, end, block))
                    break
    return results


def extract_detail_message(block: str) -> str | None:
    """Extract the human-readable message from various detail patterns."""
    # Pattern 1: detail=api_error(ErrorCode.XXX, "message")
    m = re.search(r'api_error\(\s*ErrorCode\.\w+\s*,\s*"([^"]*)"', block)
    if m:
        return m.group(1)
    # Pattern 1b: api_error with single-quoted message
    m = re.search(r"api_error\(\s*ErrorCode\.\w+\s*,\s*'([^']*)'", block)
    if m:
        return m.group(1)
    # Pattern 1c: api_error with variable (supervisor_check["reason"] or ...)
    m = re.search(r'api_error\(\s*ErrorCode\.\w+\s*,\s*(.+?)(?:\s*\)|\s*,\s*details)', block, re.DOTALL)
    if m:
        val = m.group(1).strip().rstrip(',').strip()
        if not val.startswith('"') and not val.startswith("'") and not val.startswith("f\"") and not val.startswith("f'"):
            return None  # complex expression, handle separately
    return None


def extract_detail_string(block: str) -> str | None:
    """Extract detail when it's a plain string."""
    # detail="message"
    m = re.search(r'detail\s*=\s*"([^"]*)"', block)
    if m:
        return m.group(1)
    m = re.search(r"detail\s*=\s*'([^']*)'", block)
    if m:
        return m.group(1)
    # detail=f"message"
    m = re.search(r'detail\s*=\s*(f"[^"]*")', block)
    if m:
        return m.group(1)
    m = re.search(r"detail\s*=\s*(f'[^']*')", block)
    if m:
        return m.group(1)
    return None


def extract_detail_dict_message(block: str) -> tuple[str | None, str | None, str | None]:
    """For dict-style details, extract message, error_code, and details dict."""
    # "message": "..."
    msg_m = re.search(r'"message"\s*:\s*(?:f)?"([^"]*)"', block)
    if not msg_m:
        msg_m = re.search(r'"message"\s*:\s*(f"[^"]*")', block)
    
    code_m = re.search(r'"error_code"\s*:\s*"([^"]*)"', block)
    
    msg = None
    if msg_m:
        msg = msg_m.group(1) if msg_m.group(1) else msg_m.group(0)
    
    code = code_m.group(1) if code_m else None
    
    return msg, code, None


def extract_api_error_details(block: str) -> str | None:
    """Extract details={...} from api_error call."""
    m = re.search(r'details\s*=\s*\{', block)
    if not m:
        return None
    start = m.start() + len("details=")
    # find matching brace
    depth = 0
    for i in range(m.end() - 1, len(block)):
        if block[i] == '{':
            depth += 1
        elif block[i] == '}':
            depth -= 1
            if depth == 0:
                return block[start:i+1]
    return None


def build_replacement(status_code: int, block: str, indent: str) -> str | None:
    """Build the replacement raise statement."""
    if status_code in SKIP_STATUS:
        return None
    
    error_class = STATUS_MAP.get(status_code)
    if not error_class:
        return None
    
    # Try to extract message from various patterns
    
    # Pattern: api_error(ErrorCode.XXX, "message", details={...})
    api_error_match = re.search(r'api_error\(', block)
    if api_error_match:
        # Extract message
        # Could be: api_error(ErrorCode.XXX, "message")
        # Or: api_error(ErrorCode.XXX, "message", details={...})
        # Or: api_error(ErrorCode.XXX, expr or "fallback")
        
        # Find the message argument (second arg to api_error)
        # First, let's get everything inside api_error(...)
        ae_start = api_error_match.end()
        depth = 1
        ae_end = ae_start
        for i in range(ae_start, len(block)):
            if block[i] == '(':
                depth += 1
            elif block[i] == ')':
                depth -= 1
                if depth == 0:
                    ae_end = i
                    break
        
        api_error_content = block[ae_start:ae_end]
        
        # Split by comma, but respect nested structures
        # Find first comma after ErrorCode.XXX
        ec_match = re.search(r'ErrorCode\.\w+\s*,\s*', api_error_content)
        if ec_match:
            after_code = api_error_content[ec_match.end():]
            
            # Check for details= parameter
            details_str = extract_api_error_details(block)
            
            # Extract the message part (everything before details= or end)
            details_match = re.search(r',\s*details\s*=', after_code)
            if details_match:
                msg_part = after_code[:details_match.start()].strip()
            else:
                msg_part = after_code.strip().rstrip(',').strip()
            
            if details_str:
                return f'{indent}raise {error_class}({msg_part}, details={details_str})'
            else:
                return f'{indent}raise {error_class}({msg_part})'
    
    # Pattern: detail=str(e) from except ValueError
    str_e_match = re.search(r'detail\s*=\s*str\((\w+)\)', block)
    if str_e_match:
        var = str_e_match.group(1)
        return f'{indent}raise {error_class}(str({var}))'
    
    # Pattern: detail="plain string"
    plain_match = re.search(r'detail\s*=\s*("(?:[^"\\]|\\.)*")', block)
    if plain_match:
        msg = plain_match.group(1)
        return f'{indent}raise {error_class}({msg})'
    
    # Pattern: detail=f"formatted string"
    fstr_match = re.search(r'detail\s*=\s*(f"(?:[^"\\]|\\.)*")', block)
    if fstr_match:
        msg = fstr_match.group(1)
        return f'{indent}raise {error_class}({msg})'
    
    # Pattern: detail=f'formatted string'
    fstr_match2 = re.search(r"detail\s*=\s*(f'(?:[^'\\]|\\.)*')", block)
    if fstr_match2:
        msg = fstr_match2.group(1)
        return f'{indent}raise {error_class}({msg})'
    
    # Pattern: detail={dict}
    dict_match = re.search(r'detail\s*=\s*\{', block)
    if dict_match:
        msg, code, _ = extract_detail_dict_message(block)
        details_content = extract_api_error_details(block)  # won't work for this pattern
        
        # For dict-style, extract message
        # Try f-string message
        fmsg = re.search(r'"message"\s*:\s*(f"[^"]*")', block)
        if fmsg:
            msg_str = fmsg.group(1)
        elif msg:
            msg_str = f'"{msg}"'
        else:
            return None
        
        parts = [msg_str]
        if code:
            parts.append(f'code="{code}"')
        
        # Try to extract "details": {...}
        det_match = re.search(r'"details"\s*:\s*\{', block)
        if det_match:
            depth = 0
            det_start = det_match.end() - 1
            for i in range(det_start, len(block)):
                if block[i] == '{':
                    depth += 1
                elif block[i] == '}':
                    depth -= 1
                    if depth == 0:
                        details_dict = block[det_start:i+1]
                        parts.append(f'details={details_dict}')
                        break
        
        return f'{indent}raise {error_class}({", ".join(parts)})'
    
    # Pattern: detail=result (variable)
    var_match = re.search(r'detail\s*=\s*(\w+)', block)
    if var_match:
        var = var_match.group(1)
        return f'{indent}raise {error_class}(str({var}))'
    
    return None


def get_indent(source: str, pos: int) -> str:
    """Get the indentation at a given position."""
    line_start = source.rfind('\n', 0, pos) + 1
    indent = ""
    for c in source[line_start:pos]:
        if c in ' \t':
            indent += c
        else:
            break
    return indent


def process_file(filepath: Path) -> dict:
    """Process a single file, returns info about changes made."""
    source = filepath.read_text()
    original = source
    
    blocks = find_raise_blocks(source)
    if not blocks:
        return {"file": str(filepath.relative_to(ROOT)), "changes": 0, "classes": set()}
    
    classes_needed = set()
    replacements = []
    
    for start, end, block in blocks:
        status_code = extract_status_code(block)
        if status_code is None:
            continue
        if status_code in SKIP_STATUS:
            continue
        
        error_class = STATUS_MAP.get(status_code)
        if not error_class:
            continue
        
        indent = get_indent(source, start)
        replacement = build_replacement(status_code, block, indent)
        
        if replacement:
            replacements.append((start, end, replacement))
            classes_needed.add(error_class)
    
    if not replacements:
        return {"file": str(filepath.relative_to(ROOT)), "changes": 0, "classes": set()}
    
    # Apply replacements in reverse order to preserve positions
    for start, end, replacement in reversed(replacements):
        source = source[:start] + replacement + source[end:]
    
    # Add import if needed
    if classes_needed:
        # Check if import already exists
        existing_import = re.search(r'from src\.domain\.exceptions import (.+)', source)
        if existing_import:
            # Parse existing imports
            existing_classes = {c.strip() for c in existing_import.group(1).split(',')}
            all_classes = existing_classes | classes_needed
            sorted_classes = sorted(all_classes)
            new_import = f"from src.domain.exceptions import {', '.join(sorted_classes)}"
            source = source[:existing_import.start()] + new_import + source[existing_import.end():]
        else:
            sorted_classes = sorted(classes_needed)
            new_import = f"from src.domain.exceptions import {', '.join(sorted_classes)}"
            # Insert after the last "from src." or "from fastapi" import
            # Find a good insertion point
            last_src_import = None
            for m in re.finditer(r'^from src\..+$', source, re.MULTILINE):
                last_src_import = m
            
            if last_src_import:
                insert_pos = last_src_import.end()
                source = source[:insert_pos] + "\n" + new_import + source[insert_pos:]
            else:
                # Insert after fastapi imports
                last_fastapi = None
                for m in re.finditer(r'^from fastapi .+$', source, re.MULTILINE):
                    last_fastapi = m
                if last_fastapi:
                    insert_pos = last_fastapi.end()
                    source = source[:insert_pos] + "\n" + new_import + source[insert_pos:]
    
    # Check if HTTPException is still used
    remaining_http_exceptions = len(re.findall(r'raise HTTPException\(', source))
    http_exception_in_except = len(re.findall(r'except.*HTTPException', source))
    http_exception_other = len(re.findall(r'HTTPException', source)) - remaining_http_exceptions - http_exception_in_except
    
    if remaining_http_exceptions == 0 and http_exception_in_except == 0:
        # Remove HTTPException from import
        # Pattern: from fastapi import ..., HTTPException, ...
        source = re.sub(r'(from fastapi import .*)HTTPException,?\s*', lambda m: m.group(1), source)
        # Clean up trailing comma or double spaces
        source = re.sub(r',\s*$', '', source, flags=re.MULTILINE)
        source = re.sub(r'import\s+,', 'import ', source)
        source = re.sub(r',\s*,', ',', source)
        # Clean trailing comma before )
        source = re.sub(r',\s*\)', ')', source)
        # Clean "import ," 
        source = re.sub(r'import\s+,\s+', 'import ', source)
    
    filepath.write_text(source)
    
    return {
        "file": str(filepath.relative_to(ROOT)),
        "changes": len(replacements),
        "classes": classes_needed,
        "remaining_http": remaining_http_exceptions,
    }


def main():
    files = [
        "inductions.py",
        "assessments.py",
        "form_config.py",
        "evidence_assets.py",
        "users.py",
        "standards.py",
        "tenants.py",
        "document_control.py",
        "kri.py",
        "planet_mark.py",
        "rca_tools.py",
        "engineers.py",
        "drivers.py",
        "uvdb.py",
        "auditor_competence.py",
        "employee_portal.py",
        "vehicles.py",
        "signatures.py",
        "xml_import.py",
        "policy_acknowledgment.py",
    ]
    
    total_changes = 0
    for fname in files:
        filepath = ROUTES / fname
        if not filepath.exists():
            print(f"SKIP {fname}: file not found")
            continue
        result = process_file(filepath)
        total_changes += result["changes"]
        classes = ", ".join(sorted(result.get("classes", set()))) if result.get("classes") else "none"
        remaining = result.get("remaining_http", 0)
        print(f"{fname}: {result['changes']} changes, imports=[{classes}], remaining_http={remaining}")
    
    print(f"\nTotal: {total_changes} HTTPException raises migrated")


if __name__ == "__main__":
    main()
