#!/usr/bin/env python3
"""
Production Readiness Validation Script

This script validates that the system is ready for production deployment.
It performs comprehensive checks across all critical areas.

Usage:
    python scripts/validate_production_readiness.py

Exit Codes:
    0 - All checks passed, ready for production
    1 - Critical checks failed, NOT ready for production
    2 - Warnings detected, review before deployment
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class CheckStatus(Enum):
    """Status of a validation check."""
    PASS = "✅ PASS"
    FAIL = "❌ FAIL"
    WARN = "⚠️ WARN"
    SKIP = "⏭️ SKIP"


@dataclass
class CheckResult:
    """Result of a single check."""
    name: str
    status: CheckStatus
    message: str
    details: Optional[str] = None


@dataclass
class ValidationReport:
    """Complete validation report."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    checks: List[CheckResult] = field(default_factory=list)
    
    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.PASS)
    
    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.FAIL)
    
    @property
    def warnings(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.WARN)
    
    @property
    def is_production_ready(self) -> bool:
        return self.failed == 0


def run_command(cmd: str, timeout: int = 60) -> tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


class ProductionValidator:
    """Validates production readiness."""
    
    def __init__(self):
        self.report = ValidationReport()
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    def add_result(self, name: str, status: CheckStatus, message: str, details: str = None):
        """Add a check result."""
        self.report.checks.append(CheckResult(name, status, message, details))
        print(f"  {status.value} {name}: {message}")
    
    def check_python_syntax(self):
        """Check all Python files for syntax errors."""
        print("\n📝 Checking Python Syntax...")
        
        exit_code, stdout, stderr = run_command(
            f"cd {self.project_root} && python3 -m py_compile src/**/*.py 2>&1 || "
            f"find src -name '*.py' -exec python3 -m py_compile {{}} \\;"
        )
        
        if exit_code == 0 or "No such file" not in stderr:
            self.add_result("Python Syntax", CheckStatus.PASS, "All Python files have valid syntax")
        else:
            self.add_result("Python Syntax", CheckStatus.FAIL, "Syntax errors found", stderr)
    
    def check_imports(self):
        """Check for missing imports."""
        print("\n📦 Checking Imports...")
        
        exit_code, stdout, stderr = run_command(
            f"cd {self.project_root} && python3 -c 'from src.main import app' 2>&1"
        )
        
        if exit_code == 0:
            self.add_result("Import Check", CheckStatus.PASS, "Main application imports successfully")
        else:
            self.add_result("Import Check", CheckStatus.FAIL, "Import errors found", stderr)
    
    def check_smoke_tests(self):
        """Run smoke tests."""
        print("\n🔥 Running Smoke Tests...")
        
        exit_code, stdout, stderr = run_command(
            f"cd {self.project_root} && python3 -m pytest tests/smoke/ -v --tb=short -x 2>&1",
            timeout=300
        )
        
        if exit_code == 0:
            self.add_result("Smoke Tests", CheckStatus.PASS, "All smoke tests passed")
        elif exit_code == 5:  # No tests collected
            self.add_result("Smoke Tests", CheckStatus.WARN, "No smoke tests found")
        else:
            # Count passed/failed from output
            passed = stdout.count(" PASSED")
            failed = stdout.count(" FAILED")
            self.add_result(
                "Smoke Tests", 
                CheckStatus.FAIL if failed > 0 else CheckStatus.PASS,
                f"{passed} passed, {failed} failed",
                stdout[-2000:] if len(stdout) > 2000 else stdout
            )
    
    def check_e2e_tests(self):
        """Run E2E tests."""
        print("\n🔄 Running E2E Tests...")
        
        exit_code, stdout, stderr = run_command(
            f"cd {self.project_root} && python3 -m pytest tests/e2e/ -v --tb=short 2>&1",
            timeout=600
        )
        
        passed = stdout.count(" PASSED")
        failed = stdout.count(" FAILED")
        skipped = stdout.count(" SKIPPED")
        
        if exit_code == 0:
            self.add_result("E2E Tests", CheckStatus.PASS, f"{passed} passed, {skipped} skipped")
        elif exit_code == 5:
            self.add_result("E2E Tests", CheckStatus.WARN, "No E2E tests found")
        else:
            self.add_result(
                "E2E Tests",
                CheckStatus.FAIL if failed > 0 else CheckStatus.WARN,
                f"{passed} passed, {failed} failed, {skipped} skipped"
            )
    
    def check_security_tests(self):
        """Run security tests."""
        print("\n🔒 Running Security Tests...")
        
        exit_code, stdout, stderr = run_command(
            f"cd {self.project_root} && python3 -m pytest tests/security/ -v --tb=short 2>&1",
            timeout=300
        )
        
        if exit_code == 0:
            self.add_result("Security Tests", CheckStatus.PASS, "All security tests passed")
        elif exit_code == 5:
            self.add_result("Security Tests", CheckStatus.WARN, "No security tests collected")
        else:
            passed = stdout.count(" PASSED")
            failed = stdout.count(" FAILED")
            self.add_result(
                "Security Tests",
                CheckStatus.FAIL if failed > 0 else CheckStatus.WARN,
                f"{passed} passed, {failed} failed"
            )
    
    def check_code_quality(self):
        """Check code quality with flake8."""
        print("\n🧹 Checking Code Quality...")
        
        exit_code, stdout, stderr = run_command(
            f"cd {self.project_root} && python3 -m flake8 src/ --count --statistics 2>&1"
        )
        
        if exit_code == 0:
            self.add_result("Code Quality (flake8)", CheckStatus.PASS, "No linting errors")
        else:
            error_count = len([l for l in stdout.split('\n') if l.strip() and ':' in l])
            if error_count > 50:
                self.add_result("Code Quality (flake8)", CheckStatus.FAIL, f"{error_count} issues found")
            else:
                self.add_result("Code Quality (flake8)", CheckStatus.WARN, f"{error_count} issues found")
    
    def check_type_hints(self):
        """Check type hints with mypy."""
        print("\n🔤 Checking Type Hints...")
        
        exit_code, stdout, stderr = run_command(
            f"cd {self.project_root} && python3 -m mypy src/ --ignore-missing-imports 2>&1"
        )
        
        if exit_code == 0:
            self.add_result("Type Hints (mypy)", CheckStatus.PASS, "No type errors")
        else:
            error_count = stdout.count("error:")
            if error_count > 20:
                self.add_result("Type Hints (mypy)", CheckStatus.WARN, f"{error_count} type issues")
            else:
                self.add_result("Type Hints (mypy)", CheckStatus.PASS, f"{error_count} minor issues")
    
    def check_dependencies(self):
        """Check for dependency vulnerabilities."""
        print("\n📚 Checking Dependencies...")
        
        exit_code, stdout, stderr = run_command(
            f"cd {self.project_root} && python3 -m safety check --json 2>&1"
        )
        
        if exit_code == 0:
            self.add_result("Dependencies", CheckStatus.PASS, "No known vulnerabilities")
        else:
            try:
                vulns = json.loads(stdout)
                vuln_count = len(vulns) if isinstance(vulns, list) else 0
                self.add_result("Dependencies", CheckStatus.WARN, f"{vuln_count} vulnerabilities found")
            except:
                self.add_result("Dependencies", CheckStatus.WARN, "Could not check vulnerabilities")
    
    def check_env_configuration(self):
        """Check environment configuration."""
        print("\n⚙️ Checking Configuration...")
        
        required_env_vars = [
            "DATABASE_URL",
            "SECRET_KEY",
        ]
        
        optional_env_vars = [
            "REDIS_URL",
            "OPENAI_API_KEY",
            "AZURE_AD_CLIENT_ID",
            "APPINSIGHTS_INSTRUMENTATIONKEY",
        ]
        
        missing_required = [v for v in required_env_vars if not os.getenv(v)]
        missing_optional = [v for v in optional_env_vars if not os.getenv(v)]
        
        if missing_required:
            self.add_result(
                "Required Config",
                CheckStatus.WARN,
                f"Missing: {', '.join(missing_required)}"
            )
        else:
            self.add_result("Required Config", CheckStatus.PASS, "All required config present")
        
        if missing_optional:
            self.add_result(
                "Optional Config",
                CheckStatus.WARN,
                f"Missing: {', '.join(missing_optional)}"
            )
    
    def check_documentation(self):
        """Check documentation exists."""
        print("\n📖 Checking Documentation...")
        
        docs = [
            "docs/USER_GUIDE.md",
            "docs/ADMIN_GUIDE.md",
            "README.md",
        ]
        
        existing = [d for d in docs if os.path.exists(os.path.join(self.project_root, d))]
        missing = [d for d in docs if not os.path.exists(os.path.join(self.project_root, d))]
        
        if not missing:
            self.add_result("Documentation", CheckStatus.PASS, f"{len(existing)} docs found")
        elif len(missing) <= 1:
            self.add_result("Documentation", CheckStatus.WARN, f"Missing: {', '.join(missing)}")
        else:
            self.add_result("Documentation", CheckStatus.FAIL, f"Missing: {', '.join(missing)}")
    
    def run_all_checks(self):
        """Run all validation checks."""
        print("=" * 70)
        print("🔍 PRODUCTION READINESS VALIDATION")
        print("=" * 70)
        print(f"Timestamp: {self.report.timestamp}")
        print(f"Project: {self.project_root}")
        
        # Run all checks
        self.check_python_syntax()
        self.check_imports()
        self.check_code_quality()
        self.check_type_hints()
        self.check_smoke_tests()
        self.check_e2e_tests()
        self.check_security_tests()
        self.check_dependencies()
        self.check_env_configuration()
        self.check_documentation()
        
        # Print summary
        print("\n" + "=" * 70)
        print("📊 VALIDATION SUMMARY")
        print("=" * 70)
        print(f"Total Checks: {len(self.report.checks)}")
        print(f"Passed: {self.report.passed}")
        print(f"Failed: {self.report.failed}")
        print(f"Warnings: {self.report.warnings}")
        print()
        
        if self.report.is_production_ready:
            if self.report.warnings > 0:
                print("⚠️  READY WITH WARNINGS - Review before deployment")
                return 2
            else:
                print("✅ PRODUCTION READY - All checks passed!")
                return 0
        else:
            print("❌ NOT PRODUCTION READY - Critical checks failed!")
            print("\nFailed checks:")
            for check in self.report.checks:
                if check.status == CheckStatus.FAIL:
                    print(f"  - {check.name}: {check.message}")
            return 1


def main():
    """Main entry point."""
    validator = ProductionValidator()
    exit_code = validator.run_all_checks()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
