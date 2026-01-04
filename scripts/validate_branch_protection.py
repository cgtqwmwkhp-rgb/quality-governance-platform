#!/usr/bin/env python3
"""
Branch Protection Validator

This script validates that the branch protection settings for the main branch
meet the required governance standards. It reads the exported settings from
docs/evidence/branch_protection_settings.json and checks required fields.

Exit codes:
- 0: All validations passed
- 1: One or more validations failed
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


class BranchProtectionValidator:
    """Validates branch protection settings against governance requirements."""

    def __init__(self, settings_file: Path):
        """Initialize the validator with the settings file path."""
        self.settings_file = settings_file
        self.settings: Dict[str, Any] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def load_settings(self) -> bool:
        """Load the branch protection settings from the JSON file."""
        if not self.settings_file.exists():
            self.errors.append(f"Settings file not found: {self.settings_file}")
            return False

        try:
            with open(self.settings_file, "r") as f:
                self.settings = json.load(f)
            return True
        except json.JSONDecodeError as e:
            self.errors.append(f"Failed to parse JSON: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Failed to read settings file: {e}")
            return False

    def validate_required_status_checks(self) -> bool:
        """Validate that required status checks are configured correctly."""
        status_checks = self.settings.get("required_status_checks")
        if not status_checks:
            self.errors.append("❌ required_status_checks is not configured")
            return False

        # Check that strict mode is enabled (branches must be up to date)
        if not status_checks.get("strict"):
            self.errors.append(
                "❌ required_status_checks.strict is not enabled "
                "(branches must be up to date before merging)"
            )
            return False

        # Check that "all-checks" is in the required contexts
        contexts = status_checks.get("contexts", [])
        if "all-checks" not in contexts:
            self.errors.append(
                f"❌ required_status_checks.contexts does not include 'all-checks' "
                f"(found: {contexts})"
            )
            return False

        # Ensure only "all-checks" is required (no other checks)
        if contexts != ["all-checks"]:
            self.warnings.append(
                f"⚠️  required_status_checks.contexts includes additional checks: {contexts}"
            )

        return True

    def validate_required_pull_request_reviews(self) -> bool:
        """Validate that pull request reviews are required."""
        pr_reviews = self.settings.get("required_pull_request_reviews")
        if not pr_reviews:
            self.errors.append("❌ required_pull_request_reviews is not configured")
            return False

        # Check that at least 1 approval is required
        required_count = pr_reviews.get("required_approving_review_count", 0)
        if required_count < 1:
            self.errors.append(
                f"❌ required_pull_request_reviews.required_approving_review_count "
                f"is {required_count}, must be >= 1"
            )
            return False

        return True

    def validate_enforce_admins(self) -> bool:
        """Validate that administrator bypass is disabled."""
        enforce_admins = self.settings.get("enforce_admins")
        if not enforce_admins:
            self.errors.append("❌ enforce_admins is not configured")
            return False

        if not enforce_admins.get("enabled"):
            self.errors.append(
                "❌ enforce_admins.enabled is false "
                "(administrators can bypass branch protection)"
            )
            return False

        return True

    def validate_required_linear_history(self) -> bool:
        """Validate that linear history is required."""
        linear_history = self.settings.get("required_linear_history")
        if not linear_history:
            self.warnings.append(
                "⚠️  required_linear_history is not configured (merge commits allowed)"
            )
            return True

        if not linear_history.get("enabled"):
            self.warnings.append(
                "⚠️  required_linear_history.enabled is false (merge commits allowed)"
            )

        return True

    def validate_force_pushes_disabled(self) -> bool:
        """Validate that force pushes are disabled."""
        allow_force_pushes = self.settings.get("allow_force_pushes")
        if not allow_force_pushes:
            self.errors.append("❌ allow_force_pushes is not configured")
            return False

        if allow_force_pushes.get("enabled"):
            self.errors.append("❌ allow_force_pushes.enabled is true (force pushes are allowed)")
            return False

        return True

    def validate_deletions_disabled(self) -> bool:
        """Validate that branch deletions are disabled."""
        allow_deletions = self.settings.get("allow_deletions")
        if not allow_deletions:
            self.errors.append("❌ allow_deletions is not configured")
            return False

        if allow_deletions.get("enabled"):
            self.errors.append("❌ allow_deletions.enabled is true (branch deletions are allowed)")
            return False

        return True

    def validate(self) -> bool:
        """Run all validations and return True if all pass."""
        validations = [
            ("Required Status Checks", self.validate_required_status_checks),
            ("Required Pull Request Reviews", self.validate_required_pull_request_reviews),
            ("Enforce Admins", self.validate_enforce_admins),
            ("Required Linear History", self.validate_required_linear_history),
            ("Force Pushes Disabled", self.validate_force_pushes_disabled),
            ("Deletions Disabled", self.validate_deletions_disabled),
        ]

        all_passed = True
        for name, validation_func in validations:
            if not validation_func():
                all_passed = False

        return all_passed

    def print_report(self) -> None:
        """Print the validation report."""
        print("=" * 80)
        print("BRANCH PROTECTION VALIDATION REPORT")
        print("=" * 80)
        print(f"Settings file: {self.settings_file}")
        print()

        if self.errors:
            print("ERRORS:")
            for error in self.errors:
                print(f"  {error}")
            print()

        if self.warnings:
            print("WARNINGS:")
            for warning in self.warnings:
                print(f"  {warning}")
            print()

        if not self.errors and not self.warnings:
            print("✅ All validations passed")
            print()
            print("Branch protection settings meet all governance requirements:")
            print("  ✅ Required status check 'all-checks' is enforced")
            print("  ✅ Pull request reviews are required (>= 1 approval)")
            print("  ✅ Administrators cannot bypass branch protection")
            print("  ✅ Force pushes are disabled")
            print("  ✅ Branch deletions are disabled")
        elif not self.errors:
            print("✅ All critical validations passed (warnings present)")
        else:
            print("❌ Validation failed")

        print()
        print("=" * 80)


def main():
    """Main entry point."""
    repo_root = Path(__file__).parent.parent
    settings_file = repo_root / "docs" / "evidence" / "branch_protection_settings.json"

    validator = BranchProtectionValidator(settings_file)

    if not validator.load_settings():
        validator.print_report()
        sys.exit(1)

    if validator.validate():
        validator.print_report()
        sys.exit(0)
    else:
        validator.print_report()
        sys.exit(1)


if __name__ == "__main__":
    main()
