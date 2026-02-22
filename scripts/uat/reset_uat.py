#!/usr/bin/env python3
"""
UAT Reset Script

Single command to reset UAT environment to known state:
1. Verify staging environment (fail-fast on production)
2. Clear UAT data only (preserves non-UAT data)
3. Re-seed with deterministic data
4. Output manifest with counts and key IDs

SAFETY:
- Only runs when APP_ENV=staging AND UAT_ENABLED=true
- Refuses to run in production (exits with error)
- All UAT data is prefixed with 'UAT' for easy identification
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from seed_data import (
    check_environment_safety,
    UATSeedGenerator,
    print_manifest,
)


class UATResetManager:
    """
    Manages UAT environment reset operations.

    Safety-first design:
    - Environment checks before any operation
    - Only touches UAT-prefixed data
    - Generates audit trail (manifest)
    """

    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.environ.get("DATABASE_URL")
        self.manifest_dir = Path("docs/uat")
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

    def verify_staging(self) -> bool:
        """Verify we are in staging environment."""
        return check_environment_safety()

    def clear_uat_data(self, dry_run: bool = False) -> Dict[str, int]:
        """
        Clear UAT data from staging database.
        Only clears records with UAT prefixes.

        Returns counts of cleared records.
        """
        print()
        print("=" * 70)
        print("CLEARING UAT DATA")
        print("=" * 70)

        # In a real implementation, this would connect to the database
        # and delete records with UAT prefixes

        cleared = {
            "users": 0,
            "incidents": 0,
            "audits": 0,
            "audit_templates": 0,
            "risks": 0,
            "standards": 0,
            "controls": 0,
            "evidence": 0,
        }

        if dry_run:
            print("DRY RUN: Would clear the following tables:")
            print("  - users WHERE username LIKE 'uat_%'")
            print("  - incidents WHERE reference_number LIKE 'INC-UAT-%'")
            print("  - audits WHERE reference_number LIKE 'AUD-UAT-%'")
            print("  - risks WHERE reference_number LIKE 'RISK-UAT-%'")
            print("  - standards WHERE code LIKE '%-UAT'")
            print("  - controls WHERE code LIKE '%UAT%'")
            print("  - evidence (linked to UAT controls)")
            return cleared

        # Placeholder for actual database operations
        # In real implementation:
        #
        # async with get_db_session() as session:
        #     # Clear in reverse order of dependencies
        #     result = await session.execute(
        #         delete(Evidence).where(Evidence.control_id.in_(
        #             select(Control.id).where(Control.code.like('%UAT%'))
        #         ))
        #     )
        #     cleared['evidence'] = result.rowcount
        #
        #     # ... continue for other tables
        #     await session.commit()

        print("✅ UAT data cleared (placeholder - implement DB connection)")
        return cleared

    def seed_uat_data(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Seed UAT data to staging database.

        Returns the seed manifest.
        """
        print()
        print("=" * 70)
        print("SEEDING UAT DATA")
        print("=" * 70)

        generator = UATSeedGenerator()
        manifest = generator.generate_all()

        if dry_run:
            print("DRY RUN: Would seed the following:")
            for key, count in manifest.counts.items():
                print(f"  - {key}: {count} records")
            return manifest

        # Placeholder for actual database operations
        # In real implementation:
        #
        # async with get_db_session() as session:
        #     for user_data in manifest.users:
        #         user = User(**user_data)
        #         session.add(user)
        #
        #     # ... continue for other entities
        #     await session.commit()

        print("✅ UAT data seeded (placeholder - implement DB connection)")
        return manifest

    def save_manifest(self, manifest: Dict[str, Any], operation: str) -> Path:
        """Save manifest to file for audit trail."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"uat_manifest_{operation}_{timestamp}.json"
        filepath = self.manifest_dir / filename

        with open(filepath, "w") as f:
            json.dump(manifest if isinstance(manifest, dict) else manifest.__dict__, f, indent=2, default=str)

        return filepath

    def run_reset(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute full UAT reset operation.

        Steps:
        1. Verify staging environment
        2. Clear existing UAT data
        3. Seed fresh UAT data
        4. Generate and save manifest
        5. Return summary
        """
        results = {
            "success": False,
            "environment": os.environ.get("APP_ENV", "unknown"),
            "dry_run": dry_run,
            "timestamp": datetime.now().isoformat(),
            "cleared": {},
            "seeded": {},
            "manifest_path": None,
            "errors": [],
        }

        try:
            # Step 1: Verify environment
            print()
            print("=" * 70)
            print("UAT RESET OPERATION")
            print("=" * 70)
            print(f"Environment: {results['environment']}")
            print(f"Dry Run: {dry_run}")
            print(f"Timestamp: {results['timestamp']}")

            if not dry_run:
                self.verify_staging()
            else:
                print("⚠️  Skipping environment check for dry run")

            # Step 2: Clear existing data
            results["cleared"] = self.clear_uat_data(dry_run)

            # Step 3: Seed fresh data
            manifest = self.seed_uat_data(dry_run)
            results["seeded"] = manifest.counts if hasattr(manifest, "counts") else manifest.get("counts", {})

            # Step 4: Save manifest
            manifest_path = self.save_manifest(manifest, "reset")
            results["manifest_path"] = str(manifest_path)

            # Step 5: Print summary
            print()
            print("=" * 70)
            print("UAT RESET COMPLETE")
            print("=" * 70)
            print(f"Manifest saved to: {manifest_path}")
            print()
            print("Seeded counts:")
            for key, count in results["seeded"].items():
                print(f"  {key}: {count}")

            results["success"] = True

        except SystemExit as e:
            results["errors"].append(f"Environment check failed with code {e.code}")
            raise
        except Exception as e:
            results["errors"].append(str(e))
            print(f"❌ Error during reset: {e}")
            raise

        return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Reset UAT environment to known state")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--output-dir", type=str, default="docs/uat", help="Directory for manifest output")

    args = parser.parse_args()

    # Confirmation prompt (unless --force or --dry-run)
    if not args.force and not args.dry_run:
        print()
        print("⚠️  WARNING: This will clear and reseed UAT data in staging")
        print()
        response = input("Are you sure you want to continue? [y/N]: ")
        if response.lower() != "y":
            print("Aborted.")
            sys.exit(0)

    # Run reset
    manager = UATResetManager()
    manager.manifest_dir = Path(args.output_dir)

    try:
        results = manager.run_reset(dry_run=args.dry_run)

        if results["success"]:
            print()
            print("✅ UAT reset completed successfully")
            sys.exit(0)
        else:
            print()
            print("❌ UAT reset failed")
            for error in results["errors"]:
                print(f"   - {error}")
            sys.exit(1)

    except SystemExit:
        raise
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
