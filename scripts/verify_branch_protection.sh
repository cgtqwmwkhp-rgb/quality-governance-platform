#!/bin/bash

# Operator Script for Branch Protection Verification

set -e

# --- Direct Push Rejection Test ---

echo "--- Running Direct Push Rejection Test ---"

# Create a temporary file and commit it
TEST_FILE="direct_push_test_$(date +%s).txt"
touch $TEST_FILE
git add $TEST_FILE
git commit -m "Test: direct push to main"

# Attempt to push directly to main (this should fail)
if git push origin main; then
    echo "❌ ERROR: Direct push to main succeeded. Branch protection is not configured correctly."
    exit 1
else
    echo "✅ SUCCESS: Direct push to main was rejected as expected."
fi

# Clean up the local commit
git reset --hard HEAD~1

# --- Blocked PR Test ---

echo "\n--- Running Blocked PR Test ---"

# Create a new branch
BRANCH_NAME="test/blocked-pr-$(date +%s)"
git checkout -b $BRANCH_NAME

# Create a temporary file and commit it
PR_TEST_FILE="blocked_pr_test_$(date +%s).txt"
touch $PR_TEST_FILE
git add $PR_TEST_FILE
git commit -m "Test: blocked PR"

# Push the new branch
git push origin $BRANCH_NAME

# Open a pull request (requires GitHub CLI)
if ! command -v gh &> /dev/null
then
    echo "⚠️ GitHub CLI (gh) not found. Please open the pull request manually."
else
    gh pr create --title "Test: Blocked PR" --body "This PR should be blocked from merging." --base main --head $BRANCH_NAME
fi

echo "\n✅ SUCCESS: Blocked PR test branch created and pushed."
echo "Please navigate to the pull request in your browser and capture a screenshot showing that the merge is blocked."

# Clean up the local branch
git checkout main
git branch -D $BRANCH_NAME
