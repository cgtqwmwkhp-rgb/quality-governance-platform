#!/usr/bin/env python3
"""
Setup UX Test User for Staging

Creates or updates the UX coverage test user in the staging database.
STAGING ONLY - Will refuse to run if APP_ENV is not 'staging'.

Security:
- Credentials read from environment variables
- Password never printed
- User email never logged (uses masked format)

Usage:
    export APP_ENV=staging
    export UX_TEST_USER_EMAIL="ux-test-runner@staging.local"
    export UX_TEST_USER_PASSWORD="<secure-password>"
    export DATABASE_URL="postgresql://..."
    python scripts/governance/setup-ux-test-user.py

Options:
    --verify-only   Only verify the user exists and can authenticate
    --create        Create or update the user
"""

import argparse
import hashlib
import logging
import os
import sys
from datetime import datetime

# Configure logging - never log sensitive data
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def mask_email(email: str) -> str:
    """Mask email for logging (show only first 2 chars and domain)."""
    if not email or "@" not in email:
        return "<invalid>"
    local, domain = email.rsplit("@", 1)
    masked_local = local[:2] + "***" if len(local) > 2 else "***"
    return f"{masked_local}@{domain}"


def check_environment():
    """Verify we're running in staging environment."""
    app_env = os.environ.get("APP_ENV", "").lower()

    if app_env != "staging":
        logger.error(f"❌ Refusing to run: APP_ENV={app_env}, expected 'staging'")
        logger.error("This script only runs in staging to prevent accidental production changes.")
        sys.exit(1)

    logger.info("✅ Environment check passed: staging")


def get_credentials():
    """Get test user credentials from environment."""
    email = os.environ.get("UX_TEST_USER_EMAIL")
    password = os.environ.get("UX_TEST_USER_PASSWORD")

    if not email:
        logger.error("❌ UX_TEST_USER_EMAIL not set")
        sys.exit(1)

    if not password:
        logger.error("❌ UX_TEST_USER_PASSWORD not set")
        sys.exit(1)

    logger.info(f"📧 User email: {mask_email(email)}")
    logger.info("🔐 Password: <set>")

    return email, password


def verify_user_via_api(base_url: str, email: str, password: str) -> bool:
    """Verify user can authenticate via API."""
    import json
    import urllib.error
    import urllib.request

    login_url = f"{base_url}/api/v1/auth/login"

    logger.info(f"🔄 Testing authentication at {login_url}...")

    data = json.dumps({"email": email, "password": password}).encode("utf-8")

    try:
        req = urllib.request.Request(
            login_url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "ux-test-user-setup/1.0"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status == 200:
                result = json.loads(response.read().decode("utf-8"))
                if "access_token" in result:
                    logger.info("✅ Authentication successful, token received")

                    # Verify token via whoami
                    token = result["access_token"]
                    whoami_url = f"{base_url}/api/v1/auth/whoami"
                    whoami_req = urllib.request.Request(
                        whoami_url, headers={"Authorization": f"Bearer {token}", "User-Agent": "ux-test-user-setup/1.0"}
                    )

                    with urllib.request.urlopen(whoami_req, timeout=10) as whoami_resp:
                        if whoami_resp.status == 200:
                            whoami_data = json.loads(whoami_resp.read().decode("utf-8"))
                            logger.info(
                                f"✅ Token verified: user_id={whoami_data.get('user_id')}, is_active={whoami_data.get('is_active')}"
                            )
                            return True

                    return True
                else:
                    logger.error("❌ Login succeeded but no token in response")
                    return False
            else:
                logger.error(f"❌ Unexpected response: HTTP {response.status}")
                return False

    except urllib.error.HTTPError as e:
        if e.code == 401:
            logger.error("❌ Authentication failed: Invalid credentials")
        elif e.code == 403:
            logger.error("❌ Authentication failed: User account disabled")
        else:
            logger.error(f"❌ HTTP error: {e.code}")
        return False
    except urllib.error.URLError as e:
        logger.error(f"❌ Connection error: {e.reason}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False


def create_user_instructions(email: str):
    """Print instructions for manual user creation."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("MANUAL USER CREATION REQUIRED")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Create the test user in the staging database with:")
    logger.info("")
    logger.info("  Email: <from UX_TEST_USER_EMAIL secret>")
    logger.info("  Roles: user, employee, admin, viewer")
    logger.info("  Active: true")
    logger.info("  Password: <from UX_TEST_USER_PASSWORD secret>")
    logger.info("")
    logger.info("SQL (example - adapt for your ORM/admin interface):")
    logger.info("")
    logger.info("  INSERT INTO users (email, hashed_password, is_active, first_name, last_name)")
    logger.info("  VALUES ('<email>', '<bcrypt_hash>', true, 'UX', 'TestRunner');")
    logger.info("")
    logger.info("  -- Then assign roles:")
    logger.info("  INSERT INTO user_roles (user_id, role_id)")
    logger.info("  SELECT u.id, r.id FROM users u, roles r")
    logger.info("  WHERE u.email = '<email>' AND r.name IN ('user', 'employee', 'admin', 'viewer');")
    logger.info("")
    logger.info("Or use the admin UI to create the user and assign roles.")
    logger.info("")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Setup UX Test User for Staging")
    parser.add_argument("--verify-only", action="store_true", help="Only verify authentication")
    parser.add_argument("--create", action="store_true", help="Create or update user")
    args = parser.parse_args()

    logger.info("🔧 UX Test User Setup")
    logger.info("=" * 50)

    # Safety check
    check_environment()

    # Get credentials
    email, password = get_credentials()

    # Get staging URL
    staging_url = os.environ.get("APP_URL", "https://app-qgp-staging.azurewebsites.net")
    logger.info(f"🌐 Staging URL: {staging_url}")

    # Verify authentication
    if verify_user_via_api(staging_url, email, password):
        logger.info("")
        logger.info("✅ UX test user is ready for CI")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Add GitHub secrets if not already done:")
        logger.info("     - UX_TEST_USER_EMAIL")
        logger.info("     - UX_TEST_USER_PASSWORD")
        logger.info("  2. Run UX coverage workflow manually to verify")
        sys.exit(0)
    else:
        if args.create:
            create_user_instructions(email)
            sys.exit(1)
        else:
            logger.error("")
            logger.error("❌ User cannot authenticate")
            logger.error("Run with --create to see setup instructions")
            sys.exit(1)


if __name__ == "__main__":
    main()
