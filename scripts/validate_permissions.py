#!/usr/bin/env python3
"""
Validate that all mutating endpoints (POST/PUT/PATCH/DELETE) use permission checks.

This CI gate ensures that all route handlers for mutating operations use
require_permission() or require_role() dependencies instead of just CurrentUser.

Rules:
1. All POST/PUT/PATCH/DELETE endpoints must have a parameter using require_permission() or require_role()
2. Endpoints using only CurrentUser without permission checks are violations
3. GET endpoints are excluded from this check (read-only operations)

Exit codes:
0 - All endpoints are compliant
1 - Violations found (unless --warn-only is used)
"""

import argparse
import ast
import sys
from pathlib import Path
from typing import List, Tuple


# Mutating HTTP methods that require permission checks
MUTATING_METHODS = {"post", "put", "patch", "delete"}


class PermissionValidator(ast.NodeVisitor):
    """AST visitor to validate route handlers have permission checks."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.violations: List[Tuple[int, str, str]] = []  # (line, endpoint_name, method)
        self.current_decorator = None
        self.current_function = None

    def _has_permission_check(self, annotation) -> bool:
        """Check if an annotation uses require_permission, require_role, or CurrentSuperuser."""
        if annotation is None:
            return False

        # Handle CurrentSuperuser (direct name annotation)
        if isinstance(annotation, ast.Name):
            if annotation.id == "CurrentSuperuser":
                return True
            return False

        # Handle Annotated[User, Depends(...)]
        if isinstance(annotation, ast.Subscript):
            if isinstance(annotation.value, ast.Name) and annotation.value.id == "Annotated":
                # Get the slice (can be Tuple or Index depending on Python version)
                slice_node = annotation.slice
                if isinstance(slice_node, ast.Tuple):
                    if len(slice_node.elts) >= 2:
                        depends_expr = slice_node.elts[1]
                    else:
                        return False
                elif isinstance(slice_node, ast.Index):  # Python < 3.9
                    if isinstance(slice_node.value, ast.Tuple) and len(slice_node.value.elts) >= 2:
                        depends_expr = slice_node.value.elts[1]
                    else:
                        return False
                else:
                    return False

                # Check Depends() call
                if isinstance(depends_expr, ast.Call):
                    # Check if it's Depends(...)
                    if isinstance(depends_expr.func, ast.Name) and depends_expr.func.id == "Depends":
                        if depends_expr.args:
                            dep_arg = depends_expr.args[0]
                            # Check if it's require_permission(...) or require_role(...)
                            if isinstance(dep_arg, ast.Call):
                                # Check function name
                                if isinstance(dep_arg.func, ast.Name):
                                    if dep_arg.func.id in ("require_permission", "require_role"):
                                        return True
                                elif isinstance(dep_arg.func, ast.Attribute):
                                    if dep_arg.func.attr in ("require_permission", "require_role"):
                                        return True

        return False

    def _has_current_user_only(self, annotation) -> bool:
        """Check if an annotation uses CurrentUser without permission checks."""
        if annotation is None:
            return False

        # Direct CurrentUser annotation
        if isinstance(annotation, ast.Name):
            if annotation.id == "CurrentUser":
                return True
            return False

        # Handle Annotated[User, Depends(get_current_user)] pattern
        if isinstance(annotation, ast.Subscript):
            if isinstance(annotation.value, ast.Name) and annotation.value.id == "Annotated":
                # Get the slice (can be Tuple or Index depending on Python version)
                slice_node = annotation.slice
                if isinstance(slice_node, ast.Tuple):
                    if len(slice_node.elts) >= 2:
                        depends_expr = slice_node.elts[1]
                    else:
                        return False
                elif isinstance(slice_node, ast.Index):  # Python < 3.9
                    if isinstance(slice_node.value, ast.Tuple) and len(slice_node.value.elts) >= 2:
                        depends_expr = slice_node.value.elts[1]
                    else:
                        return False
                else:
                    return False

                if isinstance(depends_expr, ast.Call):
                    if isinstance(depends_expr.func, ast.Name) and depends_expr.func.id == "Depends":
                        if depends_expr.args:
                            dep_arg = depends_expr.args[0]
                            # Check if it's get_current_user (CurrentUser pattern)
                            if isinstance(dep_arg, ast.Name) and dep_arg.id == "get_current_user":
                                return True

        return False

    def _check_function(self, node):
        """Check a function (sync or async) for permission dependencies."""
        # Check decorators for route methods
        route_method = None
        endpoint_name = node.name

        for decorator in node.decorator_list:
            # Handle @router.post, @router.put, etc.
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    if decorator.func.attr in MUTATING_METHODS:
                        route_method = decorator.func.attr.upper()
                        endpoint_name = node.name
                        break

        if route_method:
            # This is a mutating endpoint, check for permission dependencies
            has_permission_check = False
            has_current_user = False

            # Check all function parameters
            for arg in node.args.args:
                annotation = arg.annotation
                if self._has_permission_check(annotation):
                    has_permission_check = True
                elif self._has_current_user_only(annotation):
                    has_current_user = True

            # If no permission check and has CurrentUser, it's a violation
            if not has_permission_check and has_current_user:
                self.violations.append((node.lineno, endpoint_name, route_method))

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definitions and check for permission dependencies."""
        self._check_function(node)
        # Continue visiting child nodes
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit async function definitions and check for permission dependencies."""
        self._check_function(node)
        # Continue visiting child nodes
        self.generic_visit(node)


def validate_route_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """Validate a single route file for permission checks."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"⚠️  Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return []

    try:
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError as e:
        print(f"⚠️  Warning: Syntax error in {file_path}:{e.lineno}: {e.msg}", file=sys.stderr)
        return []

    validator = PermissionValidator(file_path)
    validator.visit(tree)
    return validator.violations


