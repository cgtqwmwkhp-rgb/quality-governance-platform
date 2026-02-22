#!/usr/bin/env python3
"""
UAT Seed Data Manager

Provides deterministic seed data for UAT testing with:
- Stable UUIDs (deterministic from seed)
- Test users (admin + regular)
- Sample domain objects (incidents, audits, risks, standards, controls)
- No PII - all synthetic test data

SAFETY: Only runs when APP_ENV=staging AND UAT_ENABLED=true
"""

import hashlib
import json
import os
import sys
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


# =============================================================================
# SAFETY CHECKS - FAIL FAST IF NOT STAGING
# =============================================================================


def check_environment_safety() -> bool:
    """
    Verify we are in staging environment with UAT explicitly enabled.
    Returns True if safe to proceed, exits with error otherwise.
    """
    app_env = os.environ.get("APP_ENV", "").lower()
    uat_enabled = os.environ.get("UAT_ENABLED", "").lower()

    errors = []

    if app_env == "production":
        errors.append("❌ FATAL: APP_ENV=production - UAT seed REFUSED")
        errors.append("   UAT seed data must NEVER run in production")

    if app_env != "staging":
        errors.append(f"❌ FATAL: APP_ENV={app_env or 'unset'} - must be 'staging'")

    if uat_enabled != "true":
        errors.append(f"❌ FATAL: UAT_ENABLED={uat_enabled or 'unset'} - must be 'true'")

    if errors:
        print("=" * 70)
        print("UAT SEED SAFETY CHECK FAILED")
        print("=" * 70)
        for error in errors:
            print(error)
        print()
        print("To run UAT seed, set:")
        print("  export APP_ENV=staging")
        print("  export UAT_ENABLED=true")
        print("=" * 70)
        sys.exit(1)

    return True


def generate_deterministic_uuid(seed: str, index: int) -> str:
    """Generate a deterministic UUID from a seed string and index."""
    combined = f"{seed}-{index}"
    hash_bytes = hashlib.sha256(combined.encode()).digest()[:16]
    # Set version 4 bits
    hash_bytes = bytearray(hash_bytes)
    hash_bytes[6] = (hash_bytes[6] & 0x0F) | 0x40
    hash_bytes[8] = (hash_bytes[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(hash_bytes)))


# =============================================================================
# SEED DATA DEFINITIONS - NO PII
# =============================================================================


@dataclass
class UATUser:
    """Test user with deterministic ID."""

    id: str
    username: str
    email: str
    role: str
    display_name: str
    is_active: bool = True


@dataclass
class UATIncident:
    """Test incident with deterministic ID."""

    id: str
    reference_number: str
    title: str
    description: str
    severity: str
    status: str
    reported_by_id: str
    assigned_to_id: Optional[str]
    created_at: str
    updated_at: str


@dataclass
class UATAuditTemplate:
    """Test audit template."""

    id: str
    name: str
    description: str
    category: str
    is_active: bool = True


@dataclass
class UATAudit:
    """Test audit with deterministic ID."""

    id: str
    reference_number: str
    template_id: str
    title: str
    status: str
    scheduled_date: str
    completed_date: Optional[str]
    auditor_id: str
    created_at: str


@dataclass
class UATRisk:
    """Test risk with deterministic ID."""

    id: str
    reference_number: str
    title: str
    description: str
    likelihood: int
    impact: int
    risk_score: int
    status: str
    owner_id: str
    created_at: str


@dataclass
class UATStandard:
    """Test compliance standard."""

    id: str
    code: str
    name: str
    description: str
    version: str
    is_active: bool = True


@dataclass
class UATControl:
    """Test compliance control."""

    id: str
    standard_id: str
    code: str
    name: str
    description: str
    control_type: str


@dataclass
class UATEvidence:
    """Test compliance evidence."""

    id: str
    control_id: str
    title: str
    description: str
    evidence_type: str
    uploaded_by_id: str
    created_at: str


@dataclass
class UATSeedManifest:
    """Manifest of all seeded data for verification."""

    seed_version: str
    seed_date: str
    environment: str
    users: List[Dict[str, Any]]
    incidents: List[Dict[str, Any]]
    audit_templates: List[Dict[str, Any]]
    audits: List[Dict[str, Any]]
    risks: List[Dict[str, Any]]
    standards: List[Dict[str, Any]]
    controls: List[Dict[str, Any]]
    evidence: List[Dict[str, Any]]
    counts: Dict[str, int]


