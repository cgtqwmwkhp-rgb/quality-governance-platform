#!/bin/bash
# Generate gate summary for CI artifacts (Stage 2.0 Phase 2)

set -e

OUTPUT_FILE="gate-summary.txt"

echo "================================================================================" > "$OUTPUT_FILE"
echo "CI Gate Summary (Stage 2.0)" >> "$OUTPUT_FILE"
echo "================================================================================" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

echo "Run Information:" >> "$OUTPUT_FILE"
echo "  Run ID: ${GITHUB_RUN_ID:-N/A}" >> "$OUTPUT_FILE"
echo "  Run Number: ${GITHUB_RUN_NUMBER:-N/A}" >> "$OUTPUT_FILE"
echo "  Commit SHA: ${GITHUB_SHA:-N/A}" >> "$OUTPUT_FILE"
echo "  Branch: ${GITHUB_REF_NAME:-N/A}" >> "$OUTPUT_FILE"
echo "  Workflow: ${GITHUB_WORKFLOW:-N/A}" >> "$OUTPUT_FILE"
echo "  Actor: ${GITHUB_ACTOR:-N/A}" >> "$OUTPUT_FILE"
echo "  Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

echo "================================================================================" >> "$OUTPUT_FILE"
echo "Gate Status Summary" >> "$OUTPUT_FILE"
echo "================================================================================" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "This file provides a summary of all CI gates for audit purposes." >> "$OUTPUT_FILE"
echo "For detailed logs, refer to the GitHub Actions run at:" >> "$OUTPUT_FILE"
echo "  https://github.com/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

echo "✅ Gate summary generated successfully"
cat "$OUTPUT_FILE"
