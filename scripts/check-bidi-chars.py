#!/usr/bin/env python3
"""
Check for hidden/bidirectional Unicode characters in workflow files.

This script scans YAML files in .github/workflows/ for characters that could
be used in "Trojan Source" attacks (CVE-2021-42574, CVE-2021-42694).

Exit codes:
  0 - No bidi/hidden characters found
  1 - Bidi/hidden characters found (security risk)
"""

import sys
import os
from pathlib import Path

# Dangerous characters that are TRUE security risks (Trojan Source)
# CVE-2021-42574, CVE-2021-42694
DANGEROUS_CHARS = {
    # Zero-width characters
    0x200B: 'ZERO WIDTH SPACE',
    0x200C: 'ZERO WIDTH NON-JOINER',
    0x200D: 'ZERO WIDTH JOINER',
    0x200E: 'LEFT-TO-RIGHT MARK',
    0x200F: 'RIGHT-TO-LEFT MARK',
    # Bidirectional control characters
    0x202A: 'LEFT-TO-RIGHT EMBEDDING',
    0x202B: 'RIGHT-TO-LEFT EMBEDDING',
    0x202C: 'POP DIRECTIONAL FORMATTING',
    0x202D: 'LEFT-TO-RIGHT OVERRIDE',
    0x202E: 'RIGHT-TO-LEFT OVERRIDE',
    0x2066: 'LEFT-TO-RIGHT ISOLATE',
    0x2067: 'RIGHT-TO-LEFT ISOLATE',
    0x2068: 'FIRST STRONG ISOLATE',
    0x2069: 'POP DIRECTIONAL ISOLATE',
    # Special separators
    0x2028: 'LINE SEPARATOR',
    0x2029: 'PARAGRAPH SEPARATOR',
    # Invisible formatting
    0x2060: 'WORD JOINER',
    0x2061: 'FUNCTION APPLICATION',
    0x2062: 'INVISIBLE TIMES',
    0x2063: 'INVISIBLE SEPARATOR',
    0x2064: 'INVISIBLE PLUS',
    # BOM
    0xFEFF: 'BYTE ORDER MARK (BOM)',
}

# Variation selectors - GitHub flags these but they're harmless emoji markers
# These are NOT included in DANGEROUS_CHARS because they're not security risks
VARIATION_SELECTORS = {
    0xFE0F: 'VARIATION SELECTOR-16 (emoji)',
    0xFE0E: 'VARIATION SELECTOR-15 (text)',
}

# Combined for backward compatibility
BIDI_CHARS = DANGEROUS_CHARS
HIDDEN_CHARS = {**DANGEROUS_CHARS, **VARIATION_SELECTORS}


def check_file(filepath: Path) -> list:
    """Check a file for bidi/hidden characters."""
    findings = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"  [WARN]  Could not read {filepath}: {e}")
        return findings
    
    for i, char in enumerate(content):
        code = ord(char)
        if code in DANGEROUS_CHARS:
            line_num = content[:i].count('\n') + 1
            col = i - content.rfind('\n', 0, i)
            findings.append({
                'line': line_num,
                'col': col,
                'code': hex(code),
                'name': DANGEROUS_CHARS[code],
                'file': str(filepath)
            })
    
    return findings


def main():
    # Default to checking .github/workflows/
    workflow_dir = Path('.github/workflows')
    
    if not workflow_dir.exists():
        print(f"Directory {workflow_dir} not found.")
        sys.exit(0)
    
    all_findings = []
    files_checked = 0
    
    print("[CHECK] Checking workflow files for bidi/hidden Unicode characters...")
    print()
    
    for filepath in workflow_dir.glob('*.yml'):
        files_checked += 1
        findings = check_file(filepath)
        
        if findings:
            all_findings.extend(findings)
            print(f"[FAIL] {filepath}: {len(findings)} hidden character(s) found")
            for f in findings:
                print(f"   Line {f['line']}, Col {f['col']}: {f['code']} ({f['name']})")
        else:
            print(f"[OK] {filepath}: clean")
    
    for filepath in workflow_dir.glob('*.yaml'):
        files_checked += 1
        findings = check_file(filepath)
        
        if findings:
            all_findings.extend(findings)
            print(f"[FAIL] {filepath}: {len(findings)} hidden character(s) found")
            for f in findings:
                print(f"   Line {f['line']}, Col {f['col']}: {f['code']} ({f['name']})")
        else:
            print(f"[OK] {filepath}: clean")
    
    print()
    print(f"Files checked: {files_checked}")
    print(f"Findings: {len(all_findings)}")
    
    if all_findings:
        print()
        print("[BLOCK] SECURITY RISK: Hidden/bidirectional Unicode characters detected!")
        print("These characters can be used for 'Trojan Source' attacks.")
        print("Remove them before merging.")
        sys.exit(1)
    else:
        print()
        print("[OK] No hidden/bidirectional Unicode characters found.")
        sys.exit(0)


if __name__ == '__main__':
    main()