class UATSeedGenerator:
    """
    Generates deterministic UAT seed data.
    All IDs are stable across runs when using the same seed.
    """

    SEED_VERSION = "1.0.0"
    BASE_SEED = "uat-seed-2026"

    def __init__(self):
        self.users: List[UATUser] = []
        self.incidents: List[UATIncident] = []
        self.audit_templates: List[UATAuditTemplate] = []
        self.audits: List[UATAudit] = []
        self.risks: List[UATRisk] = []
        self.standards: List[UATStandard] = []
        self.controls: List[UATControl] = []
        self.evidence: List[UATEvidence] = []

    def _uuid(self, category: str, index: int) -> str:
        """Generate deterministic UUID for a category and index."""
        return generate_deterministic_uuid(f"{self.BASE_SEED}-{category}", index)

    def _date(self, days_ago: int = 0) -> str:
        """Generate ISO date string."""
        return (datetime.now() - timedelta(days=days_ago)).isoformat()

    def generate_users(self) -> List[UATUser]:
        """Generate test users - admin and regular roles."""
        self.users = [
            UATUser(
                id=self._uuid("user", 1),
                username="uat_admin",
                email="uat-admin@test.local",
                role="admin",
                display_name="UAT Admin User",
            ),
            UATUser(
                id=self._uuid("user", 2),
                username="uat_user",
                email="uat-user@test.local",
                role="user",
                display_name="UAT Regular User",
            ),
            UATUser(
                id=self._uuid("user", 3),
                username="uat_auditor",
                email="uat-auditor@test.local",
                role="auditor",
                display_name="UAT Auditor User",
            ),
            UATUser(
                id=self._uuid("user", 4),
                username="uat_readonly",
                email="uat-readonly@test.local",
                role="readonly",
                display_name="UAT Read-Only User",
            ),
        ]
        return self.users

    def generate_incidents(self) -> List[UATIncident]:
        """Generate test incidents for lifecycle testing."""
        admin_id = self._uuid("user", 1)
        user_id = self._uuid("user", 2)

        self.incidents = [
            UATIncident(
                id=self._uuid("incident", 1),
                reference_number="INC-UAT-001",
                title="UAT Test Incident - Open",
                description="Test incident for UAT workflow - currently open status",
                severity="medium",
                status="open",
                reported_by_id=user_id,
                assigned_to_id=admin_id,
                created_at=self._date(5),
                updated_at=self._date(5),
            ),
            UATIncident(
                id=self._uuid("incident", 2),
                reference_number="INC-UAT-002",
                title="UAT Test Incident - In Progress",
                description="Test incident for UAT workflow - in progress",
                severity="high",
                status="in_progress",
                reported_by_id=user_id,
                assigned_to_id=admin_id,
                created_at=self._date(10),
                updated_at=self._date(3),
            ),
            UATIncident(
                id=self._uuid("incident", 3),
                reference_number="INC-UAT-003",
                title="UAT Test Incident - Closed",
                description="Test incident for UAT workflow - closed for reference",
                severity="low",
                status="closed",
                reported_by_id=admin_id,
                assigned_to_id=None,
                created_at=self._date(30),
                updated_at=self._date(25),
            ),
        ]
        return self.incidents

    def generate_audit_templates(self) -> List[UATAuditTemplate]:
        """Generate audit templates."""
        self.audit_templates = [
            UATAuditTemplate(
                id=self._uuid("audit_template", 1),
                name="Annual Compliance Review",
                description="Standard annual compliance review template",
                category="compliance",
            ),
            UATAuditTemplate(
                id=self._uuid("audit_template", 2),
                name="Security Assessment",
                description="Security controls assessment template",
                category="security",
            ),
            UATAuditTemplate(
                id=self._uuid("audit_template", 3),
                name="Process Audit",
                description="Business process audit template",
                category="operations",
            ),
        ]
        return self.audit_templates

    def generate_audits(self) -> List[UATAudit]:
        """Generate test audits for lifecycle testing."""
        auditor_id = self._uuid("user", 3)

        self.audits = [
            UATAudit(
                id=self._uuid("audit", 1),
                reference_number="AUD-UAT-001",
                template_id=self._uuid("audit_template", 1),
                title="Q1 Compliance Audit",
                status="scheduled",
                scheduled_date=self._date(-7),  # 7 days in future
                completed_date=None,
                auditor_id=auditor_id,
                created_at=self._date(14),
            ),
            UATAudit(
                id=self._uuid("audit", 2),
                reference_number="AUD-UAT-002",
                template_id=self._uuid("audit_template", 2),
                title="Security Assessment 2026",
                status="in_progress",
                scheduled_date=self._date(5),
                completed_date=None,
                auditor_id=auditor_id,
                created_at=self._date(30),
            ),
            UATAudit(
                id=self._uuid("audit", 3),
                reference_number="AUD-UAT-003",
                template_id=self._uuid("audit_template", 3),
                title="Process Audit - Completed",
                status="completed",
                scheduled_date=self._date(60),
                completed_date=self._date(55),
                auditor_id=auditor_id,
                created_at=self._date(90),
            ),
        ]
        return self.audits

    def generate_risks(self) -> List[UATRisk]:
        """Generate test risks for workflow testing."""
        admin_id = self._uuid("user", 1)

        self.risks = [
            UATRisk(
                id=self._uuid("risk", 1),
                reference_number="RISK-UAT-001",
                title="UAT Data Security Risk",
                description="Test risk for UAT - data security category",
                likelihood=3,
                impact=4,
                risk_score=12,
                status="open",
                owner_id=admin_id,
                created_at=self._date(20),
            ),
            UATRisk(
                id=self._uuid("risk", 2),
                reference_number="RISK-UAT-002",
                title="UAT Operational Risk",
                description="Test risk for UAT - operational category",
                likelihood=2,
                impact=3,
                risk_score=6,
                status="mitigated",
                owner_id=admin_id,
                created_at=self._date(45),
            ),
            UATRisk(
                id=self._uuid("risk", 3),
                reference_number="RISK-UAT-003",
                title="UAT Compliance Risk",
                description="Test risk for UAT - compliance category",
                likelihood=4,
                impact=5,
                risk_score=20,
                status="open",
                owner_id=admin_id,
                created_at=self._date(10),
            ),
        ]
        return self.risks

    def generate_standards(self) -> List[UATStandard]:
        """Generate compliance standards."""
        self.standards = [
            UATStandard(
                id=self._uuid("standard", 1),
                code="ISO-27001-UAT",
                name="ISO 27001 (UAT)",
                description="Information Security Management - UAT Version",
                version="2022",
            ),
            UATStandard(
                id=self._uuid("standard", 2),
                code="SOC2-UAT",
                name="SOC 2 Type II (UAT)",
                description="Service Organization Control 2 - UAT Version",
                version="2023",
            ),
        ]
        return self.standards

    def generate_controls(self) -> List[UATControl]:
        """Generate compliance controls linked to standards."""
        self.controls = [
            UATControl(
                id=self._uuid("control", 1),
                standard_id=self._uuid("standard", 1),
                code="ISO-A.5.1",
                name="Information Security Policies",
                description="Policies for information security",
                control_type="administrative",
            ),
            UATControl(
                id=self._uuid("control", 2),
                standard_id=self._uuid("standard", 1),
                code="ISO-A.9.1",
                name="Access Control Policy",
                description="Business requirements of access control",
                control_type="administrative",
            ),
            UATControl(
                id=self._uuid("control", 3),
                standard_id=self._uuid("standard", 2),
                code="SOC2-CC1.1",
                name="Control Environment",
                description="COSO control environment principle",
                control_type="administrative",
            ),
            UATControl(
                id=self._uuid("control", 4),
                standard_id=self._uuid("standard", 2),
                code="SOC2-CC6.1",
                name="Logical and Physical Access",
                description="Logical and physical access controls",
                control_type="technical",
            ),
        ]
        return self.controls

    def generate_evidence(self) -> List[UATEvidence]:
        """Generate compliance evidence."""
        admin_id = self._uuid("user", 1)

        self.evidence = [
            UATEvidence(
                id=self._uuid("evidence", 1),
                control_id=self._uuid("control", 1),
                title="Security Policy Document",
                description="Current information security policy",
                evidence_type="document",
                uploaded_by_id=admin_id,
                created_at=self._date(30),
            ),
            UATEvidence(
                id=self._uuid("evidence", 2),
                control_id=self._uuid("control", 2),
                title="Access Control Matrix",
                description="Role-based access control matrix",
                evidence_type="spreadsheet",
                uploaded_by_id=admin_id,
                created_at=self._date(15),
            ),
        ]
        return self.evidence

    def generate_all(self) -> UATSeedManifest:
        """Generate all seed data and return manifest."""
        self.generate_users()
        self.generate_incidents()
        self.generate_audit_templates()
        self.generate_audits()
        self.generate_risks()
        self.generate_standards()
        self.generate_controls()
        self.generate_evidence()

        return UATSeedManifest(
            seed_version=self.SEED_VERSION,
            seed_date=datetime.now().isoformat(),
            environment=os.environ.get("APP_ENV", "unknown"),
            users=[asdict(u) for u in self.users],
            incidents=[asdict(i) for i in self.incidents],
            audit_templates=[asdict(t) for t in self.audit_templates],
            audits=[asdict(a) for a in self.audits],
            risks=[asdict(r) for r in self.risks],
            standards=[asdict(s) for s in self.standards],
            controls=[asdict(c) for c in self.controls],
            evidence=[asdict(e) for e in self.evidence],
            counts={
                "users": len(self.users),
                "incidents": len(self.incidents),
                "audit_templates": len(self.audit_templates),
                "audits": len(self.audits),
                "risks": len(self.risks),
                "standards": len(self.standards),
                "controls": len(self.controls),
                "evidence": len(self.evidence),
            },
        )

    def get_user_credentials(self) -> Dict[str, Dict[str, str]]:
        """Get test user credentials (for test harness only)."""
        return {
            "admin": {"username": "uat_admin", "password": "UatTestPass123!", "role": "admin"},  # Test password only
            "user": {"username": "uat_user", "password": "UatTestPass123!", "role": "user"},
            "auditor": {"username": "uat_auditor", "password": "UatTestPass123!", "role": "auditor"},
            "readonly": {"username": "uat_readonly", "password": "UatTestPass123!", "role": "readonly"},
        }


