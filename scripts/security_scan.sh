#!/usr/bin/env bash
set -euo pipefail

echo "====================================="
echo "  Security Scan - Quality Governance"
echo "====================================="
echo ""

FAILED=0

echo "[1/4] Running pip-audit for dependency vulnerabilities..."
if pip-audit --strict 2>&1; then
    echo "  ✓ pip-audit passed"
else
    echo "  ✗ pip-audit found vulnerabilities"
    FAILED=1
fi
echo ""

echo "[2/4] Running safety check..."
if safety check --full-report 2>&1; then
    echo "  ✓ safety check passed"
else
    echo "  ✗ safety check found issues"
    FAILED=1
fi
echo ""

echo "[3/4] Running Bandit (high severity)..."
if bandit -r src/ -ll -q 2>&1; then
    echo "  ✓ Bandit passed (no high/critical issues)"
else
    echo "  ✗ Bandit found high-severity issues"
    FAILED=1
fi
echo ""

echo "[4/4] Checking for hardcoded secrets..."
SECRETS_FOUND=0
for pattern in "password\s*=" "secret\s*=" "api_key\s*=" "token\s*=.*['\"]" "AWS_SECRET"; do
    if rg -i "$pattern" src/ --type py -l 2>/dev/null | rg -v "test_|config\.py|security\.py|\.env" 2>/dev/null; then
        echo "  Warning: Potential hardcoded secret pattern '$pattern' found"
        SECRETS_FOUND=1
    fi
done
if [ "$SECRETS_FOUND" -eq 0 ]; then
    echo "  ✓ No obvious hardcoded secrets found"
fi
echo ""

echo "====================================="
if [ "$FAILED" -eq 0 ]; then
    echo "  All security checks PASSED"
    exit 0
else
    echo "  Some security checks FAILED"
    exit 1
fi
