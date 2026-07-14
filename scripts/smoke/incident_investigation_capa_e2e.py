#!/usr/bin/env python3
"""
Incident → Investigation → CAPA residual smoke verification.

Flow:
1. Login
2. Create incident
3. Create investigation from-record (reporting_incident)
4. Assert investigation appears on incident investigations list
5. Create investigation-scoped action + incident-scoped action
6. Create capa_actions CAPA (source_type=incident) and assert unified capa_incident filter
7. Resolve CAPA via /actions/by-key for reverse deep-link honesty

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
    params: Optional[dict[str, Any]] = None,
    timeout: int = TIMEOUT_SECONDS,
    max_attempts: int = MAX_ATTEMPTS,
) -> requests.Response:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    last_error: Optional[requests.RequestException] = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                json=payload,
                params=params,
                timeout=timeout,
            )
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
    params: Optional[dict[str, Any]] = None,
) -> Optional[requests.Response]:
    try:
        return _request(method, url, token=token, payload=payload, params=params)
    except RuntimeError as exc:
        results.append(StepResult(step_name, False, str(exc)))
        return None


def run(base_url: str, email: str, password: str) -> list[StepResult]:
    results: list[StepResult] = []
    token: Optional[str] = None

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
        "create_incident",
        "POST",
        f"{base_url}/api/v1/incidents/",
        token=token,
        payload={
            "title": f"Smoke incident {now}",
            "description": "Smoke lifecycle slip near loading bay",
            "incident_type": "injury",
            "severity": "high",
            "status": "reported",
            "incident_date": now,
            "location": "Smoke loading bay",
        },
    )
    if create_resp is None:
        return results
    if create_resp.status_code not in (200, 201):
        results.append(
            StepResult(
                "create_incident",
                False,
                f"Expected 201, got {create_resp.status_code}",
                {"body": create_resp.text[:300]},
            )
        )
        return results

    incident = create_resp.json()
    incident_id = incident.get("id")
    if not incident_id:
        results.append(StepResult("create_incident", False, "Missing incident id"))
        return results
    results.append(
        StepResult(
            "create_incident",
            True,
            f"Created incident_id={incident_id} ref={incident.get('reference_number')}",
        )
    )

    inv_resp = _request_step(
        results,
        "create_investigation_from_record",
        "POST",
        f"{base_url}/api/v1/investigations/from-record",
        token=token,
        payload={
            "source_type": "reporting_incident",
            "source_id": incident_id,
            "title": f"Smoke investigation for {incident.get('reference_number', incident_id)}",
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
        "list_incident_investigations",
        "GET",
        f"{base_url}/api/v1/incidents/{incident_id}/investigations",
        token=token,
        params={"page": 1, "page_size": 10},
    )
    if list_inv_resp is None:
        return results
    if list_inv_resp.status_code != 200:
        results.append(
            StepResult(
                "list_incident_investigations",
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
                "list_incident_investigations",
                False,
                "Created investigation not listed on incident",
                {"items": inv_items},
            )
        )
        return results
    results.append(
        StepResult(
            "list_incident_investigations",
            True,
            f"Investigation {investigation_id} linked to incident {incident_id}",
        )
    )

    inv_action_resp = _request_step(
        results,
        "create_investigation_action",
        "POST",
        f"{base_url}/api/v1/actions/",
        token=token,
        payload={
            "title": "Smoke: install anti-slip matting",
            "description": "Investigation-scoped CAPA",
            "source_type": "investigation",
            "source_id": investigation_id,
            "priority": "high",
            "action_type": "corrective",
        },
    )
    if inv_action_resp is None:
        return results
    if inv_action_resp.status_code not in (200, 201):
        results.append(
            StepResult(
                "create_investigation_action",
                False,
                f"Expected 201, got {inv_action_resp.status_code}",
                {"body": inv_action_resp.text[:300]},
            )
        )
        return results
    inv_action = inv_action_resp.json()
    results.append(
        StepResult(
            "create_investigation_action",
            True,
            f"Created investigation action key={inv_action.get('action_key')}",
        )
    )

    capa_resp = _request_step(
        results,
        "create_capa_incident",
        "POST",
        f"{base_url}/api/v1/capa",
        token=token,
        payload={
            "title": "Smoke CAPA from incident",
            "description": "Formal capa_actions row linked to incident",
            "capa_type": "corrective",
            "priority": "high",
            "source_type": "incident",
            "source_id": incident_id,
            "proposed_action": "Permanent floor treatment",
        },
    )
    if capa_resp is None:
        return results
    if capa_resp.status_code not in (200, 201):
        results.append(
            StepResult(
                "create_capa_incident",
                False,
                f"Expected 201, got {capa_resp.status_code}",
                {"body": capa_resp.text[:300]},
            )
        )
        return results
    capa = capa_resp.json()
    capa_id = capa.get("id")
    results.append(
        StepResult(
            "create_capa_incident",
            True,
            f"Created capa_id={capa_id} source_id={capa.get('source_id')}",
        )
    )

    capa_list_resp = _request_step(
        results,
        "list_capa_incident_actions",
        "GET",
        f"{base_url}/api/v1/actions/",
        token=token,
        params={"source_type": "capa_incident", "source_id": incident_id, "page": 1, "page_size": 50},
    )
    if capa_list_resp is None:
        return results
    if capa_list_resp.status_code != 200:
        results.append(
            StepResult(
                "list_capa_incident_actions",
                False,
                f"Expected 200, got {capa_list_resp.status_code}",
                {"body": capa_list_resp.text[:300]},
            )
        )
        return results
    capa_items = capa_list_resp.json().get("items", [])
    if not any(
        item.get("action_key") == f"capa:{capa_id}" and item.get("source_type") == "capa_incident"
        for item in capa_items
    ):
        results.append(
            StepResult(
                "list_capa_incident_actions",
                False,
                "capa_incident filter missing created CAPA",
                {"items": capa_items},
            )
        )
        return results
    results.append(
        StepResult(
            "list_capa_incident_actions",
            True,
            f"capa_incident list contains capa:{capa_id}",
        )
    )

    by_key_resp = _request_step(
        results,
        "get_capa_by_key",
        "GET",
        f"{base_url}/api/v1/actions/by-key",
        token=token,
        params={"key": f"capa:{capa_id}"},
    )
    if by_key_resp is None:
        return results
    if by_key_resp.status_code != 200:
        results.append(
            StepResult(
                "get_capa_by_key",
                False,
                f"Expected 200, got {by_key_resp.status_code}",
                {"body": by_key_resp.text[:300]},
            )
        )
        return results
    keyed = by_key_resp.json()
    if keyed.get("source_type") != "capa_incident" or keyed.get("source_id") != incident_id:
        results.append(
            StepResult(
                "get_capa_by_key",
                False,
                "by-key response missing capa_incident linkage",
                {"body": keyed},
            )
        )
        return results
    results.append(
        StepResult(
            "get_capa_by_key",
            True,
            f"by-key capa:{capa_id} → incident {incident_id}",
        )
    )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Incident→Investigation→CAPA residual smoke")
    parser.add_argument("--base-url", required=True, help="API base URL")
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
            mark = "PASS" if step.passed else "FAIL"
            print(f"[{mark}] {step.name}: {step.detail}")
        print("RESULT:", "PASSED" if passed else "FAILED")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
