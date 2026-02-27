#!/usr/bin/env python3
"""
Audit lifecycle E2E verification script.

Flow:
1. Login
2. List published templates
3. Schedule audit run from template
4. Submit one response
5. Complete run
6. Create finding
7. Create incident from finding context
8. Create + close action on that incident

Exit code:
- 0 if all critical steps succeed
- 1 if any step fails
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import requests

TIMEOUT_SECONDS = 20


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
) -> requests.Response:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.request(method, url, headers=headers, json=payload, timeout=timeout)


def run(base_url: str, email: str, password: str) -> list[StepResult]:
    results: list[StepResult] = []
    token: Optional[str] = None
    run_id: Optional[int] = None
    template_id: Optional[int] = None
    question_id: Optional[int] = None
    finding_ref: str = "N/A"
    incident_id: Optional[int] = None
    action_id: Optional[int] = None

    # 1) Login
    login_resp = _request(
        "POST",
        f"{base_url}/api/v1/auth/login",
        payload={"email": email, "password": password},
    )
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

    # 2) List published templates
    templates_resp = _request("GET", f"{base_url}/api/v1/audits/templates?is_published=true&page=1&page_size=50", token=token)
    if templates_resp.status_code != 200:
        results.append(
            StepResult(
                "list_published_templates",
                False,
                f"Expected 200, got {templates_resp.status_code}",
                {"body": templates_resp.text[:300]},
            )
        )
        return results
    templates = templates_resp.json().get("items", [])
    if not templates:
        results.append(StepResult("list_published_templates", False, "No published templates available"))
        return results
    template_id = templates[0]["id"]
    results.append(
        StepResult(
            "list_published_templates",
            True,
            f"Selected template_id={template_id}",
            {"template_name": templates[0].get("name"), "template_version": templates[0].get("version")},
        )
    )

    # 3) Schedule run
    run_payload = {
        "template_id": template_id,
        "title": f"E2E Audit {datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "location": "E2E Validation Site",
        "scheduled_date": _now_iso(),
    }
    run_resp = _request("POST", f"{base_url}/api/v1/audits/runs", token=token, payload=run_payload)
    if run_resp.status_code != 201:
        results.append(
            StepResult(
                "schedule_run",
                False,
                f"Expected 201, got {run_resp.status_code}",
                {"body": run_resp.text[:300]},
            )
        )
        return results
    run_data = run_resp.json()
    run_id = run_data["id"]
    results.append(
        StepResult(
            "schedule_run",
            True,
            f"Created run_id={run_id}",
            {"reference_number": run_data.get("reference_number"), "template_version": run_data.get("template_version")},
        )
    )

    # 4) Fetch template detail and submit one response
    template_resp = _request("GET", f"{base_url}/api/v1/audits/templates/{template_id}", token=token)
    if template_resp.status_code != 200:
        results.append(
            StepResult(
                "template_detail",
                False,
                f"Expected 200, got {template_resp.status_code}",
                {"body": template_resp.text[:300]},
            )
        )
        return results
    sections = template_resp.json().get("sections", [])
    for section in sections:
        questions = section.get("questions", [])
        if questions:
            question_id = questions[0]["id"]
            break
    if not question_id:
        results.append(StepResult("template_detail", False, "Template has no questions"))
        return results
    results.append(StepResult("template_detail", True, f"Using question_id={question_id}"))

    response_payload = {
        "question_id": question_id,
        "response_value": "yes",
        "score": 1,
        "max_score": 1,
        "notes": "E2E response",
    }
    response_resp = _request("POST", f"{base_url}/api/v1/audits/runs/{run_id}/responses", token=token, payload=response_payload)
    if response_resp.status_code != 201:
        results.append(
            StepResult(
                "submit_response",
                False,
                f"Expected 201, got {response_resp.status_code}",
                {"body": response_resp.text[:300]},
            )
        )
        return results
    results.append(StepResult("submit_response", True, "One response submitted"))

    # 5) Complete run
    complete_resp = _request("POST", f"{base_url}/api/v1/audits/runs/{run_id}/complete", token=token)
    if complete_resp.status_code != 200:
        results.append(
            StepResult(
                "complete_run",
                False,
                f"Expected 200, got {complete_resp.status_code}",
                {"body": complete_resp.text[:300]},
            )
        )
        return results
    results.append(StepResult("complete_run", True, "Run completed"))

    # 6) Create finding
    finding_payload = {
        "title": "E2E Finding",
        "description": "Created by e2e audit lifecycle verification",
        "severity": "medium",
        "finding_type": "nonconformity",
        "corrective_action_required": True,
        "question_id": question_id,
    }
    finding_resp = _request("POST", f"{base_url}/api/v1/audits/runs/{run_id}/findings", token=token, payload=finding_payload)
    if finding_resp.status_code != 201:
        results.append(
            StepResult(
                "create_finding",
                False,
                f"Expected 201, got {finding_resp.status_code}",
                {"body": finding_resp.text[:300]},
            )
        )
        return results
    finding_data = finding_resp.json()
    finding_ref = finding_data.get("reference_number", "N/A")
    results.append(StepResult("create_finding", True, f"Finding created ({finding_ref})"))

    # 7) Create incident from finding context (bridge to unified actions module)
    incident_payload = {
        "title": f"Corrective action source for {finding_ref}",
        "description": f"Raised from audit finding {finding_ref}",
        "incident_type": "quality",
        "severity": "medium",
        "incident_date": _now_iso(),
        "reported_date": _now_iso(),
        "location": "E2E Validation Site",
        "department": "Governance",
    }
    incident_resp = _request("POST", f"{base_url}/api/v1/incidents/", token=token, payload=incident_payload)
    if incident_resp.status_code != 201:
        results.append(
            StepResult(
                "create_incident_for_action_bridge",
                False,
                f"Expected 201, got {incident_resp.status_code}",
                {"body": incident_resp.text[:300]},
            )
        )
        return results
    incident_id = incident_resp.json()["id"]
    results.append(StepResult("create_incident_for_action_bridge", True, f"Incident created ({incident_id})"))

    # 8) Create + close action
    action_payload = {
        "title": f"Action for {finding_ref}",
        "description": "Corrective action created by audit lifecycle e2e validation",
        "source_type": "incident",
        "source_id": incident_id,
        "priority": "medium",
    }
    action_resp = _request("POST", f"{base_url}/api/v1/actions/", token=token, payload=action_payload)
    if action_resp.status_code != 201:
        results.append(
            StepResult(
                "create_action",
                False,
                f"Expected 201, got {action_resp.status_code}",
                {"body": action_resp.text[:300]},
            )
        )
        return results
    action_id = action_resp.json()["id"]
    results.append(StepResult("create_action", True, f"Action created ({action_id})"))

    close_action_payload = {
        "status": "completed",
        "completion_notes": "Closed by automated audit lifecycle e2e run",
    }
    close_resp = _request(
        "PATCH",
        f"{base_url}/api/v1/actions/{action_id}?source_type=incident",
        token=token,
        payload=close_action_payload,
    )
    if close_resp.status_code != 200:
        results.append(
            StepResult(
                "close_action",
                False,
                f"Expected 200, got {close_resp.status_code}",
                {"body": close_resp.text[:300]},
            )
        )
        return results
    results.append(StepResult("close_action", True, "Action closed"))

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run audit lifecycle e2e smoke checks")
    parser.add_argument("--base-url", required=True, help="API base URL, e.g. https://qgp-staging-plantexpand.azurewebsites.net")
    parser.add_argument("--email", required=True, help="E2E user email")
    parser.add_argument("--password", required=True, help="E2E user password")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    results = run(base_url, args.email, args.password)
    passed = all(r.passed for r in results)

    output = {
        "base_url": base_url,
        "all_passed": passed,
        "steps": [
            {
                "name": r.name,
                "passed": r.passed,
                "detail": r.detail,
                "payload": r.payload,
            }
            for r in results
        ],
    }

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print("AUDIT LIFECYCLE E2E")
        for result in results:
            marker = "PASS" if result.passed else "FAIL"
            print(f"- {marker}: {result.name} :: {result.detail}")
        print(f"Overall: {'PASS' if passed else 'FAIL'}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
