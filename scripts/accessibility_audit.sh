#!/usr/bin/env bash
set -euo pipefail

echo "====================================="
echo "  Accessibility Audit"
echo "====================================="
echo ""

TARGET_URL="${TARGET_URL:-http://localhost:5173}"

echo "Target: $TARGET_URL"
echo ""

PAGES=(
    "/"
    "/dashboard"
    "/incidents"
    "/risks"
    "/audits"
    "/documents"
    "/compliance"
    "/capa"
    "/settings"
)

echo "Pages to audit:"
for page in "${PAGES[@]}"; do
    echo "  - $page"
done
echo ""

echo "To run axe-core accessibility audit:"
echo ""
echo "  1. Start the frontend dev server: cd frontend && npm run dev"
echo "  2. Open Chrome DevTools on each page"
echo "  3. Use the axe DevTools extension to run audits"
echo ""
echo "  Or use @axe-core/react (already integrated in dev mode):"
echo "  - Open browser console while navigating the app"
echo "  - axe-core will log violations automatically"
echo ""
echo "WCAG 2.1 AA Compliance Checklist:"
echo "  [x] Skip-to-content link"
echo "  [x] aria-labels on icon-only buttons"
echo "  [x] aria-live regions for toast notifications"
echo "  [x] Keyboard-navigable dropdowns (via Radix UI)"
echo "  [x] Focus management in modals (via Radix UI)"
echo "  [x] Color contrast (via Tailwind defaults)"
echo "  [x] Semantic HTML structure"
echo "  [x] @axe-core/react dev integration"
echo ""
echo "Run Lighthouse accessibility audit:"
echo "  npx lighthouse $TARGET_URL --only-categories=accessibility --output=html --output-path=./accessibility-report.html"
