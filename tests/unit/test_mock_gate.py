"""Unit tests for the Mock Data Eradication Gate scanner.

Test ID: MOCK-GATE-001
"""

import sys
import tempfile
from pathlib import Path

import pytest

# Import the scanner module - path manipulation required for scripts/
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from check_mock_data import PATTERNS, Violation, scan_file  # noqa: E402


class TestMockGatePatterns:
    """Test pattern detection in the mock gate scanner."""

    def test_detects_mock_constant(self, tmp_path: Path):
        """MOCK_* constants should be detected."""
        test_file = tmp_path / "test.tsx"
        test_file.write_text("const MOCK_ACTIONS = [{ id: 1 }];")

        violations = scan_file(test_file, tmp_path)

        assert len(violations) == 1
        assert violations[0].pattern == "MOCK_CONSTANT"
        assert "MOCK_ACTIONS" in violations[0].match

    def test_detects_settimeout_simulation(self, tmp_path: Path):
        """setTimeout() calls should be detected."""
        test_file = tmp_path / "test.tsx"
        test_file.write_text("setTimeout(() => { setData(mockData) }, 500);")

        violations = scan_file(test_file, tmp_path)

        # Should detect setTimeout
        settimeout_violations = [
            v for v in violations if v.pattern == "SETTIMEOUT_SIMULATION"
        ]
        assert len(settimeout_violations) == 1

    def test_detects_coming_soon(self, tmp_path: Path):
        """'coming soon' placeholder text should be detected."""
        test_file = tmp_path / "test.tsx"
        test_file.write_text("<p>This feature is coming soon</p>")

        violations = scan_file(test_file, tmp_path)

        coming_soon_violations = [
            v for v in violations if v.pattern == "COMING_SOON_PLACEHOLDER"
        ]
        assert len(coming_soon_violations) == 1

    def test_detects_mock_lowercase(self, tmp_path: Path):
        """mockCompliance style objects should be detected."""
        test_file = tmp_path / "test.tsx"
        test_file.write_text("const mockCompliance = { iso9001: 87 };")

        violations = scan_file(test_file, tmp_path)

        mock_violations = [v for v in violations if v.pattern == "MOCK_LOWERCASE"]
        assert len(mock_violations) == 1

    def test_allows_static_config_annotation(self, tmp_path: Path):
        """Lines with STATIC_UI_CONFIG_OK should be allowed."""
        test_file = tmp_path / "test.tsx"
        test_file.write_text(
            "// STATIC_UI_CONFIG_OK\n" "const MOCK_CONFIG = { key: 'value' };"
        )

        violations = scan_file(test_file, tmp_path)

        assert len(violations) == 0

    def test_allows_test_files(self, tmp_path: Path):
        """Test files should be allowlisted."""
        # Create in __tests__ directory
        test_dir = tmp_path / "__tests__"
        test_dir.mkdir()
        test_file = test_dir / "test.tsx"
        test_file.write_text("const MOCK_DATA = [1, 2, 3];")

        violations = scan_file(test_file, tmp_path)

        assert len(violations) == 0

    def test_allows_fixture_files(self, tmp_path: Path):
        """Fixture files should be allowlisted."""
        test_file = tmp_path / "data.fixture.ts"
        test_file.write_text("const MOCK_DATA = [1, 2, 3];")

        violations = scan_file(test_file, tmp_path)

        assert len(violations) == 0

    def test_clean_file_returns_no_violations(self, tmp_path: Path):
        """A file without mock patterns should return no violations."""
        test_file = tmp_path / "clean.tsx"
        test_file.write_text(
            "import { useEffect, useState } from 'react';\n"
            "export function Component() {\n"
            "  const [data, setData] = useState([]);\n"
            "  useEffect(() => { fetchData(); }, []);\n"
            "  return <div>{data.map(d => <span key={d.id}>{d.name}</span>)}</div>;\n"
            "}\n"
        )

        violations = scan_file(test_file, tmp_path)

        assert len(violations) == 0


class TestMockGateViolationFormat:
    """Test violation output formatting."""

    def test_violation_contains_file_and_line(self, tmp_path: Path):
        """Violations should include file path and line number."""
        test_file = tmp_path / "test.tsx"
        test_file.write_text("line1\nconst MOCK_DATA = [];\nline3")

        violations = scan_file(test_file, tmp_path)

        assert len(violations) == 1
        assert violations[0].line == 2
        assert "test.tsx" in violations[0].file

    def test_violation_contains_remediation(self, tmp_path: Path):
        """Violations should include remediation hint."""
        test_file = tmp_path / "test.tsx"
        test_file.write_text("const MOCK_ITEMS = [];")

        violations = scan_file(test_file, tmp_path)

        assert len(violations) == 1
        assert violations[0].remediation != ""
        assert (
            "API" in violations[0].remediation or "Replace" in violations[0].remediation
        )
