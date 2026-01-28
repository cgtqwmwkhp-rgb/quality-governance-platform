#!/usr/bin/env python3
"""
Unit tests for the API path drift prevention script.

These tests prove:
1. Bare /api/ paths are detected as violations
2. Versioned /api/v1/ paths are allowed
3. Allowlisted patterns are respected
4. Health endpoints are not flagged
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from check_api_path_drift import (  # noqa: E402
    ALLOWED_PATTERNS,
    DRIFT_PATTERNS,
    Violation,
    is_allowlisted,
    load_allowlist,
    scan_file,
)


class TestDriftPatternDetection(TestCase):
    """Tests proving drift patterns are detected correctly."""
    
    def test_bare_api_path_detected(self):
        """Bare /api/endpoint patterns MUST be detected."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('''
def test_example():
    response = client.get("/api/users")
    assert response.status_code == 200
''')
            f.flush()
            
            violations = scan_file(Path(f.name), set())
            
            self.assertGreater(len(violations), 0)
            self.assertTrue(any('/api/' in v.pattern for v in violations))
            
            os.unlink(f.name)
    
    def test_bare_api_root_detected(self):
        """Bare /api/ endpoint MUST be detected."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('''
BASE_URL = "/api/"
''')
            f.flush()
            
            violations = scan_file(Path(f.name), set())
            
            self.assertGreater(len(violations), 0)
            
            os.unlink(f.name)
    
    def test_versioned_api_path_allowed(self):
        """Versioned /api/v1/ paths MUST NOT be flagged."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('''
def test_example():
    response = client.get("/api/v1/users")
    assert response.status_code == 200
''')
            f.flush()
            
            violations = scan_file(Path(f.name), set())
            
            self.assertEqual(len(violations), 0)
            
            os.unlink(f.name)
    
    def test_versioned_api_v2_allowed(self):
        """Other versions like /api/v2/ MUST also be allowed."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('''
def test_example():
    response = client.get("/api/v2/users")
    assert response.status_code == 200
''')
            f.flush()
            
            violations = scan_file(Path(f.name), set())
            
            self.assertEqual(len(violations), 0)
            
            os.unlink(f.name)
    
    def test_health_endpoint_allowed(self):
        """Health endpoints MUST NOT be flagged."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('''
def test_health():
    response = client.get("/healthz")
    assert response.status_code == 200

def test_ready():
    response = client.get("/readyz")
    assert response.status_code == 200
''')
            f.flush()
            
            violations = scan_file(Path(f.name), set())
            
            self.assertEqual(len(violations), 0)
            
            os.unlink(f.name)


class TestAllowlistHandling(TestCase):
    """Tests proving allowlist functionality works correctly."""
    
    def test_allowlist_loading(self):
        """Allowlist file MUST be loaded correctly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                'allowed_paths': [
                    '/api/legacy/endpoint',
                    '/api/special-case'
                ]
            }, f)
            f.flush()
            
            allowlist = load_allowlist(Path(f.name))
            
            self.assertEqual(len(allowlist), 2)
            self.assertIn('/api/legacy/endpoint', allowlist)
            self.assertIn('/api/special-case', allowlist)
            
            os.unlink(f.name)
    
    def test_missing_allowlist_returns_empty(self):
        """Missing allowlist file MUST return empty set."""
        allowlist = load_allowlist(Path('/nonexistent/allowlist.json'))
        
        self.assertEqual(allowlist, set())
    
    def test_allowlisted_path_not_flagged(self):
        """Paths in allowlist MUST NOT be flagged."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('''
def test_legacy():
    response = client.get("/api/legacy/endpoint")
    assert response.status_code == 200
''')
            f.flush()
            
            allowlist = {'/api/legacy/endpoint'}
            violations = scan_file(Path(f.name), allowlist)
            
            self.assertEqual(len(violations), 0)
            
            os.unlink(f.name)


class TestViolationOutput(TestCase):
    """Tests proving violation output format is correct."""
    
    def test_violation_includes_file_and_line(self):
        """Violations MUST include file path and line number."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('''line1
line2
response = client.get("/api/users")
line4
''')
            f.flush()
            
            violations = scan_file(Path(f.name), set())
            
            self.assertGreater(len(violations), 0)
            v = violations[0]
            self.assertEqual(v.file, f.name)
            self.assertEqual(v.line, 3)  # Line 3 has the violation
            
            os.unlink(f.name)
    
    def test_violation_includes_remediation(self):
        """Violations MUST include remediation guidance."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('url = "/api/users"')
            f.flush()
            
            violations = scan_file(Path(f.name), set())
            
            self.assertGreater(len(violations), 0)
            v = violations[0]
            self.assertIn('/api/v1/', v.remediation)
            
            os.unlink(f.name)


class TestMixedContent(TestCase):
    """Tests with mixed valid and invalid paths."""
    
    def test_mixed_paths_only_flags_invalid(self):
        """Only invalid paths should be flagged in mixed content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('''
# Valid paths
valid1 = "/api/v1/users"
valid2 = "/api/v1/policies"
valid3 = "/healthz"
valid4 = "/readyz"

# Invalid paths
invalid1 = "/api/users"
invalid2 = "/api/policies"
''')
            f.flush()
            
            violations = scan_file(Path(f.name), set())
            
            # Should find exactly 2 violations (the invalid paths)
            self.assertEqual(len(violations), 2)
            
            # Verify the line numbers are correct (lines 9 and 10)
            lines = {v.line for v in violations}
            self.assertIn(9, lines)
            self.assertIn(10, lines)
            
            os.unlink(f.name)


if __name__ == '__main__':
    main()