def print_manifest(manifest: UATSeedManifest) -> None:
    """Print seed manifest summary."""
    print()
    print("=" * 70)
    print("UAT SEED MANIFEST")
    print("=" * 70)
    print(f"Version: {manifest.seed_version}")
    print(f"Date: {manifest.seed_date}")
    print(f"Environment: {manifest.environment}")
    print()
    print("Counts:")
    for key, count in manifest.counts.items():
        print(f"  {key}: {count}")
    print()
    print("Key IDs:")
    print(f"  Admin User: {manifest.users[0]['id']}")
    print(f"  Regular User: {manifest.users[1]['id']}")
    print(f"  First Incident: {manifest.incidents[0]['id']}")
    print(f"  First Audit: {manifest.audits[0]['id']}")
    print(f"  First Risk: {manifest.risks[0]['id']}")
    print("=" * 70)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="UAT Seed Data Generator")
    parser.add_argument(
        "--output", "-o", type=str, default="uat_seed_manifest.json", help="Output file for seed manifest"
    )
    parser.add_argument(
        "--skip-safety-check", action="store_true", help="Skip environment safety check (for local dev only)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Generate manifest without applying to database")

    args = parser.parse_args()

    # Safety check (unless explicitly skipped for local dev)
    if not args.skip_safety_check:
        check_environment_safety()
    else:
        print("⚠️  WARNING: Safety check skipped - for local development only")

    # Generate seed data
    generator = UATSeedGenerator()
    manifest = generator.generate_all()

    # Write manifest
    with open(args.output, "w") as f:
        json.dump(asdict(manifest), f, indent=2)

    print(f"✅ Seed manifest written to: {args.output}")
    print_manifest(manifest)

    if args.dry_run:
        print("ℹ️  DRY RUN: No database changes made")
    else:
        print("ℹ️  To apply to database, integrate with your ORM/migration system")


if __name__ == "__main__":
    main()
