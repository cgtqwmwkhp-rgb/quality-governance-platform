#!/usr/bin/env python3
"""
RTA admin lifecycle E2E verification script.

Flow:
1. Login
2. Create RTA
3. Patch status (reported → under_investigation)
4. List linked actions (expect empty initially)
5. Create investigation from RTA via from-record
6. Assert investigation appears on RTA investigations list
7. Add running-sheet entry and list entries

Exit code:
- 0 if all critical steps succeed
- 1 if any step fails
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import requests

TIMEOUT_SECONDS = 45
MAX_ATTEMPTS = 3
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


@dataclass
class StepResult:
    name: str
    passed: bool
    detail: str
    payload: Optional[dict[str, Any]] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _request(
    method: str,
    url: str,
    token: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
    timeout: int = TIMEOUT_SECONDS,
    max_attempts: int = MAX_ATTEMPTS,
) -> requests.Response:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    last_error: Optional[requests.RequestException] = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.request(method, url, headers=headers, json=payload, timeout=timeout)
        except requests.RequestException as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            time.sleep(attempt)
            continue

        if response.status_code in RETRYABLE_STATUS_CODES and attempt < max_attempts:
            time.sleep(attempt)
            continue

        return response

    assert last_error is not None
    raise RuntimeError(
        f"Request to {url} failed after {max_attempts} attempts: "
        f"{last_error.__class__.__name__}: {last_error}"
    ) from last_error


def _request_step(
    results: list[StepResult],
    step_name: str,
    method: str,
    url: str,
    token: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> Optional[requests.Response]:
    try:
        return _request(method, url, token=token, payload=payload)
    except RuntimeError as exc:
        results.append(StepResult(step_name, False, str(exc)))
        return None


def run(base_url: str, email: str, password: str) -> list[StepResult]:
    results: list[StepResult] = []
    token: Optional[str] = None
    rta_id: Optional[int] = None
    investigation_id: Optional[int] = None

    login_resp = _request_step(
        results,
        "login",
        "POST",
        f"{base_url}/api/v1/auth/login",
        payload={"email": email, "password": password},
    )
    if login_resp is None:
        return results
    if login_resp.status_code != 200:
        results.append(
            StepResult(
                "login",
                False,
                f"Expected 200, got {login_resp.status_code}",
                {"body": login_resp.text[:300]},
            )
        )
        return results

    token = login_resp.json().get("access_token")
    if not token:
        results.append(StepResult("login", False, "Missing access_token in login response"))
        return results
    results.append(StepResult("login", True, "Authenticated"))

    now = _now_iso()
    create_resp = _request_step(
        results,
        "create_rta",
        "POST",
        f"{base_url}/api/v1/rtas/",
        token=token,
        payload={
            "title": f"Smoke RTA {now}",
            "description": "Smoke lifecycle collision",
            "severity": "damage_only",
            "collision_date": now,
            "reported_date": now,
            "location": "Smoke test junction",
        },
    )
    if create_resp is None:
        return results
    if create_resp.status_code not in (200, 201):
        results.append(
            StepResult(
                "create_rta",
                False,
                f"Expected 201, got {create_resp.status_code}",
                {"body": create_resp.text[:300]},
            )
        )
        return results

    rta = create_resp.json()
    rta_id = rta.get("id")
    if not rta_id:
        results.append(StepResult("create_rta", False, "Missing RTA id"))
        return results
    results.append(
        StepResult(
            "create_rta",
            True,
            f"Created rta_id={rta_id} ref={rta.get('reference_number')}",
        )
    )

    patch_resp = _request_step(
        results,
        "patch_rta_status",
        "PATCH",
        f"{base_url}/api/v1/rtas/{rta_id}",
        token=token,
        payload={"status": "under_investigation"},
    )
    if patch_resp is None:
        return results
    if patch_resp.status_code != 200:
        results.append(
            StepResult(
                "patch_rta_status",
                False,
                f"Expected 200, got {patch_resp.status_code}",
                {"body": patch_resp.text[:300]},
            )
        )
        return results
    if patch_resp.json().get("status") != "under_investigation":
        results.append(StepResult("patch_rta_status", False, "Status not under_investigation after patch"))
        return results
    results.append(StepResult("patch_rta_status", True, "Status under_investigation"))

    actions_resp = _request_step(
        results,
        "list_rta_actions",
        "GET",
        f"{base_url}/api/v1/actions/?page=1&page_size=10&source_type=rta&source_id={rta_id}",
        token=token,
    )
    if actions_resp is None:
        return results
    if actions_resp.status_code != 200:
        results.append(
            StepResult(
                "list_rta_actions",
                False,
                f"Expected 200, got {actions_resp.status_code}",
                {"body": actions_resp.text[:300]},
            )
        )
        return results
    results.append(
        StepResult(
            "list_rta_actions",
            True,
            f"Listed {actions_resp.json().get('total', 0)} RTA-scoped actions",
        )
    )

    inv_resp = _request_step(
        results,
        "create_investigation_from_record",
        "POST",
        f"{base_url}/api/v1/investigations/from-record",
        token=token,
        payload={
            "source_type": "road_traffic_collision",
            "source_id": rta_id,
            "title": f"Smoke investigation for {rta.get('reference_number', rta_id)}",
        },
    )
    if inv_resp is None:
        return results
    if inv_resp.status_code not in (200, 201):
        results.append(
            StepResult(
                "create_investigation_from_record",
                False,
                f"Expected 201, got {inv_resp.status_code}",
                {"body": inv_resp.text[:300]},
            )
        )
        return results
    investigation = inv_resp.json()
    investigation_id = investigation.get("id")
    results.append(
        StepResult(
            "create_investigation_from_record",
            True,
            f"Created investigation_id={investigation_id} ref={investigation.get('reference_number')}",
        )
    )

    list_inv_resp = _request_step(
        results,
        "list_rta_investigations",
        "GET",
        f"{base_url}/api/v1/rtas/{rta_id}/investigations?page=1&page_size=10",
        token=token,
    )
    if list_inv_resp is None:
        return results
    if list_inv_resp.status_code != 200:
        results.append(
            StepResult(
                "list_rta_investigations",
                False,
                f"Expected 200, got {list_inv_resp.status_code}",
                {"body": list_inv_resp.text[:300]},
            )
        )
        return results
    inv_items = list_inv_resp.json().get("items", [])
    if not any(item.get("id") == investigation_id for item in inv_items):
        results.append(
            StepResult(
                "list_rta_investigations",
                False,
                "Created investigation not listed on RTA",
                {"items": inv_items},
            )
        )
        return results
    results.append(
        StepResult(
            "list_rta_investigations",
            True,
            f"Investigation {investigation_id} linked to RTA {rta_id}",
        )
    )

    rs_add_resp = _request_step(
        results,
        "add_rta_running_sheet_entry",
        "POST",
        f"{base_url}/api/v1/rtas/{rta_id}/running-sheet",
        token=token,
        payload={"content": "Smoke: police reference confirmed"},
    )
    if rs_add_resp is None:
        return results
    if rs_add_resp.status_code not in (200, 201):
        results.append(
            StepResult(
                "add_rta_running_sheet_entry",
                False,
                f"Expected 201, got {rs_add_resp.status_code}",
                {"body": rs_add_resp.text[:300]},
            )
        )
        return results

    rs_list_resp = _request_step(
        results,
        "list_rta_running_sheet",
        "GET",
        f"{base_url}/api/v1/rtas/{rta_id}/running-sheet",
        token=token,
    )
    if rs_list_resp is None:
        return results
    if rs_list_resp.status_code != 200:
        results.append(
            StepResult(
                "list_rta_running_sheet",
                False,
                f"Expected 200, got {rs_list_resp.status_code}",
                {"body": rs_list_resp.text[:300]},
            )
        )
        return results
    entries = rs_list_resp.json()
    if not entries or not any("Smoke: police reference" in (e.get("content") or "") for e in entries):
        results.append(
            StepResult(
                "list_rta_running_sheet",
                False,
                "Running-sheet entry not found after create",
                {"entries": entries},
            )
        )
        return results
    results.append(
        StepResult(
            "list_rta_running_sheet",
            True,
            f"Running sheet has {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}",
        )
    )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="RTA lifecycle smoke verification")
    parser.add_argument("--base-url", required=True, help="API base URL (e.g. https://qgp-staging.example.com)")
    parser.add_argument("--email", required=True, help="Login email")
    parser.add_argument("--password", required=True, help="Login password")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()

    results = run(args.base_url.rstrip("/"), args.email, args.password)
    passed = all(step.passed for step in results)

    if args.json:
        print(
            json.dumps(
                {
                    "passed": passed,
                    "steps": [
                        {"name": s.name, "passed": s.passed, "detail": s.detail, "payload": s.payload}
                        for s in results
                    ],
                },
                indent=2,
            )
        )
    else:
        for step in results:
            status = "PASS" if step.passed else "FAIL"
            print(f"[{status}] {step.name}: {step.detail}")
        print(f"\nOverall: {'PASS' if passed else 'FAIL'} ({sum(s.passed for s in results)}/{len(results)} steps)")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
