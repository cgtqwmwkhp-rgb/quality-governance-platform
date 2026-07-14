#!/usr/bin/env python3
"""
Complaint admin lifecycle E2E verification script.

Flow:
1. Login
2. Create complaint
3. List complaints (assert created id is tenant-visible)
4. Get complaint detail
5. Patch status (received → acknowledged)
6. List linked actions (expect empty initially)
7. Create investigation from complaint via from-record
8. Add running-sheet entry and list entries
9. Assert investigation appears on complaint investigations list

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
    complaint_id: Optional[int] = None
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
            StepResult("login", False, f"Expected 200, got {login_resp.status_code}", {"body": login_resp.text[:300]})
        )
        return results

    token = login_resp.json().get("access_token")
    if not token:
        results.append(StepResult("login", False, "Missing access_token in login response"))
        return results
    results.append(StepResult("login", True, "Authenticated"))

    create_resp = _request_step(
        results,
        "create_complaint",
        "POST",
        f"{base_url}/api/v1/complaints/",
        token=token,
        payload={
            "title": f"Smoke complaint {_now_iso()}",
            "description": "Complaint lifecycle smoke verification",
            "complaint_type": "service",
            "received_date": _now_iso(),
            "complainant_name": "Smoke Tester",
            "complainant_email": "smoke@test.local",
            "priority": "medium",
        },
    )
    if create_resp is None:
        return results
    if create_resp.status_code not in (200, 201):
        results.append(
            StepResult(
                "create_complaint",
                False,
                f"Expected 201, got {create_resp.status_code}",
                {"body": create_resp.text[:300]},
            )
        )
        return results

    complaint = create_resp.json()
    complaint_id = complaint.get("id")
    if not complaint_id:
        results.append(StepResult("create_complaint", False, "Missing complaint id"))
        return results
    results.append(
        StepResult(
            "create_complaint",
            True,
            f"Created complaint_id={complaint_id} ref={complaint.get('reference_number')}",
        )
    )

    list_resp = _request_step(
        results,
        "list_complaints",
        "GET",
        f"{base_url}/api/v1/complaints/?page=1&page_size=50",
        token=token,
    )
    if list_resp is None:
        return results
    if list_resp.status_code != 200:
        results.append(
            StepResult(
                "list_complaints",
                False,
                f"Expected 200, got {list_resp.status_code}",
                {"body": list_resp.text[:300]},
            )
        )
        return results
    list_payload = list_resp.json()
    list_items = list_payload.get("items") or list_payload.get("data") or []
    if not any(item.get("id") == complaint_id for item in list_items if isinstance(item, dict)):
        results.append(
            StepResult(
                "list_complaints",
                False,
                f"Created complaint_id={complaint_id} not present in tenant-scoped list",
                {"total": list_payload.get("total"), "count": len(list_items)},
            )
        )
        return results
    results.append(
        StepResult(
            "list_complaints",
            True,
            f"Created complaint visible in list (total={list_payload.get('total', len(list_items))})",
        )
    )

    get_resp = _request_step(
        results,
        "get_complaint_detail",
        "GET",
        f"{base_url}/api/v1/complaints/{complaint_id}",
        token=token,
    )
    if get_resp is None:
        return results
    if get_resp.status_code != 200:
        results.append(
            StepResult(
                "get_complaint_detail",
                False,
                f"Expected 200, got {get_resp.status_code}",
                {"body": get_resp.text[:300]},
            )
        )
        return results
    detail = get_resp.json()
    if detail.get("id") != complaint_id:
        results.append(StepResult("get_complaint_detail", False, "Detail id mismatch"))
        return results
    results.append(
        StepResult(
            "get_complaint_detail",
            True,
            f"Detail ok ref={detail.get('reference_number')} status={detail.get('status')}",
        )
    )

    patch_resp = _request_step(
        results,
        "patch_complaint_status",
        "PATCH",
        f"{base_url}/api/v1/complaints/{complaint_id}",
        token=token,
        payload={"status": "acknowledged"},
    )
    if patch_resp is None:
        return results
    if patch_resp.status_code != 200:
        results.append(
            StepResult(
                "patch_complaint_status",
                False,
                f"Expected 200, got {patch_resp.status_code}",
                {"body": patch_resp.text[:300]},
            )
        )
        return results
    if patch_resp.json().get("status") != "acknowledged":
        results.append(StepResult("patch_complaint_status", False, "Status not acknowledged after patch"))
        return results
    results.append(StepResult("patch_complaint_status", True, "Status acknowledged"))

    actions_resp = _request_step(
        results,
        "list_complaint_actions",
        "GET",
        f"{base_url}/api/v1/actions/?page=1&page_size=10&source_type=complaint&source_id={complaint_id}",
        token=token,
    )
    if actions_resp is None:
        return results
    if actions_resp.status_code != 200:
        results.append(
            StepResult(
                "list_complaint_actions",
                False,
                f"Expected 200, got {actions_resp.status_code}",
                {"body": actions_resp.text[:300]},
            )
        )
        return results
    results.append(
        StepResult(
            "list_complaint_actions",
            True,
            f"Listed {actions_resp.json().get('total', 0)} complaint-scoped actions",
        )
    )

    inv_resp = _request_step(
        results,
        "create_investigation_from_record",
        "POST",
        f"{base_url}/api/v1/investigations/from-record",
        token=token,
        payload={
            "source_type": "complaint",
            "source_id": complaint_id,
            "title": f"Smoke investigation for {complaint.get('reference_number', complaint_id)}",
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
        "list_complaint_investigations",
        "GET",
        f"{base_url}/api/v1/complaints/{complaint_id}/investigations?page=1&page_size=10",
        token=token,
    )
    if list_inv_resp is None:
        return results
    if list_inv_resp.status_code != 200:
        results.append(
            StepResult(
                "list_complaint_investigations",
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
                "list_complaint_investigations",
                False,
                "Created investigation not listed on complaint",
                {"items": inv_items},
            )
        )
        return results
    results.append(
        StepResult(
            "list_complaint_investigations",
            True,
            f"Investigation {investigation_id} linked to complaint {complaint_id}",
        )
    )

    rs_add_resp = _request_step(
        results,
        "add_complaint_running_sheet_entry",
        "POST",
        f"{base_url}/api/v1/complaints/{complaint_id}/running-sheet",
        token=token,
        payload={"content": "Smoke: acknowledged complainant"},
    )
    if rs_add_resp is None:
        return results
    if rs_add_resp.status_code not in (200, 201):
        results.append(
            StepResult(
                "add_complaint_running_sheet_entry",
                False,
                f"Expected 201, got {rs_add_resp.status_code}",
                {"body": rs_add_resp.text[:300]},
            )
        )
        return results

    rs_list_resp = _request_step(
        results,
        "list_complaint_running_sheet",
        "GET",
        f"{base_url}/api/v1/complaints/{complaint_id}/running-sheet",
        token=token,
    )
    if rs_list_resp is None:
        return results
    if rs_list_resp.status_code != 200:
        results.append(
            StepResult(
                "list_complaint_running_sheet",
                False,
                f"Expected 200, got {rs_list_resp.status_code}",
                {"body": rs_list_resp.text[:300]},
            )
        )
        return results
    entries = rs_list_resp.json()
    if not entries or not any("Smoke: acknowledged" in (e.get("content") or "") for e in entries):
        results.append(
            StepResult(
                "list_complaint_running_sheet",
                False,
                "Running-sheet entry not found after create",
                {"entries": entries},
            )
        )
        return results
    results.append(
        StepResult(
            "list_complaint_running_sheet",
            True,
            f"Running sheet has {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}",
        )
    )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Complaint lifecycle smoke verification")
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
