# CI Workflow Setup Instructions

Due to GitHub App permission restrictions, the CI workflow file (`.github/workflows/ci.yml`) cannot be pushed via the Manus GitHub integration. This document provides instructions for manually adding the workflow through the GitHub web interface.

## Workflow File Location

The complete CI workflow configuration is available in the repository at commit `47622ac` or can be found in the Stage 0 completion reports.

## Manual Setup Steps

1. Navigate to the repository on GitHub: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform

2. Create the `.github/workflows` directory structure:
   - Click "Add file" → "Create new file"
   - In the filename field, enter: `.github/workflows/ci.yml`

3. Copy the workflow content from the file below into the editor

4. Commit the file directly to the `main` branch

## CI Workflow Content

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  code-quality:
    name: Code Quality
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install black isort flake8 mypy
          pip install -r requirements.txt

      - name: Check code formatting (black)
        run: black --check src/ tests/

      - name: Check import sorting (isort)
        run: isort --check-only src/ tests/

      - name: Lint with flake8
        run: flake8 src/ tests/ --count --show-source --statistics

      - name: Type check with mypy
        run: mypy src/ --ignore-missing-imports

  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run unit tests
        run: |
          pytest tests/unit/ -v --cov=src --cov-report=xml --cov-report=term

      - name: Upload coverage reports
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          flags: unit
          name: codecov-umbrella
        if: always()

  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: testpass
          POSTGRES_DB: quality_governance_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run Alembic migrations
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:testpass@localhost:5432/quality_governance_test
        run: |
          alembic upgrade head
          echo "✅ Migrations applied successfully using Postgres context"

      - name: Validate quarantine policy
        run: |
          python3 scripts/validate_quarantine.py

      - name: Run integration tests
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:testpass@localhost:5432/quality_governance_test
        run: |
          pytest tests/integration/ -v --cov=src --cov-report=xml --cov-report=term

      - name: Upload coverage reports
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          flags: integration
          name: codecov-umbrella
        if: always()

  security-scan:
    name: Security Scan
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pip-audit bandit

      - name: Validate security waivers (BLOCKING)
        run: |
          pip install -r requirements.txt
          echo "=== Security Waiver Validation (BLOCKING) ==="
          python3 scripts/validate_security_waivers.py
          echo ""

      - name: Security linting with Bandit (BLOCKING on High severity)
        run: |
          echo "=== Bandit: Security Linting (BLOCKING on High) ==="
          bandit -r src/ -ll -f screen
          echo ""
          echo "✅ Bandit passed: No High severity issues found"

  build-check:
    name: Build Check
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Verify application starts
        env:
          DATABASE_URL: sqlite+aiosqlite:///./test.db
          SECRET_KEY: test-secret-key
          JWT_SECRET_KEY: test-jwt-secret
        run: |
          python -c "from src.main import app; print('✅ Application imports successfully')"

  all-checks:
    name: All Checks Passed
    runs-on: ubuntu-latest
    needs: [code-quality, unit-tests, integration-tests, security-scan, build-check]
    
    steps:
      - name: All checks passed
        run: |
          echo "✅ All CI checks passed successfully!"
          echo "The code is ready to be merged."
```

## Verification

After adding the workflow:

1. The CI should automatically run on the next push to `main` or `develop`
2. You can view the run at: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions
3. All jobs should pass green, confirming the release governance foundation is complete

## Troubleshooting

If the workflow fails:

1. Check the job logs in the Actions tab
2. Verify the Postgres service is starting correctly
3. Ensure all dependencies are installing without errors
4. Review the quarantine validation output

For security scan warnings about the `ecdsa` vulnerability, refer to `docs/SECURITY_WAIVERS.md` for the documented risk acceptance.