def main():
    parser = argparse.ArgumentParser(description="Validate that mutating endpoints use permission checks")
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Only warn about violations, don't fail the build",
    )
    parser.add_argument(
        "--routes-dir",
        type=Path,
        default=Path(__file__).parent.parent / "src" / "api" / "routes",
        help="Directory containing route files (default: src/api/routes)",
    )
    args = parser.parse_args()

    routes_dir = args.routes_dir
    if not routes_dir.exists():
        print(f"❌ Error: Routes directory not found: {routes_dir}", file=sys.stderr)
        sys.exit(1)

    print("🔍 Validating permission checks on mutating endpoints...")
    print(f"📂 Scanning: {routes_dir}")
    print()

    all_violations = []

    # Find all Python files in routes directory
    for route_file in sorted(routes_dir.glob("*.py")):
        # Skip __init__.py
        if route_file.name == "__init__.py":
            continue

        violations = validate_route_file(route_file)
        if violations:
            all_violations.extend([(route_file, line, name, method) for line, name, method in violations])

    if not all_violations:
        print("✅ All mutating endpoints have proper permission checks!")
        sys.exit(0)

    # Report violations
    print(f"❌ Found {len(all_violations)} endpoint(s) without permission checks:\n")
    for route_file, line, endpoint_name, method in all_violations:
        rel_path = route_file.relative_to(Path(__file__).parent.parent)
        print(f"   {rel_path}:{line} - {endpoint_name} ({method})")
        print(f"      Missing: require_permission() or require_role() dependency")

    print()
    print("💡 Fix: Add a parameter like:")
    print('      current_user: Annotated[User, Depends(require_permission("resource:action"))]')
    print("   Or use CurrentSuperuser if superuser-only access is intended.")

    if args.warn_only:
        print("\n⚠️  Warning mode: Not failing build")
        sys.exit(0)
    else:
        print("\n❌ Build failed: Fix violations before merging")
        sys.exit(1)


if __name__ == "__main__":
    main()
